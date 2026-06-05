"""Testes das funções de agregação em apps/boletins/services.py."""
from datetime import date, timedelta
from decimal import Decimal

from django.test import TestCase

from apps.avaliacao.models import (
    Avaliacao,
    NotaAvaliacao,
    NotaPeriodo,
    PeriodoAvaliativo,
)
from apps.boletins.services import (
    calcular_frequencia,
    calcular_notas_por_disciplina,
    calcular_ocorrencias,
    listar_avaliacoes_do_aluno,
    montar_boletim,
)
from apps.escola.models import Aluno, Disciplina, Escola, Turma
from apps.ocorrencias.models import Ocorrencia
from apps.presenca.models import ItemPresenca, RegistroPresenca


class _Setup(TestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        cls.escola = Escola.objects.create(nome="Escola")
        cls.turma = Turma.objects.create(
            escola=cls.escola, nome="1º A",
            turno=Turma.Turno.MATUTINO, ano_letivo=2026,
        )
        cls.aluno = Aluno.objects.create(
            escola=cls.escola, matricula="A1",
            nome_completo="Aluno Teste", turma=cls.turma,
        )
        cls.disc_mat = Disciplina.objects.create(escola=cls.escola, nome="Matemática")
        cls.disc_port = Disciplina.objects.create(escola=cls.escola, nome="Português")


class FrequenciaTests(_Setup):
    def _criar_chamada_com_status(self, status_codigo: str, dias_atras: int = 0):
        data_chamada = date.today() - timedelta(days=dias_atras)
        registro = RegistroPresenca.objects.create(
            escola=self.escola, turma=self.turma, data=data_chamada,
        )
        ItemPresenca.objects.create(
            registro=registro, aluno=self.aluno,
            escola=self.escola, status=status_codigo,
        )

    def test_sem_chamadas_zera_tudo(self):
        f = calcular_frequencia(self.aluno)
        self.assertEqual(f["total"], 0)
        self.assertEqual(f["percentual_presenca"], "0.00")

    def test_justificado_conta_como_presenca(self):
        # 1 P + 1 R + 1 J + 1 A = 4 total, 3 efetivas (P, R, J), 75% presença.
        self._criar_chamada_com_status("P", 4)
        self._criar_chamada_com_status("R", 3)
        self._criar_chamada_com_status("J", 2)
        self._criar_chamada_com_status("A", 1)
        f = calcular_frequencia(self.aluno)
        self.assertEqual(f["total"], 4)
        self.assertEqual(f["presentes"], 1)
        self.assertEqual(f["retardatarios"], 1)
        self.assertEqual(f["justificados"], 1)
        self.assertEqual(f["ausentes"], 1)
        self.assertEqual(f["presencas_efetivas"], 3)
        self.assertEqual(f["percentual_presenca"], "75.00")

    def test_filtro_periodo_data_inicio(self):
        self._criar_chamada_com_status("P", 10)
        self._criar_chamada_com_status("A", 1)
        f = calcular_frequencia(
            self.aluno, data_inicio=date.today() - timedelta(days=5)
        )
        # Só a chamada de 1 dia atrás cai no período.
        self.assertEqual(f["total"], 1)
        self.assertEqual(f["ausentes"], 1)


class OcorrenciasTests(_Setup):
    def _criar(self, status: str, dias_atras: int = 0):
        Ocorrencia.objects.create(
            escola=self.escola, turma=self.turma, aluno=self.aluno,
            descricao="x", status=status,
            data_ocorrencia=date.today() - timedelta(days=dias_atras),
        )

    def test_conta_por_status(self):
        self._criar("aberta")
        self._criar("aberta", 1)
        self._criar("resolvida", 2)
        self._criar("arquivada", 3)
        o = calcular_ocorrencias(self.aluno)
        self.assertEqual(o["total"], 4)
        self.assertEqual(o["abertas"], 2)
        self.assertEqual(o["resolvidas"], 1)
        self.assertEqual(o["arquivadas"], 1)

    def test_periodo_restringe(self):
        self._criar("aberta", 10)
        self._criar("resolvida", 1)
        o = calcular_ocorrencias(
            self.aluno, data_inicio=date.today() - timedelta(days=5)
        )
        self.assertEqual(o["total"], 1)
        self.assertEqual(o["resolvidas"], 1)


class NotasPorDisciplinaTests(_Setup):
    """Testes do refator pra `NotaAvaliacao` + `NotaPeriodo`.

    Sistema NÃO calcula média — só agrupa o que o professor lançou.
    """

    @classmethod
    def setUpTestData(cls) -> None:
        super().setUpTestData()
        cls.periodo_1 = PeriodoAvaliativo.objects.create(
            escola=cls.escola,
            nome="1º Bim",
            ordem=1,
            ano_letivo=2026,
            data_inicio=date(2026, 2, 1),
            data_fim=date(2026, 4, 30),
        )

    def _criar_avaliacao(
        self, disciplina, data=None, nota_maxima="10", peso="1"
    ):
        return Avaliacao.objects.create(
            escola=self.escola,
            turma=self.turma,
            disciplina=disciplina,
            titulo="t",
            data=data or date(2026, 3, 15),
            nota_maxima=Decimal(nota_maxima),
            peso=Decimal(peso),
        )

    def _criar_nota(self, avaliacao, valor):
        return NotaAvaliacao.objects.create(
            escola=self.escola,
            avaliacao=avaliacao,
            aluno=self.aluno,
            nota=Decimal(valor),
        )

    def test_agrupa_avaliacoes_por_disciplina_sem_calcular_media(self):
        av1 = self._criar_avaliacao(self.disc_mat, nota_maxima="10", peso="2")
        av2 = self._criar_avaliacao(self.disc_mat, nota_maxima="10", peso="1")
        self._criar_nota(av1, "8")
        self._criar_nota(av2, "5")

        notas = calcular_notas_por_disciplina(self.aluno)
        self.assertEqual(len(notas), 1)
        bucket = notas[0]
        self.assertEqual(bucket["disciplina"]["nome"], "Matemática")
        # **Sem média calculada** — só lista das avaliações com nota.
        self.assertNotIn("media_ponderada", bucket)
        self.assertEqual(len(bucket["avaliacoes"]), 2)
        # Sem NotaPeriodo lançada ainda — lista vazia.
        self.assertEqual(bucket["notas_finais_por_periodo"], [])

    def test_inclui_nota_final_quando_periodo_fechado(self):
        """A média final digitada pelo professor aparece no bucket."""
        av = self._criar_avaliacao(self.disc_mat)
        self._criar_nota(av, "9")
        NotaPeriodo.objects.create(
            escola=self.escola,
            aluno=self.aluno,
            disciplina=self.disc_mat,
            periodo=self.periodo_1,
            nota_final=Decimal("8.50"),
        )

        notas = calcular_notas_por_disciplina(self.aluno)
        self.assertEqual(len(notas), 1)
        finais = notas[0]["notas_finais_por_periodo"]
        self.assertEqual(len(finais), 1)
        self.assertEqual(finais[0]["periodo_nome"], "1º Bim")
        self.assertEqual(finais[0]["nota_final"], "8.50")

    def test_separa_por_disciplina(self):
        av_mat = self._criar_avaliacao(self.disc_mat)
        av_port = self._criar_avaliacao(self.disc_port)
        self._criar_nota(av_mat, "9")
        self._criar_nota(av_port, "6")

        notas = calcular_notas_por_disciplina(self.aluno)
        self.assertEqual(len(notas), 2)
        nomes = [n["disciplina"]["nome"] for n in notas]
        # Ordenado alfabeticamente.
        self.assertEqual(nomes, ["Matemática", "Português"])

    def test_ignora_avaliacoes_sem_nota_lancada(self):
        """NotaAvaliacao com `nota=NULL` (auto-criada vazia) não aparece."""
        av = self._criar_avaliacao(self.disc_mat)
        # Nota auto-criada vazia (sem `nota=`).
        NotaAvaliacao.objects.create(
            escola=self.escola, avaliacao=av, aluno=self.aluno,
        )
        notas = calcular_notas_por_disciplina(self.aluno)
        self.assertEqual(notas, [])

    def test_observacao_nao_vai_no_bucket(self):
        """`NotaPeriodo.observacao` é nota interna do professor — fora do boletim."""
        av = self._criar_avaliacao(self.disc_mat)
        self._criar_nota(av, "7")
        NotaPeriodo.objects.create(
            escola=self.escola,
            aluno=self.aluno,
            disciplina=self.disc_mat,
            periodo=self.periodo_1,
            nota_final=Decimal("7.00"),
            observacao="recuperação simples aplicada",
        )

        notas = calcular_notas_por_disciplina(self.aluno)
        final = notas[0]["notas_finais_por_periodo"][0]
        self.assertNotIn("observacao", final)


class ListarAvaliacoesAlunoTests(_Setup):
    """Testes do helper plano usado pelo export CSV/XLSX."""

    def test_lista_com_e_sem_nota_lancada(self):
        av_com_nota = Avaliacao.objects.create(
            escola=self.escola,
            turma=self.turma,
            disciplina=self.disc_mat,
            titulo="Prova 1",
            data=date(2026, 3, 15),
            nota_maxima=Decimal("10"),
            peso=Decimal("1"),
        )
        av_sem_nota = Avaliacao.objects.create(
            escola=self.escola,
            turma=self.turma,
            disciplina=self.disc_mat,
            titulo="Prova 2",
            data=date(2026, 4, 10),
            nota_maxima=Decimal("10"),
            peso=Decimal("1"),
        )
        NotaAvaliacao.objects.create(
            escola=self.escola,
            avaliacao=av_com_nota,
            aluno=self.aluno,
            nota=Decimal("8.5"),
        )
        # `av_sem_nota` sem NotaAvaliacao do aluno — não aparece.
        NotaAvaliacao.objects.create(
            escola=self.escola, avaliacao=av_sem_nota, aluno=self.aluno,
        )

        linhas = listar_avaliacoes_do_aluno(self.aluno)
        # Inclui as 2 NotaAvaliacao mesmo a segunda estando sem nota.
        self.assertEqual(len(linhas), 2)
        # Linha sem nota vem com nota_obtida = "".
        sem_nota = next(l for l in linhas if l["titulo"] == "Prova 2")
        self.assertEqual(sem_nota["nota_obtida"], "")
        com_nota = next(l for l in linhas if l["titulo"] == "Prova 1")
        # DecimalField com 2 casas serializa "8.50" (não "8.5").
        self.assertEqual(com_nota["nota_obtida"], "8.50")
        # Schema esperado.
        for chave in (
            "disciplina",
            "periodo",
            "data",
            "tipo",
            "titulo",
            "nota_maxima",
            "nota_obtida",
            "peso",
        ):
            self.assertIn(chave, com_nota)


class MontarBoletimTests(_Setup):
    def test_retorna_estrutura_completa(self):
        bol = montar_boletim(self.aluno)
        self.assertIn("aluno", bol)
        self.assertIn("turma", bol)
        self.assertIn("periodo", bol)
        self.assertIn("frequencia", bol)
        self.assertIn("notas_por_disciplina", bol)
        self.assertIn("ocorrencias", bol)
        self.assertEqual(bol["aluno"]["matricula"], "A1")
        self.assertEqual(bol["turma"]["nome"], "1º A")
