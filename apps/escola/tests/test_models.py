"""Testes dos modelos da app escola — constraints e invariantes."""
from datetime import date

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from apps.escola.models import Aluno, Disciplina, Escola, Turma


class _BaseEscolaSetup(TestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        cls.escola_a = Escola.objects.create(nome="Escola A")
        cls.escola_b = Escola.objects.create(nome="Escola B")
        cls.turma_a = Turma.objects.create(
            escola=cls.escola_a,
            nome="1º Ano A",
            turno=Turma.Turno.MATUTINO,
            ano_letivo=2026,
        )
        cls.turma_b = Turma.objects.create(
            escola=cls.escola_b,
            nome="1º Ano A",
            turno=Turma.Turno.MATUTINO,
            ano_letivo=2026,
        )


class TurmaConstraintTests(_BaseEscolaSetup):
    def test_turma_unica_por_escola_nome_ano(self):
        """Mesma escola+nome+ano não pode duplicar."""
        with self.assertRaises(IntegrityError), transaction.atomic():
            Turma.objects.create(
                escola=self.escola_a,
                nome="1º Ano A",
                turno=Turma.Turno.VESPERTINO,
                ano_letivo=2026,
            )

    def test_turma_mesmo_nome_em_escolas_diferentes_ok(self):
        """Mesma nomenclatura em escolas diferentes é permitida."""
        # já criado no setUp: escola_a e escola_b ambas têm "1º Ano A" 2026
        self.assertEqual(Turma.objects.filter(nome="1º Ano A", ano_letivo=2026).count(), 2)

    def test_turma_mesmo_nome_em_anos_diferentes_ok(self):
        Turma.objects.create(
            escola=self.escola_a,
            nome="1º Ano A",
            turno=Turma.Turno.MATUTINO,
            ano_letivo=2027,
        )
        self.assertEqual(
            Turma.objects.filter(escola=self.escola_a, nome="1º Ano A").count(), 2
        )


class DisciplinaConstraintTests(_BaseEscolaSetup):
    def test_disciplina_unica_por_escola(self):
        Disciplina.objects.create(escola=self.escola_a, nome="Matemática")
        with self.assertRaises(IntegrityError), transaction.atomic():
            Disciplina.objects.create(escola=self.escola_a, nome="Matemática")

    def test_mesma_disciplina_em_escolas_diferentes_ok(self):
        Disciplina.objects.create(escola=self.escola_a, nome="Matemática")
        Disciplina.objects.create(escola=self.escola_b, nome="Matemática")
        self.assertEqual(Disciplina.objects.filter(nome="Matemática").count(), 2)


class AlunoConstraintTests(_BaseEscolaSetup):
    def test_matricula_unica_por_escola(self):
        Aluno.objects.create(
            escola=self.escola_a,
            matricula="2026001",
            nome_completo="Aluno Um",
            turma=self.turma_a,
        )
        with self.assertRaises(IntegrityError), transaction.atomic():
            Aluno.objects.create(
                escola=self.escola_a,
                matricula="2026001",
                nome_completo="Aluno Dois",
                turma=self.turma_a,
            )

    def test_mesma_matricula_em_escolas_diferentes_ok(self):
        Aluno.objects.create(
            escola=self.escola_a,
            matricula="2026001",
            nome_completo="Aluno A",
            turma=self.turma_a,
        )
        Aluno.objects.create(
            escola=self.escola_b,
            matricula="2026001",
            nome_completo="Aluno B",
            turma=self.turma_b,
        )
        self.assertEqual(Aluno.objects.filter(matricula="2026001").count(), 2)


class AlunoCleanTests(_BaseEscolaSetup):
    def test_clean_falha_quando_turma_de_outra_escola(self):
        """`Aluno.clean()` exige que turma e escola batam."""
        aluno = Aluno(
            escola=self.escola_a,
            matricula="2026099",
            nome_completo="Aluno X",
            turma=self.turma_b,  # turma de outra escola
            data_nascimento=date(2010, 1, 1),
        )
        with self.assertRaises(ValidationError) as ctx:
            aluno.full_clean()
        self.assertIn("turma", ctx.exception.message_dict)

    def test_clean_passa_quando_escolas_batem(self):
        aluno = Aluno(
            escola=self.escola_a,
            matricula="2026100",
            nome_completo="Aluno Y",
            turma=self.turma_a,
        )
        aluno.full_clean()  # não deve levantar
