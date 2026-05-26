"""Testes das funções de agregação em apps/boletins/services.py."""
from datetime import date, timedelta
from decimal import Decimal

from django.test import TestCase

from apps.boletins.services import (
    calcular_frequencia,
    calcular_notas_por_disciplina,
    calcular_ocorrencias,
    montar_boletim,
)
from apps.escola.models import Aluno, Disciplina, Escola, Turma
from apps.ocorrencias.models import Ocorrencia
from apps.presenca.models import ItemPresenca, RegistroPresenca
from apps.tarefas.models import EntregaTarefa, Tarefa


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
    def _criar_tarefa(self, disciplina, nota_maxima, peso="1"):
        return Tarefa.objects.create(
            escola=self.escola, turma=self.turma,
            disciplina=disciplina, titulo="t",
            vale_nota=True, nota_maxima=Decimal(nota_maxima),
            peso=Decimal(peso),
        )

    def _criar_entrega(self, tarefa, nota):
        return EntregaTarefa.objects.create(
            tarefa=tarefa, aluno=self.aluno, escola=self.escola,
            entregue=True, data_entrega=date.today(),
            nota=Decimal(nota),
        )

    def test_media_ponderada_simples(self):
        t1 = self._criar_tarefa(self.disc_mat, "10", peso="2")
        t2 = self._criar_tarefa(self.disc_mat, "10", peso="1")
        self._criar_entrega(t1, "8")  # 8 × 2 = 16
        self._criar_entrega(t2, "5")  # 5 × 1 = 5
        # (16 + 5) / (2 + 1) = 21 / 3 = 7
        notas = calcular_notas_por_disciplina(self.aluno)
        self.assertEqual(len(notas), 1)
        self.assertEqual(notas[0]["disciplina"]["nome"], "Matemática")
        self.assertEqual(notas[0]["media_ponderada"], "7.00")
        self.assertEqual(len(notas[0]["tarefas"]), 2)

    def test_separa_por_disciplina(self):
        t_mat = self._criar_tarefa(self.disc_mat, "10")
        t_port = self._criar_tarefa(self.disc_port, "10")
        self._criar_entrega(t_mat, "9")
        self._criar_entrega(t_port, "6")
        notas = calcular_notas_por_disciplina(self.aluno)
        self.assertEqual(len(notas), 2)
        nomes = [n["disciplina"]["nome"] for n in notas]
        # Ordenado alfabeticamente.
        self.assertEqual(nomes, ["Matemática", "Português"])

    def test_ignora_tarefas_sem_nota(self):
        t = self._criar_tarefa(self.disc_mat, "10")
        # Entrega criada automaticamente (sem nota).
        EntregaTarefa.objects.create(
            tarefa=t, aluno=self.aluno, escola=self.escola,
        )
        notas = calcular_notas_por_disciplina(self.aluno)
        self.assertEqual(notas, [])

    def test_ignora_tarefas_que_nao_valem_nota(self):
        # `vale_nota=False` — não entra mesmo com nota presente.
        t = Tarefa.objects.create(
            escola=self.escola, turma=self.turma,
            disciplina=self.disc_mat, titulo="t",
            vale_nota=False,
        )
        # `clean()` rejeitaria, mas pulamos via .objects.create sem clean.
        EntregaTarefa.objects.create(
            tarefa=t, aluno=self.aluno, escola=self.escola,
        )
        notas = calcular_notas_por_disciplina(self.aluno)
        self.assertEqual(notas, [])


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
