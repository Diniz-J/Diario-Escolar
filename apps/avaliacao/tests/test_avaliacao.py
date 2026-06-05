"""Testes de `Avaliacao` + `NotaAvaliacao` + endpoint de lançamento em lote.

Cobre:
- auto-alocação de período pela data (model.save)
- auto-criação de NotaAvaliacao por aluno ativo da turma (perform_create)
- IDOR e escopo de escola
- lancar-notas em lote (sucesso, falha atômica, deslançar nota)
- endpoint /historico/ (consome simple_history)
- permissões por perfil
"""
from datetime import date
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.accounts.models import Usuario
from apps.avaliacao.models import Avaliacao, NotaAvaliacao, PeriodoAvaliativo
from apps.avaliacao.views import AvaliacaoViewSet, NotaAvaliacaoViewSet
from apps.escola.models import Aluno, Disciplina, Escola, Turma


class _Base(TestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        cls.factory = APIRequestFactory()
        cls.escola_a = Escola.objects.create(nome="Escola A")
        cls.escola_b = Escola.objects.create(nome="Escola B")

        cls.turma_a = Turma.objects.create(
            escola=cls.escola_a,
            nome="1º A",
            turno=Turma.Turno.MATUTINO,
            ano_letivo=2026,
        )
        cls.disciplina_a = Disciplina.objects.create(
            escola=cls.escola_a, nome="Matemática"
        )
        cls.periodo_1 = PeriodoAvaliativo.objects.create(
            escola=cls.escola_a,
            nome="1º Bim",
            ordem=1,
            ano_letivo=2026,
            data_inicio=date(2026, 2, 1),
            data_fim=date(2026, 4, 30),
        )
        cls.periodo_2 = PeriodoAvaliativo.objects.create(
            escola=cls.escola_a,
            nome="2º Bim",
            ordem=2,
            ano_letivo=2026,
            data_inicio=date(2026, 5, 1),
            data_fim=date(2026, 7, 31),
        )

        # 3 alunos ativos + 1 inativo (não deve aparecer nas notas).
        cls.aluno1 = Aluno.objects.create(
            escola=cls.escola_a,
            turma=cls.turma_a,
            matricula="001",
            nome_completo="Ana",
            nome_responsavel="r",
            email_responsavel="r@r.com",
        )
        cls.aluno2 = Aluno.objects.create(
            escola=cls.escola_a,
            turma=cls.turma_a,
            matricula="002",
            nome_completo="Bia",
            nome_responsavel="r",
            email_responsavel="r@r.com",
        )
        cls.aluno3 = Aluno.objects.create(
            escola=cls.escola_a,
            turma=cls.turma_a,
            matricula="003",
            nome_completo="Caio",
            nome_responsavel="r",
            email_responsavel="r@r.com",
        )
        cls.aluno_inativo = Aluno.objects.create(
            escola=cls.escola_a,
            turma=cls.turma_a,
            matricula="004",
            nome_completo="Inativo",
            ativo=False,
            nome_responsavel="r",
            email_responsavel="r@r.com",
        )

        cls.admin = Usuario.objects.create_user(
            username="adm", password="x", perfil=Usuario.Perfil.ADMIN
        )
        cls.diretor = Usuario.objects.create_user(
            username="dir",
            password="x",
            perfil=Usuario.Perfil.DIRETOR,
            escola=cls.escola_a,
        )
        cls.professor = Usuario.objects.create_user(
            username="prof",
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

    def _request(
        self,
        method: str,
        viewset_cls=AvaliacaoViewSet,
        payload: dict | None = None,
        user=None,
        pk=None,
        url_path: str | None = None,
    ):
        path = f"/{pk}/" if pk else "/"
        if url_path:
            path = f"{path.rstrip('/')}/{url_path}/"
        if method == "list":
            req = self.factory.get(path)
            view = viewset_cls.as_view({"get": "list"})
        elif method == "create":
            req = self.factory.post(path, payload or {}, format="json")
            view = viewset_cls.as_view({"post": "create"})
        elif method == "retrieve":
            req = self.factory.get(path)
            view = viewset_cls.as_view({"get": "retrieve"})
        elif method == "post_lancar":
            req = self.factory.post(path, payload or {}, format="json")
            view = viewset_cls.as_view({"post": "lancar_notas"})
        elif method == "get_historico":
            req = self.factory.get(path)
            view = viewset_cls.as_view({"get": "historico"})
        else:
            raise ValueError(method)
        force_authenticate(req, user=user or self.diretor)
        if pk:
            return view(req, pk=pk)
        return view(req)

    def _payload_avaliacao(self, **overrides) -> dict:
        base = {
            "turma": self.turma_a.id,
            "disciplina": self.disciplina_a.id,
            "titulo": "Prova 1",
            "tipo": "prova",
            "data": "2026-03-15",
            "nota_maxima": "10.00",
        }
        base.update(overrides)
        return base


# ===================================================================== #
# Auto-aloca período + auto-cria NotaAvaliacao                           #
# ===================================================================== #


class AvaliacaoAutoTests(_Base):
    def test_periodo_alocado_pela_data(self):
        """Data no 1º bim deve alocar `periodo=periodo_1` automaticamente."""
        resp = self._request("create", payload=self._payload_avaliacao())
        self.assertEqual(resp.status_code, 201, resp.data)
        avaliacao = Avaliacao.objects.get(id=resp.data["id"])
        self.assertEqual(avaliacao.periodo_id, self.periodo_1.id)

    def test_periodo_null_quando_data_fora_de_qualquer_periodo(self):
        """Data em janeiro (antes do 1º bim) → `periodo=None`, não bloqueia."""
        resp = self._request(
            "create",
            payload=self._payload_avaliacao(data="2026-01-15"),
        )
        self.assertEqual(resp.status_code, 201)
        avaliacao = Avaliacao.objects.get(id=resp.data["id"])
        self.assertIsNone(avaliacao.periodo_id)

    def test_auto_cria_nota_para_cada_aluno_ativo(self):
        resp = self._request("create", payload=self._payload_avaliacao())
        self.assertEqual(resp.status_code, 201)
        avaliacao = Avaliacao.objects.get(id=resp.data["id"])
        # 3 ativos, 1 inativo — espera 3 NotaAvaliacao.
        self.assertEqual(avaliacao.notas.count(), 3)
        alunos_com_nota = set(avaliacao.notas.values_list("aluno_id", flat=True))
        self.assertEqual(
            alunos_com_nota,
            {self.aluno1.id, self.aluno2.id, self.aluno3.id},
        )

    def test_periodo_recalculado_quando_data_e_editada(self):
        """Editar data move a avaliação pro período correspondente."""
        resp = self._request("create", payload=self._payload_avaliacao())
        avaliacao = Avaliacao.objects.get(id=resp.data["id"])
        self.assertEqual(avaliacao.periodo_id, self.periodo_1.id)

        avaliacao.data = date(2026, 6, 10)  # cai no 2º bim
        avaliacao.save()
        avaliacao.refresh_from_db()
        self.assertEqual(avaliacao.periodo_id, self.periodo_2.id)


# ===================================================================== #
# Escopo + IDOR                                                          #
# ===================================================================== #


class EscopoEIdorTests(_Base):
    def test_diretor_so_ve_avaliacoes_da_propria_escola(self):
        # Cria avaliação na escola B.
        turma_b = Turma.objects.create(
            escola=self.escola_b,
            nome="1º A",
            turno=Turma.Turno.MATUTINO,
            ano_letivo=2026,
        )
        disc_b = Disciplina.objects.create(escola=self.escola_b, nome="Mat")
        Avaliacao.objects.create(
            escola=self.escola_b,
            turma=turma_b,
            disciplina=disc_b,
            titulo="X",
            data=date(2026, 3, 15),
            nota_maxima=Decimal("10"),
        )
        resp = self._request("list", user=self.diretor)
        self.assertEqual(resp.status_code, 200)
        # Diretor A não vê a da escola B.
        titulos = [a["titulo"] for a in resp.data]
        self.assertNotIn("X", titulos)

    def test_idor_payload_escola_alheia_bloqueado(self):
        resp = self._request(
            "create",
            payload=self._payload_avaliacao(escola=self.escola_b.id),
        )
        self.assertEqual(resp.status_code, 400)

    def test_admin_sem_escola_recebe_400_em_vez_de_500(self):
        """Admin global (sem `escola_id`) que esquece de passar escola
        no payload deve receber 400 explicito, nao IntegrityError 500.

        Cenario real: admin operando direto na API, ou usuario com JWT
        antigo (gerado antes de ele ser vinculado a uma escola). Sem
        este guard o INSERT explode no banco com mensagem opaca.
        """
        resp = self._request(
            "create", payload=self._payload_avaliacao(), user=self.admin
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("escola", resp.data)
        # Mensagem diferenciada — admin global ve orientacao de selecao,
        # nao "faca logout" (que seria pra perfil normal sem escola).
        msg = str(resp.data["escola"][0]).lower()
        self.assertIn("administrador", msg)

    def test_admin_passando_escola_explicita_funciona(self):
        """Admin que escolhe a escola no formulario (frontend ja faz
        isso quando user.escola_id eh null) consegue criar normalmente."""
        resp = self._request(
            "create",
            payload=self._payload_avaliacao(escola=self.escola_a.id),
            user=self.admin,
        )
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data["escola"], self.escola_a.id)


# ===================================================================== #
# Lançamento em lote                                                     #
# ===================================================================== #


class LancarNotasTests(_Base):
    def _criar_avaliacao(self) -> Avaliacao:
        resp = self._request("create", payload=self._payload_avaliacao())
        return Avaliacao.objects.get(id=resp.data["id"])

    def test_lancar_notas_atualiza_em_lote(self):
        avaliacao = self._criar_avaliacao()
        payload = {
            "itens": [
                {
                    "aluno_id": self.aluno1.id,
                    "nota": "8.50",
                    "observacao": "muito bem",
                },
                {"aluno_id": self.aluno2.id, "nota": "7.00"},
            ]
        }
        resp = self._request(
            "post_lancar", payload=payload, pk=avaliacao.id, url_path="lancar-notas"
        )
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data["atualizadas"], 2)
        self.assertEqual(resp.data["falhas"], [])

        nota1 = NotaAvaliacao.objects.get(
            avaliacao=avaliacao, aluno=self.aluno1
        )
        self.assertEqual(nota1.nota, Decimal("8.50"))
        self.assertEqual(nota1.observacao, "muito bem")

        # Aluno3 não foi tocado — nota continua null.
        nota3 = NotaAvaliacao.objects.get(
            avaliacao=avaliacao, aluno=self.aluno3
        )
        self.assertIsNone(nota3.nota)

    def test_lancar_notas_atomico_falha_total_se_aluno_invalido(self):
        avaliacao = self._criar_avaliacao()
        payload = {
            "itens": [
                {"aluno_id": self.aluno1.id, "nota": "8.50"},
                # Aluno que NAO pertence a esta avaliacao.
                {"aluno_id": 99999, "nota": "5.00"},
            ]
        }
        resp = self._request(
            "post_lancar", payload=payload, pk=avaliacao.id, url_path="lancar-notas"
        )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.data["atualizadas"], 0)
        self.assertEqual(len(resp.data["falhas"]), 1)

        # Confere rollback: aluno1 NÃO foi atualizado.
        nota1 = NotaAvaliacao.objects.get(
            avaliacao=avaliacao, aluno=self.aluno1
        )
        self.assertIsNone(nota1.nota)

    def test_lancar_pode_deslancar_passando_nota_null(self):
        """Aceita `nota=null` pra apagar uma nota antes lançada."""
        avaliacao = self._criar_avaliacao()
        nota1 = NotaAvaliacao.objects.get(avaliacao=avaliacao, aluno=self.aluno1)
        nota1.nota = Decimal("9.00")
        nota1.save()

        resp = self._request(
            "post_lancar",
            payload={"itens": [{"aluno_id": self.aluno1.id, "nota": None}]},
            pk=avaliacao.id,
            url_path="lancar-notas",
        )
        self.assertEqual(resp.status_code, 200)
        nota1.refresh_from_db()
        self.assertIsNone(nota1.nota)

    def test_professor_pode_lancar(self):
        """Decisão do Diniz: qualquer professor da escola pode lançar."""
        avaliacao = self._criar_avaliacao()
        resp = self._request(
            "post_lancar",
            payload={"itens": [{"aluno_id": self.aluno1.id, "nota": "5.0"}]},
            pk=avaliacao.id,
            user=self.professor,
            url_path="lancar-notas",
        )
        self.assertEqual(resp.status_code, 200)


# ===================================================================== #
# Histórico (audit log)                                                   #
# ===================================================================== #


class HistoricoNotaTests(_Base):
    def test_endpoint_historico_retorna_snapshots(self):
        # Cria avaliação + atualiza uma nota duas vezes.
        #
        # Nota: a auto-criação das NotaAvaliacao no perform_create usa
        # `bulk_create`, que NÃO dispara post_save — então o simple_history
        # não registra a criação inicial. Cada `.save()` subsequente sim
        # vira snapshot. Pra audit do produto isso é OK: o que importa é
        # "quem mudou a nota X pra Y, quando" — não importa quem criou o
        # registro vazio inicial.
        resp = self._request("create", payload=self._payload_avaliacao())
        avaliacao = Avaliacao.objects.get(id=resp.data["id"])
        nota1 = NotaAvaliacao.objects.get(
            avaliacao=avaliacao, aluno=self.aluno1
        )
        nota1.nota = Decimal("7")
        nota1.save()
        nota1.nota = Decimal("8.5")
        nota1.save()

        resp = self._request(
            "get_historico",
            viewset_cls=NotaAvaliacaoViewSet,
            pk=nota1.id,
            url_path="historico",
        )
        self.assertEqual(resp.status_code, 200)
        eventos = resp.data["eventos"]
        # 2 updates registrados (bulk_create da criação não vira evento).
        self.assertEqual(len(eventos), 2)
        # Mais recente primeiro: o `nota` da primeira entrada é a última gravada.
        self.assertEqual(eventos[0]["nota"], "8.50")
        self.assertEqual(eventos[1]["nota"], "7.00")
