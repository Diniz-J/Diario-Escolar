"""Testes do relatório de frequência por turma.

Cobre o que o relatório promete e o que ele não pode fazer: a régua de
presença igual à do boletim, o escopo de escola, a contagem de queries
que não cresce com a turma e os quatro formatos.
"""
from datetime import date

from django.test import TestCase
from django.urls import reverse
from unittest.mock import patch

from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import Usuario
from apps.avaliacao.models import PeriodoAvaliativo
from apps.boletins.services import calcular_frequencia
from apps.escola.models import Aluno, Escola, Turma
from apps.presenca.models import ItemPresenca, RegistroPresenca
from apps.relatorios.services import frequencia_por_turma


def _registrar(turma, dia: date, statuses: dict[Aluno, str]) -> RegistroPresenca:
    """Cria uma chamada da turma no dia, com os status informados.

    A auto-geração dos itens mora no viewset, não no modelo, então aqui
    os itens são explícitos — o que também deixa o teste dizer
    exatamente qual status cada aluno teve.
    """
    registro = RegistroPresenca.objects.create(
        escola=turma.escola, turma=turma, data=dia
    )
    for aluno, status in statuses.items():
        ItemPresenca.objects.create(
            registro=registro, aluno=aluno, status=status
        )
    return registro


class FrequenciaServiceTests(TestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        cls.escola = Escola.objects.create(nome="Escola")
        cls.turma = Turma.objects.create(
            escola=cls.escola,
            nome="1º A",
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

    def test_justificada_e_retardatario_contam_como_presenca(self):
        """Mesma régua do boletim: só `A` derruba a frequência."""
        _registrar(
            self.turma,
            date(2026, 3, 2),
            {self.ana: ItemPresenca.Status.PRESENTE},
        )
        _registrar(
            self.turma,
            date(2026, 3, 3),
            {self.ana: ItemPresenca.Status.JUSTIFICADO},
        )
        _registrar(
            self.turma,
            date(2026, 3, 4),
            {self.ana: ItemPresenca.Status.RETARDATARIO},
        )
        _registrar(
            self.turma,
            date(2026, 3, 5),
            {self.ana: ItemPresenca.Status.AUSENTE},
        )

        linha = self._linha_de(frequencia_por_turma(self.turma), "A1")
        self.assertEqual(linha["total"], 4)
        self.assertEqual(linha["presencas_efetivas"], 3)
        self.assertEqual(linha["ausentes"], 1)
        self.assertEqual(linha["percentual_presenca"], "75.00")

    def test_nao_divergir_do_boletim(self):
        """Trava a régua contra a do boletim.

        Se alguém mudar o cálculo num dos dois lados, este teste acusa —
        é o motivo de o relatório não ter copiado a conta e seguido a
        vida.
        """
        for dia, status in enumerate(
            [
                ItemPresenca.Status.PRESENTE,
                ItemPresenca.Status.AUSENTE,
                ItemPresenca.Status.JUSTIFICADO,
                ItemPresenca.Status.AUSENTE,
                ItemPresenca.Status.RETARDATARIO,
                ItemPresenca.Status.PRESENTE,
                ItemPresenca.Status.AUSENTE,
            ],
            start=2,
        ):
            _registrar(self.turma, date(2026, 3, dia), {self.ana: status})

        do_boletim = calcular_frequencia(self.ana)
        do_relatorio = self._linha_de(frequencia_por_turma(self.turma), "A1")
        for campo in (
            "total",
            "presentes",
            "ausentes",
            "justificados",
            "retardatarios",
            "presencas_efetivas",
            "percentual_presenca",
        ):
            self.assertEqual(
                do_relatorio[campo],
                do_boletim[campo],
                f"divergência no campo {campo}",
            )

    def test_janela_recorta_as_chamadas(self):
        _registrar(
            self.turma,
            date(2026, 2, 10),
            {self.ana: ItemPresenca.Status.AUSENTE},
        )
        _registrar(
            self.turma,
            date(2026, 3, 10),
            {self.ana: ItemPresenca.Status.PRESENTE},
        )

        so_marco = frequencia_por_turma(
            self.turma, date(2026, 3, 1), date(2026, 3, 31)
        )
        linha = self._linha_de(so_marco, "A1")
        self.assertEqual(linha["total"], 1)
        self.assertEqual(linha["percentual_presenca"], "100.00")
        self.assertEqual(so_marco["total_chamadas"], 1)

    def test_abaixo_do_limite_marcado_e_sem_dado_nao(self):
        """Quem tem 50% é alertado; quem não tem chamada, não."""
        _registrar(
            self.turma,
            date(2026, 3, 2),
            {
                self.ana: ItemPresenca.Status.AUSENTE,
                self.bruno: ItemPresenca.Status.PRESENTE,
            },
        )
        _registrar(
            self.turma,
            date(2026, 3, 3),
            {self.ana: ItemPresenca.Status.PRESENTE},
        )
        # Bruno só tem 1 chamada e está 100%; a Ana tem 50%.
        relatorio = frequencia_por_turma(self.turma)
        self.assertTrue(self._linha_de(relatorio, "A1")["abaixo_do_limite"])
        self.assertFalse(self._linha_de(relatorio, "A2")["abaixo_do_limite"])
        self.assertEqual(relatorio["resumo"]["abaixo_do_limite"], 1)

        # Aluno novo, sem nenhuma chamada: 0% mas não é alerta.
        carla = Aluno.objects.create(
            escola=self.escola,
            matricula="A3",
            nome_completo="Carla",
            turma=self.turma,
        )
        relatorio = frequencia_por_turma(self.turma)
        linha = self._linha_de(relatorio, carla.matricula)
        self.assertEqual(linha["total"], 0)
        self.assertEqual(linha["percentual_presenca"], "0.00")
        self.assertFalse(linha["abaixo_do_limite"])
        self.assertEqual(relatorio["resumo"]["abaixo_do_limite"], 1)

    def test_inativo_aparece_so_se_tem_chamada_na_janela(self):
        """Quem estudou parte do período não pode sumir do total."""
        saiu_antes = Aluno.objects.create(
            escola=self.escola,
            matricula="A9",
            nome_completo="Saiu Antes",
            turma=self.turma,
            ativo=False,
        )
        saiu_depois = Aluno.objects.create(
            escola=self.escola,
            matricula="A8",
            nome_completo="Saiu Depois",
            turma=self.turma,
            ativo=False,
        )
        _registrar(
            self.turma,
            date(2026, 3, 2),
            {saiu_depois: ItemPresenca.Status.AUSENTE},
        )

        matriculas = {
            linha["matricula"]
            for linha in frequencia_por_turma(self.turma)["alunos"]
        }
        self.assertIn(saiu_depois.matricula, matriculas)
        self.assertNotIn(saiu_antes.matricula, matriculas)

    def test_percentual_da_turma_e_sobre_o_total_nao_media_de_medias(self):
        """Aluno que entrou no meio do período não distorce o número."""
        # Ana: 2 chamadas, 1 presença (50%). Bruno: 1 chamada, 1 presença
        # (100%). Média das médias daria 75%; a taxa real é 2/3 = 66,67%.
        _registrar(
            self.turma,
            date(2026, 3, 2),
            {
                self.ana: ItemPresenca.Status.AUSENTE,
                self.bruno: ItemPresenca.Status.PRESENTE,
            },
        )
        _registrar(
            self.turma,
            date(2026, 3, 3),
            {self.ana: ItemPresenca.Status.PRESENTE},
        )
        relatorio = frequencia_por_turma(self.turma)
        self.assertEqual(relatorio["resumo"]["percentual_turma"], "66.67")

    def test_contagem_de_queries_nao_cresce_com_a_turma(self):
        """O relatório existe pra turma inteira: tem que ser O(1)."""
        _registrar(
            self.turma,
            date(2026, 3, 2),
            {self.ana: ItemPresenca.Status.PRESENTE},
        )
        with self.assertNumQueries(2):
            frequencia_por_turma(self.turma)

        extras = [
            Aluno.objects.create(
                escola=self.escola,
                matricula=f"X{i}",
                nome_completo=f"Extra {i}",
                turma=self.turma,
            )
            for i in range(12)
        ]
        _registrar(
            self.turma,
            date(2026, 3, 3),
            {aluno: ItemPresenca.Status.AUSENTE for aluno in extras},
        )
        with self.assertNumQueries(2):
            relatorio = frequencia_por_turma(self.turma)
        self.assertEqual(relatorio["resumo"]["total_alunos"], 14)

    def _linha_de(self, relatorio, matricula):
        for linha in relatorio["alunos"]:
            if linha["matricula"] == matricula:
                return linha
        self.fail(f"matrícula {matricula} fora do relatório")


class FrequenciaEndpointTests(TestCase):
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
        cls.periodo_alheio = PeriodoAvaliativo.objects.create(
            escola=cls.outra_escola,
            nome="1º Bimestre",
            ordem=1,
            ano_letivo=2026,
            data_inicio=date(2026, 2, 1),
            data_fim=date(2026, 4, 30),
        )

    def setUp(self) -> None:
        self.client = APIClient()
        _registrar(
            self.turma,
            date(2026, 3, 2),
            {self.aluno: ItemPresenca.Status.PRESENTE},
        )

    def _auth(self, user) -> None:
        token = RefreshToken.for_user(user).access_token
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    @property
    def url(self) -> str:
        return reverse("api_v1:relatorio_frequencia")

    def test_sem_token_401(self):
        self.assertEqual(self.client.get(self.url).status_code, 401)

    def test_turma_obrigatoria(self):
        self._auth(self.diretor)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 400)
        self.assertIn("turma", resp.data)

    def test_formato_invalido(self):
        self._auth(self.diretor)
        resp = self.client.get(
            self.url, {"turma": self.turma.id, "formato": "docx"}
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("formato", resp.data)

    def test_turma_de_outra_escola_404(self):
        """404, não 403: a resposta não confirma que o id existe."""
        self._auth(self.diretor)
        resp = self.client.get(self.url, {"turma": self.turma_alheia.id})
        self.assertEqual(resp.status_code, 404)

    def test_diretor_le_json(self):
        self._auth(self.diretor)
        resp = self.client.get(self.url, {"turma": self.turma.id})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["turma"]["nome"], "2º B")
        self.assertEqual(resp.data["limite_frequencia"], "75.00")
        self.assertEqual(len(resp.data["alunos"]), 1)

    def test_professor_le(self):
        """Quem lança a chamada precisa conferir o resultado dela."""
        self._auth(self.professor)
        resp = self.client.get(self.url, {"turma": self.turma.id})
        self.assertEqual(resp.status_code, 200)

    def test_periodo_de_outra_escola_cai_em_janela_aberta(self):
        """Não vaza nome nem datas de período alheio, nem recorta por ele."""
        self._auth(self.diretor)
        resp = self.client.get(
            self.url,
            {"turma": self.turma.id, "periodo": self.periodo_alheio.id},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIsNone(resp.data["janela"]["data_inicio"])
        self.assertIsNone(resp.data["janela"]["data_fim"])

    def test_data_invalida_400(self):
        self._auth(self.diretor)
        resp = self.client.get(
            self.url, {"turma": self.turma.id, "data_inicio": "02-03-2026"}
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("data_inicio", resp.data)

    def test_csv_tem_cabecalho_e_uma_linha_por_aluno(self):
        self._auth(self.diretor)
        resp = self.client.get(
            self.url, {"turma": self.turma.id, "formato": "csv"}
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp["Content-Type"], "text/csv")
        self.assertIn("frequencia_2o_b.csv", resp["Content-Disposition"])
        linhas = resp.content.decode("utf-8").strip().splitlines()
        self.assertEqual(len(linhas), 2)
        self.assertIn("matricula", linhas[0])
        self.assertIn("M1", linhas[1])

    def test_xlsx_sai_como_planilha(self):
        self._auth(self.diretor)
        resp = self.client.get(
            self.url, {"turma": self.turma.id, "formato": "xlsx"}
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn("spreadsheetml", resp["Content-Type"])
        self.assertIn("frequencia_2o_b.xlsx", resp["Content-Disposition"])

    @patch("apps.relatorios.views._render_pdf", return_value=b"%PDF-1.4 fake")
    def test_pdf_renderiza_o_template(self, render_mock):
        """O WeasyPrint é mockado, mas o template roda de verdade."""
        self._auth(self.diretor)
        resp = self.client.get(
            self.url, {"turma": self.turma.id, "formato": "pdf"}
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp["Content-Type"], "application/pdf")
        self.assertIn("frequencia_2o_b.pdf", resp["Content-Disposition"])
        html = render_mock.call_args[0][0]
        self.assertIn("Relatório de Frequência", html)
        self.assertIn("Ana", html)
        self.assertIn("Todo o período registrado", html)
        # Sintaxe de template que sobrou vira texto visível no PDF — foi
        # o que aconteceu com um `{# #}` de três linhas (comentário de
        # uma linha só), impresso no topo da página.
        self.assertNotIn("{#", html)
        self.assertNotIn("{%", html)
