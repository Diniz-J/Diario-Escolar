"""Testes dos modelos `Tarefa` e `EntregaTarefa`."""
from datetime import date, timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from apps.accounts.models import Usuario
from apps.escola.models import Aluno, Disciplina, Escola, Professor, Turma
from apps.tarefas.models import EntregaTarefa, Tarefa


class _BaseSetup(TestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        cls.escola_a = Escola.objects.create(nome="Escola A")
        cls.escola_b = Escola.objects.create(nome="Escola B")
        cls.turma_a = Turma.objects.create(
            escola=cls.escola_a, nome="1º A",
            turno=Turma.Turno.MATUTINO, ano_letivo=2026,
        )
        cls.turma_b = Turma.objects.create(
            escola=cls.escola_b, nome="1º A",
            turno=Turma.Turno.MATUTINO, ano_letivo=2026,
        )
        cls.disc_a = Disciplina.objects.create(escola=cls.escola_a, nome="Mat")
        cls.disc_b = Disciplina.objects.create(escola=cls.escola_b, nome="Mat")
        cls.aluno_a = Aluno.objects.create(
            escola=cls.escola_a, matricula="A1",
            nome_completo="Aluno A", turma=cls.turma_a,
        )
        cls.aluno_b = Aluno.objects.create(
            escola=cls.escola_b, matricula="B1",
            nome_completo="Aluno B", turma=cls.turma_b,
        )


class TarefaCleanTests(_BaseSetup):
    def test_caminho_feliz(self):
        t = Tarefa(
            escola=self.escola_a, turma=self.turma_a,
            disciplina=self.disc_a, titulo="Lista 1",
        )
        t.full_clean()

    def test_turma_de_outra_escola(self):
        t = Tarefa(
            escola=self.escola_a, turma=self.turma_b,
            disciplina=self.disc_a, titulo="x",
        )
        with self.assertRaises(ValidationError) as ctx:
            t.full_clean()
        self.assertIn("turma", ctx.exception.message_dict)

    def test_disciplina_de_outra_escola(self):
        t = Tarefa(
            escola=self.escola_a, turma=self.turma_a,
            disciplina=self.disc_b, titulo="x",
        )
        with self.assertRaises(ValidationError) as ctx:
            t.full_clean()
        self.assertIn("disciplina", ctx.exception.message_dict)

    def test_prazo_anterior_ao_lancamento(self):
        t = Tarefa(
            escola=self.escola_a, turma=self.turma_a,
            disciplina=self.disc_a, titulo="x",
            data_lancamento=date.today(),
            prazo=date.today() - timedelta(days=1),
        )
        with self.assertRaises(ValidationError) as ctx:
            t.full_clean()
        self.assertIn("prazo", ctx.exception.message_dict)

    def test_vale_nota_sem_nota_maxima(self):
        t = Tarefa(
            escola=self.escola_a, turma=self.turma_a,
            disciplina=self.disc_a, titulo="x",
            vale_nota=True,
        )
        with self.assertRaises(ValidationError) as ctx:
            t.full_clean()
        self.assertIn("nota_maxima", ctx.exception.message_dict)

    def test_prazo_opcional(self):
        t = Tarefa(
            escola=self.escola_a, turma=self.turma_a,
            disciplina=self.disc_a, titulo="x",
        )
        t.full_clean()  # prazo = None é OK


class EntregaTarefaTests(_BaseSetup):
    def setUp(self) -> None:
        self.tarefa = Tarefa.objects.create(
            escola=self.escola_a, turma=self.turma_a,
            disciplina=self.disc_a, titulo="Lista 1",
        )

    def test_save_sincroniza_escola_com_tarefa(self):
        entrega = EntregaTarefa(
            tarefa=self.tarefa, aluno=self.aluno_a,
            escola=self.escola_b,  # divergente — deve ser sobrescrito
        )
        entrega.save()
        entrega.refresh_from_db()
        self.assertEqual(entrega.escola_id, self.escola_a.id)

    def test_aluno_de_outra_turma(self):
        outra_turma = Turma.objects.create(
            escola=self.escola_a, nome="2º A",
            turno=Turma.Turno.MATUTINO, ano_letivo=2026,
        )
        outro_aluno = Aluno.objects.create(
            escola=self.escola_a, matricula="A2",
            nome_completo="X", turma=outra_turma,
        )
        e = EntregaTarefa(
            tarefa=self.tarefa, aluno=outro_aluno, escola=self.escola_a,
        )
        with self.assertRaises(ValidationError) as ctx:
            e.full_clean()
        self.assertIn("aluno", ctx.exception.message_dict)

    def test_unique_por_tarefa_aluno(self):
        EntregaTarefa.objects.create(
            tarefa=self.tarefa, aluno=self.aluno_a, escola=self.escola_a,
        )
        with self.assertRaises(IntegrityError), transaction.atomic():
            EntregaTarefa.objects.create(
                tarefa=self.tarefa, aluno=self.aluno_a, escola=self.escola_a,
            )

    def test_cascade_delete_remove_entregas(self):
        EntregaTarefa.objects.create(
            tarefa=self.tarefa, aluno=self.aluno_a, escola=self.escola_a,
        )
        self.assertEqual(EntregaTarefa.objects.count(), 1)
        self.tarefa.delete()
        self.assertEqual(EntregaTarefa.objects.count(), 0)


class StatusComputadoTests(_BaseSetup):
    """Testa o `@property status` em diferentes combinações."""

    def setUp(self) -> None:
        self.hoje = date.today()
        self.amanha = self.hoje + timedelta(days=1)
        self.ontem = self.hoje - timedelta(days=1)

    def _entrega(self, prazo, entregue, data_entrega=None):
        tarefa = Tarefa.objects.create(
            escola=self.escola_a, turma=self.turma_a,
            disciplina=self.disc_a, titulo="x", prazo=prazo,
        )
        return EntregaTarefa.objects.create(
            tarefa=tarefa, aluno=self.aluno_a, escola=self.escola_a,
            entregue=entregue, data_entrega=data_entrega,
        )

    def test_pendente_sem_prazo(self):
        self.assertEqual(
            self._entrega(prazo=None, entregue=False).status, "pendente"
        )

    def test_pendente_dentro_do_prazo(self):
        self.assertEqual(
            self._entrega(prazo=self.amanha, entregue=False).status, "pendente"
        )

    def test_atrasada_prazo_vencido_nao_entregue(self):
        self.assertEqual(
            self._entrega(prazo=self.ontem, entregue=False).status, "atrasada"
        )

    def test_entregue_no_prazo(self):
        self.assertEqual(
            self._entrega(
                prazo=self.amanha, entregue=True, data_entrega=self.hoje
            ).status,
            "entregue_no_prazo",
        )

    def test_entregue_sem_prazo_definido(self):
        self.assertEqual(
            self._entrega(
                prazo=None, entregue=True, data_entrega=self.hoje
            ).status,
            "entregue_no_prazo",
        )

    def test_entregue_com_atraso(self):
        self.assertEqual(
            self._entrega(
                prazo=self.ontem, entregue=True, data_entrega=self.hoje
            ).status,
            "entregue_com_atraso",
        )


class NotaTests(_BaseSetup):
    def test_nota_acima_da_maxima_falha(self):
        tarefa = Tarefa.objects.create(
            escola=self.escola_a, turma=self.turma_a,
            disciplina=self.disc_a, titulo="x",
            vale_nota=True, nota_maxima=Decimal("10.00"),
        )
        e = EntregaTarefa(
            tarefa=tarefa, aluno=self.aluno_a, escola=self.escola_a,
            entregue=True, data_entrega=date.today(),
            nota=Decimal("11.00"),
        )
        with self.assertRaises(ValidationError) as ctx:
            e.full_clean()
        self.assertIn("nota", ctx.exception.message_dict)

    def test_nota_em_tarefa_sem_nota_falha(self):
        tarefa = Tarefa.objects.create(
            escola=self.escola_a, turma=self.turma_a,
            disciplina=self.disc_a, titulo="x",
        )
        e = EntregaTarefa(
            tarefa=tarefa, aluno=self.aluno_a, escola=self.escola_a,
            entregue=True, data_entrega=date.today(),
            nota=Decimal("5.00"),
        )
        with self.assertRaises(ValidationError) as ctx:
            e.full_clean()
        self.assertIn("nota", ctx.exception.message_dict)
