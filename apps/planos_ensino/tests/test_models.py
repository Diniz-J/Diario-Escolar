"""Testes do modelo `PlanoEnsino`."""
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from apps.escola.models import Disciplina, Escola, Turma
from apps.planos_ensino.models import PlanoEnsino


class _Setup(TestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        cls.escola_a = Escola.objects.create(nome="A")
        cls.escola_b = Escola.objects.create(nome="B")
        cls.turma_a = Turma.objects.create(
            escola=cls.escola_a, nome="1A",
            turno=Turma.Turno.MATUTINO, ano_letivo=2026,
        )
        cls.turma_b = Turma.objects.create(
            escola=cls.escola_b, nome="1A",
            turno=Turma.Turno.MATUTINO, ano_letivo=2026,
        )
        cls.disc_a = Disciplina.objects.create(escola=cls.escola_a, nome="Mat")
        cls.disc_b = Disciplina.objects.create(escola=cls.escola_b, nome="Mat")


class CleanTests(_Setup):
    def test_caminho_feliz(self):
        p = PlanoEnsino(
            escola=self.escola_a, turma=self.turma_a,
            disciplina=self.disc_a, ano_letivo=2026,
        )
        p.full_clean()

    def test_turma_de_outra_escola(self):
        p = PlanoEnsino(
            escola=self.escola_a, turma=self.turma_b,
            disciplina=self.disc_a, ano_letivo=2026,
        )
        with self.assertRaises(ValidationError) as ctx:
            p.full_clean()
        self.assertIn("turma", ctx.exception.message_dict)

    def test_disciplina_de_outra_escola(self):
        p = PlanoEnsino(
            escola=self.escola_a, turma=self.turma_a,
            disciplina=self.disc_b, ano_letivo=2026,
        )
        with self.assertRaises(ValidationError) as ctx:
            p.full_clean()
        self.assertIn("disciplina", ctx.exception.message_dict)

    def test_ano_letivo_diferente_da_turma(self):
        p = PlanoEnsino(
            escola=self.escola_a, turma=self.turma_a,
            disciplina=self.disc_a, ano_letivo=2025,
        )
        with self.assertRaises(ValidationError) as ctx:
            p.full_clean()
        self.assertIn("ano_letivo", ctx.exception.message_dict)


class UniqueConstraintTests(_Setup):
    def test_um_plano_por_turma_disciplina_ano(self):
        PlanoEnsino.objects.create(
            escola=self.escola_a, turma=self.turma_a,
            disciplina=self.disc_a, ano_letivo=2026,
        )
        with self.assertRaises(IntegrityError), transaction.atomic():
            PlanoEnsino.objects.create(
                escola=self.escola_a, turma=self.turma_a,
                disciplina=self.disc_a, ano_letivo=2026,
            )

    def test_mesma_disciplina_turma_anos_diferentes_ok(self):
        # Cria uma segunda turma do ano 2027 pra repetir disciplina.
        turma_2027 = Turma.objects.create(
            escola=self.escola_a, nome="1A",
            turno=Turma.Turno.MATUTINO, ano_letivo=2027,
        )
        PlanoEnsino.objects.create(
            escola=self.escola_a, turma=self.turma_a,
            disciplina=self.disc_a, ano_letivo=2026,
        )
        PlanoEnsino.objects.create(
            escola=self.escola_a, turma=turma_2027,
            disciplina=self.disc_a, ano_letivo=2027,
        )
        self.assertEqual(PlanoEnsino.objects.count(), 2)


class DefaultsTests(_Setup):
    def test_campos_de_texto_vazios_por_default(self):
        p = PlanoEnsino.objects.create(
            escola=self.escola_a, turma=self.turma_a,
            disciplina=self.disc_a, ano_letivo=2026,
        )
        self.assertEqual(p.ementa, "")
        self.assertEqual(p.conteudo_programatico, "")
        self.assertEqual(p.habilidades_bncc, "")
        self.assertTrue(p.ativo)
