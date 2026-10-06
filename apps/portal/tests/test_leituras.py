"""Testes das leituras do portal (fatia 4 do `PORTAL.md`).

Verificação da fatia: responsável A não lê nada do aluno de B; id alheio
na URL dá 404; rascunho invisível. Mais: período de outra escola, filho
inativo, comunicado por log de entrega e ausência de N+1.
"""
from datetime import date

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.accounts.models import Usuario
from apps.avaliacao.models import PeriodoAvaliativo
from apps.comunicados.models import Comunicado, ComunicadoDestinatario
from apps.escola.models import Aluno, Escola, Professor, Turma
from apps.ocorrencias.models import Ocorrencia
from apps.portal.models import Responsavel, ResponsavelAluno
from apps.portal.tokens import PortalRefreshToken

ENVIADO = Comunicado.Status.ENVIADO


class _LeiturasSetup(TestCase):
    """Duas famílias na Escola A, uma escola B. Helpers sem testes."""

    @classmethod
    def setUpTestData(cls) -> None:
        cls.escola = Escola.objects.create(nome="Escola A")
        cls.outra_escola = Escola.objects.create(nome="Escola B")
        cls.turma1 = cls._turma(cls.escola, "1º A")
        cls.turma2 = cls._turma(cls.escola, "2º A")
        cls.turma_b = cls._turma(cls.outra_escola, "1º A")

        cls.filho = cls._aluno("Ana Filha", cls.turma1)
        cls.filho_inativo = cls._aluno("Ana Transferida", cls.turma1, ativo=False)
        cls.filho_beto = cls._aluno("Beto Filho", cls.turma2)
        cls.aluno_b = cls._aluno("Aluno B", cls.turma_b)

        cls.ana = cls._responsavel(cls.escola, "ana@example.com", [cls.filho, cls.filho_inativo])
        cls.beto = cls._responsavel(cls.escola, "beto@example.com", [cls.filho_beto])

        prof_usuario = Usuario.objects.create_user(
            username="prof", password="x", perfil=Usuario.Perfil.PROFESSOR,
            escola=cls.escola, first_name="Carla", last_name="Professora",
        )
        cls.professor = Professor.objects.create(usuario=prof_usuario, escola=cls.escola)
        cls.ocorrencia = Ocorrencia.objects.create(
            escola=cls.escola, turma=cls.turma1, aluno=cls.filho,
            professor=cls.professor, descricao="Conversa durante a prova.",
        )
        cls.ocorrencia_beto = Ocorrencia.objects.create(
            escola=cls.escola, turma=cls.turma2, aluno=cls.filho_beto,
            descricao="Atraso.",
        )

        cls.periodo = cls._periodo(cls.escola)
        cls.periodo_b = cls._periodo(cls.outra_escola)

        # Comunicados: o que vale é o log de entrega (quem foi endereçado).
        cls.c_escola = cls._comunicado(cls.escola, ENVIADO, [cls.filho, cls.filho_beto])
        cls.c_antigo = cls._comunicado(cls.escola, ENVIADO, [cls.filho_inativo])
        cls.c_turma2 = cls._comunicado(cls.escola, ENVIADO, [cls.filho_beto])
        cls.c_rascunho = cls._comunicado(cls.escola, Comunicado.Status.RASCUNHO, [cls.filho])
        cls.c_falhou = cls._comunicado(cls.escola, Comunicado.Status.FALHOU, [cls.filho])
        cls.c_outra_escola = cls._comunicado(cls.outra_escola, ENVIADO, [cls.aluno_b])

    @staticmethod
    def _turma(escola, nome):
        return Turma.objects.create(
            escola=escola, nome=nome, turno=Turma.Turno.MATUTINO, ano_letivo=2026
        )

    @staticmethod
    def _aluno(nome, turma, ativo=True):
        return Aluno.objects.create(
            escola=turma.escola,
            matricula=f"M{Aluno.objects.count() + 1}",
            nome_completo=nome,
            turma=turma,
            ativo=ativo,
        )

    @staticmethod
    def _responsavel(escola, email, filhos):
        r = Responsavel.objects.create(escola=escola, email=email, nome=email)
        for filho in filhos:
            ResponsavelAluno.objects.create(responsavel=r, aluno=filho)
        return r

    @staticmethod
    def _periodo(escola):
        return PeriodoAvaliativo.objects.create(
            escola=escola, nome="1º Bimestre", ordem=1, ano_letivo=2026,
            data_inicio=date(2026, 2, 1), data_fim=date(2026, 4, 30),
        )

    @staticmethod
    def _comunicado(escola, status, alunos):
        c = Comunicado.objects.create(
            escola=escola, titulo=f"Aviso {status}", mensagem="Texto.", status=status,
            enviado_em=timezone.now() if status == ENVIADO else None,
        )
        for aluno in alunos:
            ComunicadoDestinatario.objects.create(
                comunicado=c, aluno=aluno, status=ComunicadoDestinatario.Status.ENVIADO
            )
        return c

    def setUp(self) -> None:
        self.client = APIClient()
        self._entrar(self.ana)

    def _entrar(self, responsavel):
        access = PortalRefreshToken.para_responsavel(responsavel).access_token
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")

    def _get(self, nome, *args, **params):
        return self.client.get(reverse(f"api_v1:{nome}", args=args), params)


class AutorizacaoPorVinculoTests(_LeiturasSetup):
    """`PORTAL.md` 4.2: responsável A não lê nada do aluno de B."""

    def test_aluno_alheio_da_404_em_todo_endpoint(self):
        for nome in ("portal_aluno", "portal_aluno_boletim", "portal_aluno_ocorrencias"):
            with self.subTest(nome):
                self.assertEqual(self._get(nome, self.filho_beto.pk).status_code, 404)
                # Aluno de outra escola também.
                self.assertEqual(self._get(nome, self.aluno_b.pk).status_code, 404)

    def test_id_inexistente_e_id_alheio_respondem_igual(self):
        alheio = self._get("portal_aluno", self.filho_beto.pk)
        inexistente = self._get("portal_aluno", 999_999)
        self.assertEqual(alheio.status_code, inexistente.status_code)
        self.assertEqual(alheio.data, inexistente.data)

    def test_lista_so_os_proprios_filhos_incluindo_inativo(self):
        nomes = [a["nome_completo"] for a in self._get("portal_alunos").data]
        self.assertEqual(nomes, ["Ana Filha", "Ana Transferida"])

    def test_vinculo_cruzado_criado_sem_clean_nao_abre_aluno_de_outra_escola(self):
        """`objects.create()` pula o `clean()` que barra vínculo entre
        escolas; a leitura não pode depender só dele."""
        ResponsavelAluno.objects.create(responsavel=self.ana, aluno=self.aluno_b)
        ids = [a["id"] for a in self._get("portal_alunos").data]
        self.assertNotIn(self.aluno_b.pk, ids)
        for nome in ("portal_aluno", "portal_aluno_boletim", "portal_aluno_ocorrencias"):
            with self.subTest(nome):
                self.assertEqual(self._get(nome, self.aluno_b.pk).status_code, 404)

    def test_token_de_staff_e_recusado(self):
        token = AccessToken()
        token["user_id"] = str(self.professor.usuario.pk)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        self.assertEqual(self._get("portal_alunos").status_code, 401)


class BoletimTests(_LeiturasSetup):
    def test_boletim_anual_do_filho(self):
        resp = self._get("portal_aluno_boletim", self.filho.pk)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["aluno"]["id"], self.filho.pk)
        self.assertEqual(resp.data["ocorrencias"]["total"], 1)

    def test_boletim_por_periodo_da_escola(self):
        resp = self._get("portal_aluno_boletim", self.filho.pk, periodo=self.periodo.pk)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["periodo"]["id"], self.periodo.pk)

    def test_periodo_de_outra_escola_da_404_sem_vazar_dados(self):
        resp = self._get("portal_aluno_boletim", self.filho.pk, periodo=self.periodo_b.pk)
        self.assertEqual(resp.status_code, 404)
        self.assertEqual(
            self._get("portal_aluno_boletim", self.filho.pk, periodo="abc").status_code, 404
        )

    def test_filho_inativo_continua_com_boletim(self):
        resp = self._get("portal_aluno_boletim", self.filho_inativo.pk)
        self.assertEqual(resp.status_code, 200)

    def test_periodos_so_da_escola(self):
        ids = [p["id"] for p in self._get("portal_periodos").data]
        self.assertEqual(ids, [self.periodo.pk])


class OcorrenciasTests(_LeiturasSetup):
    def test_lista_paginada_com_professor(self):
        resp = self._get("portal_aluno_ocorrencias", self.filho.pk)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["count"], 1)
        item = resp.data["results"][0]
        self.assertEqual(item["id"], self.ocorrencia.pk)
        self.assertEqual(item["professor"], "Carla Professora")
        self.assertNotIn("escola", item)


class ComunicadosTests(_LeiturasSetup):
    def _ids(self, resp):
        return {c["id"] for c in resp.data["results"]}

    def test_so_enviados_que_alcancaram_um_filho(self):
        """Rascunho, falhou, outra turma e outra escola ficam de fora; o
        aviso antigo do filho que saiu continua."""
        resp = self._get("portal_comunicados")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(self._ids(resp), {self.c_escola.pk, self.c_antigo.pk})

    def test_alunos_do_comunicado_sao_so_os_filhos_do_responsavel(self):
        """O comunicado da escola alcançou o filho do Beto também — isso não
        pode aparecer pra Ana."""
        resp = self._get("portal_comunicado", self.c_escola.pk)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["alunos"], [{"id": self.filho.pk, "nome_completo": "Ana Filha"}])

    def test_detalhe_nao_enderecado_da_404(self):
        for c in (self.c_turma2, self.c_rascunho, self.c_falhou, self.c_outra_escola):
            with self.subTest(c.titulo):
                self.assertEqual(self._get("portal_comunicado", c.pk).status_code, 404)

    def test_outro_responsavel_ve_os_dele(self):
        self._entrar(self.beto)
        resp = self._get("portal_comunicados")
        self.assertEqual(self._ids(resp), {self.c_escola.pk, self.c_turma2.pk})


class ConsultasTests(_LeiturasSetup):
    """A listagem não pode fazer uma query por linha."""

    def _queries(self, nome, *args):
        with CaptureQueriesContext(connection) as ctx:
            self.assertEqual(self._get(nome, *args).status_code, 200)
        return len(ctx.captured_queries)

    def test_comunicados_nao_crescem_com_o_numero_de_itens(self):
        antes = self._queries("portal_comunicados")
        for _ in range(5):
            self._comunicado(self.escola, ENVIADO, [self.filho])
        self.assertEqual(self._queries("portal_comunicados"), antes)

    def test_filhos_e_ocorrencias_nao_crescem(self):
        filhos = self._queries("portal_alunos")
        ocorrencias = self._queries("portal_aluno_ocorrencias", self.filho.pk)
        for i in range(3):
            novo = self._aluno(f"Ana Extra {i}", self.turma1)
            ResponsavelAluno.objects.create(responsavel=self.ana, aluno=novo)
            Ocorrencia.objects.create(
                escola=self.escola, turma=self.turma1, aluno=self.filho,
                professor=self.professor, descricao=f"Extra {i}",
            )
        self.assertEqual(self._queries("portal_alunos"), filhos)
        self.assertEqual(self._queries("portal_aluno_ocorrencias", self.filho.pk), ocorrencias)
