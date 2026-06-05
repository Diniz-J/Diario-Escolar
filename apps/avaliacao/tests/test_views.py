"""Testes do PeriodoAvaliativoViewSet.

Cobre permissão por perfil, escopo de escola (EscopoEscolaMixin),
guard IDOR no payload, soft delete, validação propagada do model
(sobreposição) e audit log via simple_history.
"""
from datetime import date

from django.test import TestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.accounts.models import Usuario
from apps.avaliacao.models import PeriodoAvaliativo
from apps.avaliacao.views import PeriodoAvaliativoViewSet
from apps.escola.models import Escola


class _Base(TestCase):
    """Setup: 2 escolas + 1 usuário de cada perfil relevante."""

    @classmethod
    def setUpTestData(cls) -> None:
        cls.factory = APIRequestFactory()
        cls.escola_a = Escola.objects.create(nome="Escola A")
        cls.escola_b = Escola.objects.create(nome="Escola B")

        cls.admin = Usuario.objects.create_user(
            username="adm", password="x", perfil=Usuario.Perfil.ADMIN
        )
        cls.diretor_a = Usuario.objects.create_user(
            username="dir_a",
            password="x",
            perfil=Usuario.Perfil.DIRETOR,
            escola=cls.escola_a,
        )
        cls.secretaria_a = Usuario.objects.create_user(
            username="sec_a",
            password="x",
            perfil=Usuario.Perfil.SECRETARIA,
            escola=cls.escola_a,
        )
        cls.professor_a = Usuario.objects.create_user(
            username="prof_a",
            password="x",
            perfil=Usuario.Perfil.PROFESSOR,
            escola=cls.escola_a,
        )
        cls.diretor_b = Usuario.objects.create_user(
            username="dir_b",
            password="x",
            perfil=Usuario.Perfil.DIRETOR,
            escola=cls.escola_b,
        )

        cls.periodo_a = PeriodoAvaliativo.objects.create(
            escola=cls.escola_a,
            nome="1º Bim",
            ordem=1,
            ano_letivo=2026,
            data_inicio=date(2026, 2, 1),
            data_fim=date(2026, 4, 30),
        )
        cls.periodo_b = PeriodoAvaliativo.objects.create(
            escola=cls.escola_b,
            nome="1º Bim",
            ordem=1,
            ano_letivo=2026,
            data_inicio=date(2026, 2, 1),
            data_fim=date(2026, 4, 30),
        )

    def _request(self, method: str, payload: dict | None = None, user=None, pk=None):
        path = f"/{pk}/" if pk else "/"
        if method == "list":
            req = self.factory.get(path)
            view = PeriodoAvaliativoViewSet.as_view({"get": "list"})
        elif method == "create":
            req = self.factory.post(path, payload or {}, format="json")
            view = PeriodoAvaliativoViewSet.as_view({"post": "create"})
        elif method == "delete":
            req = self.factory.delete(path)
            view = PeriodoAvaliativoViewSet.as_view({"delete": "destroy"})
        elif method == "update":
            req = self.factory.patch(path, payload or {}, format="json")
            view = PeriodoAvaliativoViewSet.as_view({"patch": "partial_update"})
        else:
            raise ValueError(method)
        force_authenticate(req, user=user or self.diretor_a)
        if pk:
            return view(req, pk=pk)
        return view(req)


# ===================================================================== #
# Permissões                                                             #
# ===================================================================== #


class PermissionTests(_Base):
    def test_list_professor_aceito(self):
        """Leitura ampla — professor/inspetor precisam ver pra contextualizar
        avaliações que vão pousar no período."""
        resp = self._request("list", user=self.professor_a)
        self.assertEqual(resp.status_code, 200)

    def test_list_secretaria_aceito(self):
        resp = self._request("list", user=self.secretaria_a)
        self.assertEqual(resp.status_code, 200)

    def test_create_diretor_aceito(self):
        resp = self._request(
            "create",
            {
                "nome": "2º Bim",
                "ordem": 2,
                "ano_letivo": 2026,
                "data_inicio": "2026-05-01",
                "data_fim": "2026-07-15",
            },
        )
        self.assertEqual(resp.status_code, 201, resp.data)

    def test_create_secretaria_aceito(self):
        resp = self._request(
            "create",
            {
                "nome": "2º Bim",
                "ordem": 2,
                "ano_letivo": 2026,
                "data_inicio": "2026-05-01",
                "data_fim": "2026-07-15",
            },
            user=self.secretaria_a,
        )
        self.assertEqual(resp.status_code, 201, resp.data)

    def test_create_professor_negado(self):
        resp = self._request(
            "create",
            {
                "nome": "2º Bim",
                "ordem": 2,
                "ano_letivo": 2026,
                "data_inicio": "2026-05-01",
                "data_fim": "2026-07-15",
            },
            user=self.professor_a,
        )
        self.assertEqual(resp.status_code, 403)


# ===================================================================== #
# Escopo de escola + IDOR                                                #
# ===================================================================== #


class EscopoTests(_Base):
    def test_diretor_so_ve_periodos_da_propria_escola(self):
        resp = self._request("list")
        self.assertEqual(resp.status_code, 200)
        ids = [p["id"] for p in resp.data]
        self.assertIn(self.periodo_a.id, ids)
        self.assertNotIn(self.periodo_b.id, ids)

    def test_admin_global_ve_todas_as_escolas(self):
        resp = self._request("list", user=self.admin)
        self.assertEqual(resp.status_code, 200)
        ids = [p["id"] for p in resp.data]
        self.assertIn(self.periodo_a.id, ids)
        self.assertIn(self.periodo_b.id, ids)

    def test_auto_escopo_injeta_escola_no_create(self):
        """Diretor não passa escola no payload — o mixin injeta pelo JWT."""
        resp = self._request(
            "create",
            {
                "nome": "2º Bim",
                "ordem": 2,
                "ano_letivo": 2026,
                "data_inicio": "2026-05-01",
                "data_fim": "2026-07-15",
            },
        )
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.data["escola"], self.escola_a.id)

    def test_idor_bloqueia_escola_alheia_no_payload(self):
        """Diretor da A mandando `escola=B` no payload tem que ser bloqueado."""
        resp = self._request(
            "create",
            {
                "escola": self.escola_b.id,
                "nome": "2º Bim",
                "ordem": 2,
                "ano_letivo": 2026,
                "data_inicio": "2026-05-01",
                "data_fim": "2026-07-15",
            },
        )
        self.assertEqual(resp.status_code, 400)


# ===================================================================== #
# Validações de domínio propagadas pelo serializer                       #
# ===================================================================== #


class ValidacaoTests(_Base):
    def test_create_com_sobreposicao_falha_com_400(self):
        resp = self._request(
            "create",
            {
                "nome": "2º Bim",
                "ordem": 2,
                "ano_letivo": 2026,
                "data_inicio": "2026-04-15",  # sobrepõe o 1º Bim existente
                "data_fim": "2026-06-30",
            },
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("data_inicio", resp.data)

    def test_create_data_fim_antes_de_inicio_falha(self):
        resp = self._request(
            "create",
            {
                "nome": "Z",
                "ordem": 9,
                "ano_letivo": 2026,
                "data_inicio": "2026-06-01",
                "data_fim": "2026-05-01",
            },
        )
        self.assertEqual(resp.status_code, 400)


# ===================================================================== #
# Soft delete + audit                                                    #
# ===================================================================== #


class SoftDeleteTests(_Base):
    def test_delete_marca_ativo_false_em_vez_de_apagar(self):
        resp = self._request("delete", pk=self.periodo_a.id)
        self.assertEqual(resp.status_code, 204)
        # Registro continua no banco, só com `ativo=False`.
        self.periodo_a.refresh_from_db()
        self.assertFalse(self.periodo_a.ativo)

    def test_audit_log_registra_snapshot_no_update(self):
        """Update via API gera snapshot no histórico do simple-history.

        Nota: `history_user_id` fica `None` neste teste porque
        `APIRequestFactory + force_authenticate` não passa pelo
        `HistoryRequestMiddleware` (que popula o thread-local lido
        pelo `simple_history` em runtime). Em produção/staging o user
        é capturado normalmente — a validação dessa parte vive nos
        testes de integração da suite.
        """
        resp = self._request(
            "update",
            {"nome": "1º Bimestre"},
            pk=self.periodo_a.id,
        )
        self.assertEqual(resp.status_code, 200)
        ultimo = self.periodo_a.history.first()
        self.assertIsNotNone(ultimo)
        self.assertEqual(ultimo.nome, "1º Bimestre")
