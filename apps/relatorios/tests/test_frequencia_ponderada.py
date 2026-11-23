"""A frequência pesa TEMPOS de aula, não chamadas (`PRESENCA.md`).

Estes testes existem porque a suíte antiga não os distinguia: até
nov/2026 toda chamada valia 1, então contar itens e somar tempos davam o
mesmo número e qualquer um dos dois passaria. Todo caso aqui usa bloco de
tamanho **diferente de 1** — é a única forma de a asserção falhar se
alguém voltar a contar chamadas.

Cobre as três pontas juntas de propósito: boletim, relatório por turma e
dashboard leem a mesma régua, e o risco real não é uma delas errar, é
elas se afastarem.
"""
from datetime import date

from django.test import TestCase

from apps.boletins.services import calcular_frequencia
from apps.escola.models import Aluno, Escola, Turma
from apps.presenca.models import ItemPresenca, RegistroPresenca
from apps.relatorios.services import frequencia_por_turma, metricas_dashboard


def _chamada(turma, dia: date, tempos: list[int], statuses: dict) -> RegistroPresenca:
    registro = RegistroPresenca.objects.create(
        escola=turma.escola, turma=turma, data=dia, tempos=tempos
    )
    for aluno, status in statuses.items():
        ItemPresenca.objects.create(registro=registro, aluno=aluno, status=status)
    return registro


class FrequenciaPonderadaTests(TestCase):
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
            escola=cls.escola, matricula="A1", nome_completo="Ana", turma=cls.turma
        )

    def test_bloco_de_dois_tempos_conta_dois(self):
        _chamada(
            self.turma,
            date(2026, 3, 2),
            [1, 2],
            {self.ana: ItemPresenca.Status.PRESENTE},
        )
        frequencia = calcular_frequencia(self.ana)
        self.assertEqual(frequencia["total"], 2)
        self.assertEqual(frequencia["presentes"], 2)
        self.assertEqual(frequencia["presencas_efetivas"], 2)

    def test_falta_em_bloco_duplo_custa_dois_tempos(self):
        """É a razão de ser da mudança: faltar num bloco duplo é 2 faltas."""
        _chamada(
            self.turma,
            date(2026, 3, 2),
            [1, 2],
            {self.ana: ItemPresenca.Status.AUSENTE},
        )
        _chamada(
            self.turma,
            date(2026, 3, 3),
            [1, 2],
            {self.ana: ItemPresenca.Status.PRESENTE},
        )
        frequencia = calcular_frequencia(self.ana)
        self.assertEqual(frequencia["total"], 4)
        self.assertEqual(frequencia["ausentes"], 2)
        self.assertEqual(frequencia["percentual_presenca"], "50.00")

    def test_blocos_de_tamanhos_diferentes_somam_carga_horaria(self):
        """Quatro tempos previstos em duas chamadas, uma falta de um tempo."""
        _chamada(
            self.turma,
            date(2026, 3, 2),
            [1, 2, 3],
            {self.ana: ItemPresenca.Status.PRESENTE},
        )
        _chamada(
            self.turma,
            date(2026, 3, 3),
            [1],
            {self.ana: ItemPresenca.Status.AUSENTE},
        )
        frequencia = calcular_frequencia(self.ana)
        self.assertEqual(frequencia["total"], 4)
        self.assertEqual(frequencia["presencas_efetivas"], 3)
        self.assertEqual(frequencia["percentual_presenca"], "75.00")

    def test_relatorio_por_turma_pesa_igual_ao_boletim(self):
        """Trava a não-divergência com bloco != 1, que é o caso novo."""
        _chamada(
            self.turma,
            date(2026, 3, 2),
            [1, 2, 3],
            {self.ana: ItemPresenca.Status.PRESENTE},
        )
        _chamada(
            self.turma,
            date(2026, 3, 3),
            [1, 2],
            {self.ana: ItemPresenca.Status.AUSENTE},
        )

        do_boletim = calcular_frequencia(self.ana)
        linha = next(
            item
            for item in frequencia_por_turma(self.turma)["alunos"]
            if item["aluno_id"] == self.ana.pk
        )
        for campo in (
            "total",
            "presentes",
            "ausentes",
            "justificados",
            "retardatarios",
            "presencas_efetivas",
            "percentual_presenca",
        ):
            self.assertEqual(linha[campo], do_boletim[campo], campo)

    def test_relatorio_separa_chamadas_de_tempos(self):
        """"3 aulas perdidas" e "1 dia de falta" são números diferentes."""
        _chamada(
            self.turma,
            date(2026, 3, 2),
            [1, 2, 3],
            {self.ana: ItemPresenca.Status.AUSENTE},
        )
        linha = frequencia_por_turma(self.turma)["alunos"][0]
        self.assertEqual(linha["total_chamadas_aluno"], 1)
        self.assertEqual(linha["total"], 3)
        self.assertEqual(linha["ausentes"], 3)

    def test_relatorio_pesado_segue_em_uma_query(self):
        """O `Sum` com `array_length` não pode virar query por aluno.

        É a razão de o peso sair de um lookup do `ArrayField` em vez de
        ser resolvido em Python: o relatório existe pra turma inteira.
        """
        for indice in range(5):
            Aluno.objects.create(
                escola=self.escola,
                matricula=f"M{indice}",
                nome_completo=f"Aluno {indice}",
                turma=self.turma,
            )
        _chamada(
            self.turma,
            date(2026, 3, 2),
            [1, 2],
            {
                aluno: ItemPresenca.Status.PRESENTE
                for aluno in Aluno.objects.filter(turma=self.turma)
            },
        )
        # 2 queries fixas, independentes do tamanho da turma: a lista
        # anotada (a subquery de quem tem chamada aqui entra inline, no
        # `pk__in`) e o total de chamadas da turma.
        with self.assertNumQueries(2):
            frequencia_por_turma(self.turma)

    def test_dashboard_pesa_tempos(self):
        """A mesma régua no card — terceira ponta da não-divergência."""
        hoje = date.today()
        _chamada(self.turma, hoje, [1, 2], {self.ana: ItemPresenca.Status.AUSENTE})

        metricas = metricas_dashboard(self.escola.pk)
        self.assertEqual(metricas["presenca"]["total_itens"], 2)
        self.assertEqual(metricas["presenca"]["presencas_efetivas"], 0)
        self.assertEqual(metricas["presenca"]["percentual_medio"], "0.00")
        # Uma chamada, dois tempos: o card distingue as duas unidades.
        self.assertEqual(metricas["presenca"]["total_chamadas"], 1)
