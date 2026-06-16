"""Testes do `RegistroAulaViewSet` — CRUD, escopo, conferência e agenda."""
from datetime import date

from rest_framework.test import APIRequestFactory, force_authenticate

from django.test import TestCase

from apps.accounts.models import Usuario
from apps.aulas.models import RegistroAula
from apps.aulas.views import RegistroAulaViewSet
from apps.escola.models import (
    Disciplina,
    Escola,
    Lecionamento,
    Professor,
    Turma,
)


class _AulasSetup(TestCase):
    """Escola com turma/disciplina, professor com lecionamento e perfis."""

    @classmethod
    def setUpTestData(cls) -> None:
        cls.factory = APIRequestFactory()
        cls.escola = Escola.objects.create(nome="Escola Teste")
        cls.turma = Turma.objects.create(
            escola=cls.escola,
            nome="1º A",
            turno=Turma.Turno.MATUTINO,
            ano_letivo=2026,
        )
        cls.disciplina = Disciplina.objects.create(
            escola=cls.escola, nome="Matemática"
        )
        cls.usuario_docente = Usuario.objects.create_user(
            username="doc",
            password="x",
            perfil=Usuario.Perfil.PROFESSOR,
            escola=cls.escola,
        )
        cls.professor = Professor.objects.create(
            escola=cls.escola, usuario=cls.usuario_docente
        )
        cls.lecionamento = Lecionamento.objects.create(
            escola=cls.escola,
            professor=cls.professor,
            turma=cls.turma,
            disciplina=cls.disciplina,
            dias_semana=[0, 2],  # segunda e quarta
        )
        cls.diretor = Usuario.objects.create_user(
            username="dir",
            password="x",
            perfil=Usuario.Perfil.DIRETOR,
            escola=cls.escola,
        )

    def _payload(self, **overrides) -> dict:
        dados = {
            "escola": self.escola.id,
            "turma": self.turma.id,
            "disciplina": self.disciplina.id,
            "professor": self.professor.id,
            "data": date.today().isoformat(),
            "conteudo": "Equação do 2º grau",
            "status": RegistroAula.Status.LANCADO,
        }
        dados.update(overrides)
        return dados

    def _criar_registro(self, **overrides) -> RegistroAula:
        dados = {
            "escola": self.escola,
            "turma": self.turma,
            "disciplina": self.disciplina,
            "professor": self.professor,
            "data": date.today(),
            "conteudo": "Conteúdo",
            "status": RegistroAula.Status.LANCADO,
        }
        dados.update(overrides)
        return RegistroAula.objects.create(**dados)


class RegistroAulaCrudTests(_AulasSetup):
    def test_professor_cria_para_si(self):
        req = self.factory.post("/", self._payload(), format="json")
        force_authenticate(req, user=self.usuario_docente)
        resp = RegistroAulaViewSet.as_view({"post": "create"})(req)
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.data["professor"], self.professor.id)

    def test_serializer_recusa_status_conferido(self):
        req = self.factory.post(
            "/", self._payload(status=RegistroAula.Status.CONFERIDO), format="json"
        )
        force_authenticate(req, user=self.usuario_docente)
        resp = RegistroAulaViewSet.as_view({"post": "create"})(req)
        self.assertEqual(resp.status_code, 400)
        self.assertIn("status", resp.data)

    def test_lancar_sem_conteudo_falha(self):
        req = self.factory.post(
            "/", self._payload(conteudo=""), format="json"
        )
        force_authenticate(req, user=self.usuario_docente)
        resp = RegistroAulaViewSet.as_view({"post": "create"})(req)
        self.assertEqual(resp.status_code, 400)
        self.assertIn("conteudo", resp.data)

    def test_aula_conferida_nao_pode_ser_editada(self):
        registro = self._criar_registro(status=RegistroAula.Status.CONFERIDO)
        req = self.factory.patch("/", {"conteudo": "novo"}, format="json")
        force_authenticate(req, user=self.diretor)
        resp = RegistroAulaViewSet.as_view({"patch": "partial_update"})(
            req, pk=registro.id
        )
        self.assertEqual(resp.status_code, 400)


class RegistroAulaEscopoTests(_AulasSetup):
    @classmethod
    def setUpTestData(cls) -> None:
        super().setUpTestData()
        # Outro professor da mesma escola, com seu próprio registro.
        cls.usuario_outro = Usuario.objects.create_user(
            username="doc2",
            password="x",
            perfil=Usuario.Perfil.PROFESSOR,
            escola=cls.escola,
        )
        cls.outro_professor = Professor.objects.create(
            escola=cls.escola, usuario=cls.usuario_outro
        )
        cls.reg_proprio = RegistroAula.objects.create(
            escola=cls.escola,
            turma=cls.turma,
            disciplina=cls.disciplina,
            professor=cls.professor,
            data=date(2026, 1, 7),
            conteudo="Conteúdo próprio",
            status=RegistroAula.Status.LANCADO,
        )

    def test_professor_so_ve_os_proprios(self):
        # Registro de outro professor não deve aparecer.
        outro_reg = RegistroAula.objects.create(
            escola=self.escola,
            turma=self.turma,
            disciplina=self.disciplina,
            professor=self.outro_professor,
            data=date(2026, 1, 5),
            conteudo="x",
            status=RegistroAula.Status.LANCADO,
        )
        req = self.factory.get("/")
        force_authenticate(req, user=self.usuario_docente)
        resp = RegistroAulaViewSet.as_view({"get": "list"})(req)
        ids = {item["id"] for item in resp.data}
        self.assertIn(self.reg_proprio.id, ids)
        self.assertNotIn(outro_reg.id, ids)

    def test_diretor_ve_todos_da_escola(self):
        outro_reg = RegistroAula.objects.create(
            escola=self.escola,
            turma=self.turma,
            disciplina=self.disciplina,
            professor=self.outro_professor,
            data=date(2026, 1, 6),
            conteudo="x",
            status=RegistroAula.Status.LANCADO,
        )
        req = self.factory.get("/")
        force_authenticate(req, user=self.diretor)
        resp = RegistroAulaViewSet.as_view({"get": "list"})(req)
        ids = {item["id"] for item in resp.data}
        self.assertIn(self.reg_proprio.id, ids)
        self.assertIn(outro_reg.id, ids)


class RegistroAulaConferirTests(_AulasSetup):
    def test_diretor_confere_aula_lancada(self):
        registro = self._criar_registro(status=RegistroAula.Status.LANCADO)
        req = self.factory.post("/")
        force_authenticate(req, user=self.diretor)
        resp = RegistroAulaViewSet.as_view({"post": "conferir"})(
            req, pk=registro.id
        )
        self.assertEqual(resp.status_code, 200)
        registro.refresh_from_db()
        self.assertEqual(registro.status, RegistroAula.Status.CONFERIDO)
        self.assertEqual(registro.conferido_por_id, self.diretor.id)
        self.assertIsNotNone(registro.conferido_em)

    def test_conferir_aula_em_rascunho_falha(self):
        registro = self._criar_registro(
            status=RegistroAula.Status.RASCUNHO, conteudo=""
        )
        req = self.factory.post("/")
        force_authenticate(req, user=self.diretor)
        resp = RegistroAulaViewSet.as_view({"post": "conferir"})(
            req, pk=registro.id
        )
        self.assertEqual(resp.status_code, 400)

    def test_professor_nao_pode_conferir(self):
        registro = self._criar_registro(status=RegistroAula.Status.LANCADO)
        req = self.factory.post("/")
        force_authenticate(req, user=self.usuario_docente)
        resp = RegistroAulaViewSet.as_view({"post": "conferir"})(
            req, pk=registro.id
        )
        self.assertEqual(resp.status_code, 403)


class RegistroAulaAgendaTests(_AulasSetup):
    def test_agenda_projeta_apenas_dias_da_grade(self):
        mes = date.today().strftime("%Y-%m")
        req = self.factory.get(
            f"/?turma={self.turma.id}&disciplina={self.disciplina.id}&mes={mes}"
        )
        force_authenticate(req, user=self.usuario_docente)
        resp = RegistroAulaViewSet.as_view({"get": "agenda"})(req)
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(len(resp.data) > 0)
        # Lecionamento tem aula só seg(0)/qua(2).
        self.assertTrue(all(s["dia_semana"] in (0, 2) for s in resp.data))

    def test_agenda_exige_parametros(self):
        req = self.factory.get("/")
        force_authenticate(req, user=self.usuario_docente)
        resp = RegistroAulaViewSet.as_view({"get": "agenda"})(req)
        self.assertEqual(resp.status_code, 400)
