"""Testes das métricas do dashboard (presença média e reincidência).

Cobre o que as duas métricas prometem e o que elas não podem fazer: a
régua de presença herdada do relatório de frequência, a janela recente
que não deixa o mês passado pesar, o escopo de escola, o recorte por
turma do remanejado e a contagem de queries, que não cresce com a base.
"""
from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import Usuario
from apps.escola.models import Aluno, Escola, Turma
from apps.ocorrencias.models import Ocorrencia
from apps.presenca.models import ItemPresenca, RegistroPresenca
from apps.relatorios.services import (
    JANELA_DASHBOARD_DIAS,
    LIMIAR_REINCIDENCIA,
    metricas_dashboard,
)

HOJE = timezone.localdate()
# Fora da janela por folga larga, pra o teste não virar flaky na virada
# do mês nem depender do tamanho exato de `JANELA_DASHBOARD_DIAS`.
ANTIGO = HOJE - timedelta(days=JANELA_DASHBOARD_DIAS + 30)


def _registrar(turma, dia, statuses: dict) -> RegistroPresenca:
    """Chamada da turma no dia, com os status informados.

    Itens explícitos: a auto-geração mora no viewset, e aqui o teste
    precisa dizer qual status cada aluno teve.
    """
    registro = RegistroPresenca.objects.create(
        escola=turma.escola, turma=turma, data=dia
    )
    for aluno, status in statuses.items():
        ItemPresenca.objects.create(
            registro=registro, aluno=aluno, status=status
        )
    return registro


def _ocorrer(aluno, dia, quantas: int = 1) -> None:
    for i in range(quantas):
        Ocorrencia.objects.create(
            escola=aluno.escola,
            turma=aluno.turma,
            aluno=aluno,
            descricao=f"evento {i}",
            data_ocorrencia=dia,
        )


class MetricasDashboardServiceTests(TestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        cls.escola = Escola.objects.create(nome="Escola")
        cls.outra_escola = Escola.objects.create(nome="Outra")
        cls.turma = Turma.objects.create(
            escola=cls.escola,
            nome="1º A",
            turno=Turma.Turno.MATUTINO,
            ano_letivo=2026,
        )
        cls.turma_b = Turma.objects.create(
            escola=cls.escola,
            nome="1º B",
            turno=Turma.Turno.MATUTINO,
            ano_letivo=2026,
        )
        cls.ana = Aluno.objects.create(
            escola=cls.escola,
            matricula="A1",
            nome_completo="Ana",
            turma=cls.turma,
        )
        cls.bruno = Aluno.objects.create(
            escola=cls.escola,
            matricula="A2",
            nome_completo="Bruno",
            turma=cls.turma,
        )

    def test_presenca_media_usa_a_regua_do_relatorio(self):
        """P, R e J contam como presença efetiva; só A derruba."""
        _registrar(
            self.turma,
            HOJE,
            {
                self.ana: ItemPresenca.Status.PRESENTE,
                self.bruno: ItemPresenca.Status.JUSTIFICADO,
            },
        )
        _registrar(
            self.turma,
            HOJE - timedelta(days=1),
            {
                self.ana: ItemPresenca.Status.RETARDATARIO,
                self.bruno: ItemPresenca.Status.AUSENTE,
            },
        )

        presenca = metricas_dashboard(self.escola.pk)["presenca"]
        self.assertEqual(presenca["total_itens"], 4)
        self.assertEqual(presenca["presencas_efetivas"], 3)
        self.assertEqual(presenca["percentual_medio"], "75.00")
        self.assertEqual(presenca["total_chamadas"], 2)

    def test_abaixo_do_limite_marca_so_quando_fura_a_ldb(self):
        _registrar(
            self.turma,
            HOJE,
            {
                self.ana: ItemPresenca.Status.AUSENTE,
                self.bruno: ItemPresenca.Status.AUSENTE,
            },
        )
        _registrar(
            self.turma,
            HOJE - timedelta(days=1),
            {
                self.ana: ItemPresenca.Status.PRESENTE,
                self.bruno: ItemPresenca.Status.AUSENTE,
            },
        )

        presenca = metricas_dashboard(self.escola.pk)["presenca"]
        self.assertEqual(presenca["percentual_medio"], "25.00")
        self.assertTrue(presenca["abaixo_do_limite"])
        self.assertEqual(presenca["limite_frequencia"], "75.00")

    def test_sem_chamada_nao_acusa_infrequencia(self):
        """0% sem dado é 'não houve chamada', não 'ninguém veio'.

        O card precisa dessa distinção: marcar `abaixo_do_limite` numa
        escola que só não fez chamada mandaria a direção atrás de um
        problema inexistente.
        """
        metricas = metricas_dashboard(self.escola.pk)
        self.assertEqual(metricas["presenca"]["percentual_medio"], "0.00")
        self.assertEqual(metricas["presenca"]["total_itens"], 0)
        self.assertEqual(metricas["presenca"]["total_chamadas"], 0)
        self.assertFalse(metricas["presenca"]["abaixo_do_limite"])

    def test_janela_ignora_o_que_ficou_para_tras(self):
        """A chamada e a ocorrência antigas não entram no recorte."""
        _registrar(
            self.turma, ANTIGO, {self.ana: ItemPresenca.Status.AUSENTE}
        )
        _ocorrer(self.ana, ANTIGO, quantas=3)

        metricas = metricas_dashboard(self.escola.pk)
        self.assertEqual(metricas["presenca"]["total_itens"], 0)
        self.assertEqual(metricas["reincidencia"]["total_ocorrencias"], 0)
        self.assertEqual(metricas["reincidencia"]["alunos_reincidentes"], 0)

    def test_janela_devolve_as_pontas_do_recorte(self):
        janela = metricas_dashboard(self.escola.pk)["janela"]
        self.assertEqual(janela["dias"], JANELA_DASHBOARD_DIAS)
        self.assertEqual(janela["data_fim"], HOJE.isoformat())
        # `dias - 1`: as duas pontas são inclusivas, então 30 dias
        # cobrem 30 datas contando hoje.
        self.assertEqual(
            janela["data_inicio"],
            (HOJE - timedelta(days=JANELA_DASHBOARD_DIAS - 1)).isoformat(),
        )

    def test_reincidente_e_quem_repete_na_janela(self):
        _ocorrer(self.ana, HOJE, quantas=LIMIAR_REINCIDENCIA)
        _ocorrer(self.bruno, HOJE, quantas=1)

        reincidencia = metricas_dashboard(self.escola.pk)["reincidencia"]
        self.assertEqual(reincidencia["limiar"], LIMIAR_REINCIDENCIA)
        self.assertEqual(reincidencia["alunos_reincidentes"], 1)
        self.assertEqual(reincidencia["alunos_com_ocorrencia"], 2)
        self.assertEqual(
            reincidencia["total_ocorrencias"], LIMIAR_REINCIDENCIA + 1
        )

    def test_escopo_de_escola(self):
        """Dado de outra escola não entra em nenhuma das duas métricas."""
        turma_alheia = Turma.objects.create(
            escola=self.outra_escola,
            nome="1º A",
            turno=Turma.Turno.MATUTINO,
            ano_letivo=2026,
        )
        aluno_alheio = Aluno.objects.create(
            escola=self.outra_escola,
            matricula="X1",
            nome_completo="Alheio",
            turma=turma_alheia,
        )
        _registrar(
            turma_alheia, HOJE, {aluno_alheio: ItemPresenca.Status.AUSENTE}
        )
        _ocorrer(aluno_alheio, HOJE, quantas=3)
        _registrar(self.turma, HOJE, {self.ana: ItemPresenca.Status.PRESENTE})

        metricas = metricas_dashboard(self.escola.pk)
        self.assertEqual(metricas["presenca"]["total_itens"], 1)
        self.assertEqual(metricas["presenca"]["percentual_medio"], "100.00")
        self.assertEqual(metricas["reincidencia"]["alunos_com_ocorrencia"], 0)

    def test_escola_none_agrega_todas(self):
        """Admin global não tem escola e enxerga a base inteira."""
        turma_alheia = Turma.objects.create(
            escola=self.outra_escola,
            nome="1º A",
            turno=Turma.Turno.MATUTINO,
            ano_letivo=2026,
        )
        aluno_alheio = Aluno.objects.create(
            escola=self.outra_escola,
            matricula="X1",
            nome_completo="Alheio",
            turma=turma_alheia,
        )
        _registrar(
            turma_alheia, HOJE, {aluno_alheio: ItemPresenca.Status.PRESENTE}
        )
        _registrar(self.turma, HOJE, {self.ana: ItemPresenca.Status.AUSENTE})

        metricas = metricas_dashboard(None)
        self.assertEqual(metricas["presenca"]["total_itens"], 2)
        self.assertEqual(metricas["presenca"]["percentual_medio"], "50.00")

    def test_turma_recorta_pelo_registro_nao_pela_turma_atual(self):
        """Remanejado não leva pra turma nova as faltas da antiga.

        Mesma decisão de `frequencia_por_turma`: o filtro é a turma do
        registro de chamada e da ocorrência, não a turma onde o aluno
        está hoje.
        """
        _registrar(self.turma, HOJE, {self.ana: ItemPresenca.Status.AUSENTE})
        _ocorrer(self.ana, HOJE, quantas=2)
        # Ana é remanejada pra B depois dos eventos acima.
        self.ana.turma = self.turma_b
        self.ana.save(update_fields=["turma"])

        na_antiga = metricas_dashboard(self.escola.pk, self.turma)
        self.assertEqual(na_antiga["presenca"]["total_itens"], 1)
        self.assertEqual(na_antiga["reincidencia"]["alunos_reincidentes"], 1)
        self.assertEqual(na_antiga["turma_id"], self.turma.pk)

        na_nova = metricas_dashboard(self.escola.pk, self.turma_b)
        self.assertEqual(na_nova["presenca"]["total_itens"], 0)
        self.assertEqual(na_nova["reincidencia"]["alunos_reincidentes"], 0)

    def test_contagem_de_queries_nao_cresce_com_a_base(self):
        """Três queries fixas: presença, chamadas e ocorrências por aluno.

        É o motivo de as métricas serem agregado no banco e não derivação
        no front, que é como as outras do dashboard nasceram.
        """
        extras = [
            Aluno.objects.create(
                escola=self.escola,
                matricula=f"E{i}",
                nome_completo=f"Extra {i}",
                turma=self.turma,
            )
            for i in range(12)
        ]
        _registrar(
            self.turma,
            HOJE,
            {aluno: ItemPresenca.Status.AUSENTE for aluno in extras},
        )
        for aluno in extras:
            _ocorrer(aluno, HOJE, quantas=2)

        with self.assertNumQueries(3):
            metricas_dashboard(self.escola.pk)


class MetricasDashboardEndpointTests(TestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        cls.escola = Escola.objects.create(nome="Escola")
        cls.outra_escola = Escola.objects.create(nome="Outra")
        cls.turma = Turma.objects.create(
            escola=cls.escola,
            nome="2º B",
            turno=Turma.Turno.MATUTINO,
            ano_letivo=2026,
        )
        cls.turma_alheia = Turma.objects.create(
            escola=cls.outra_escola,
            nome="2º B",
            turno=Turma.Turno.MATUTINO,
            ano_letivo=2026,
        )
        cls.aluno = Aluno.objects.create(
            escola=cls.escola,
            matricula="M1",
            nome_completo="Ana",
            turma=cls.turma,
        )
        cls.diretor = Usuario.objects.create_user(
            username="dir",
            password="x",
            perfil=Usuario.Perfil.DIRETOR,
            escola=cls.escola,
        )
        cls.professor = Usuario.objects.create_user(
            username="prof",
            password="x",
            perfil=Usuario.Perfil.PROFESSOR,
            escola=cls.escola,
        )
        cls.sem_escola = Usuario.objects.create_user(
            username="orfao",
            password="x",
            perfil=Usuario.Perfil.DIRETOR,
        )
        cls.admin = Usuario.objects.create_user(
            username="adm", password="x", perfil=Usuario.Perfil.ADMIN
        )

    def setUp(self) -> None:
        self.client = APIClient()
        _registrar(
            self.turma, HOJE, {self.aluno: ItemPresenca.Status.PRESENTE}
        )

    def _auth(self, user) -> None:
        token = RefreshToken.for_user(user).access_token
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    @property
    def url(self) -> str:
        return reverse("api_v1:relatorio_dashboard")

    def test_sem_token_401(self):
        self.assertEqual(self.client.get(self.url).status_code, 401)

    def test_diretor_le_sem_turma(self):
        """Turma é opcional aqui: 'todas as turmas' é o default da tela."""
        self._auth(self.diretor)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        self.assertIsNone(resp.data["turma_id"])
        self.assertEqual(resp.data["presenca"]["percentual_medio"], "100.00")

    def test_filtro_por_turma(self):
        self._auth(self.diretor)
        resp = self.client.get(self.url, {"turma": self.turma.id})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["turma_id"], self.turma.id)

    def test_turma_de_outra_escola_404(self):
        """404, não 403: a resposta não confirma que o id existe."""
        self._auth(self.diretor)
        resp = self.client.get(self.url, {"turma": self.turma_alheia.id})
        self.assertEqual(resp.status_code, 404)

    def test_professor_le(self):
        """Agregado sem nome de aluno: quem lança a chamada pode ver."""
        self._auth(self.professor)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)

    def test_usuario_sem_escola_recebe_zerado(self):
        """Zerado em vez de erro: um 4xx aqui derrubaria o dashboard."""
        self._auth(self.sem_escola)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["presenca"]["total_itens"], 0)
        self.assertEqual(resp.data["reincidencia"]["alunos_com_ocorrencia"], 0)

    def test_admin_global_ve_todas_as_escolas(self):
        self._auth(self.admin)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["presenca"]["total_itens"], 1)
