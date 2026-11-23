"""Testes dos modelos `RegistroPresenca` e `ItemPresenca`."""
from datetime import date, timedelta

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from apps.accounts.models import Usuario
from apps.escola.models import Aluno, Escola, Professor, Turma
from apps.presenca.models import ItemPresenca, RegistroPresenca


class _BasePresencaSetup(TestCase):
    """Duas escolas com turmas e alunos em cada uma."""

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

        cls.aluno_a = Aluno.objects.create(
            escola=cls.escola_a, matricula="A1",
            nome_completo="Aluno A", turma=cls.turma_a,
        )
        cls.aluno_b = Aluno.objects.create(
            escola=cls.escola_b, matricula="B1",
            nome_completo="Aluno B", turma=cls.turma_b,
        )

        cls.usuario_docente_a = Usuario.objects.create_user(
            username="doc_a", password="x",
            perfil=Usuario.Perfil.PROFESSOR, escola=cls.escola_a,
        )
        cls.professor_a = Professor.objects.create(
            escola=cls.escola_a, usuario=cls.usuario_docente_a
        )


class RegistroPresencaCleanTests(_BasePresencaSetup):
    """Invariantes do `clean()` do registro."""

    def test_clean_caminho_feliz(self):
        registro = RegistroPresenca(
            escola=self.escola_a, turma=self.turma_a, professor=self.professor_a,
            tempos=[1],
        )
        registro.full_clean()

    def test_clean_sem_professor_ok(self):
        registro = RegistroPresenca(
            escola=self.escola_a, turma=self.turma_a, tempos=[1]
        )
        registro.full_clean()

    def test_clean_falha_turma_de_outra_escola(self):
        registro = RegistroPresenca(escola=self.escola_a, turma=self.turma_b)
        with self.assertRaises(ValidationError) as ctx:
            registro.full_clean()
        self.assertIn("turma", ctx.exception.message_dict)

    def test_clean_falha_data_futura(self):
        registro = RegistroPresenca(
            escola=self.escola_a, turma=self.turma_a,
            data=date.today() + timedelta(days=1),
        )
        with self.assertRaises(ValidationError) as ctx:
            registro.full_clean()
        self.assertIn("data", ctx.exception.message_dict)

    def test_clean_falha_professor_de_outra_escola(self):
        # Criar um professor da escola B pra forçar o mismatch.
        usuario_b = Usuario.objects.create_user(
            username="doc_b", password="x",
            perfil=Usuario.Perfil.PROFESSOR, escola=self.escola_b,
        )
        professor_b = Professor.objects.create(escola=self.escola_b, usuario=usuario_b)
        registro = RegistroPresenca(
            escola=self.escola_a, turma=self.turma_a, professor=professor_b,
        )
        with self.assertRaises(ValidationError) as ctx:
            registro.full_clean()
        self.assertIn("professor", ctx.exception.message_dict)


class RegistroPresencaBlocoDeTemposTests(_BasePresencaSetup):
    """Várias chamadas por dia, uma por bloco de tempos (`PRESENCA.md`).

    Substitui os testes do antigo unique `(escola, turma, data)`, que
    caiu em nov/2026: a turma passou a ter uma chamada por bloco, e o que
    não pode repetir é o **tempo**, não o dia. A garantia saiu do banco
    (constraint não cobre interseção de array) e virou validação, então
    estes testes são o que impede o tempo contado em dobro.
    """

    def test_blocos_disjuntos_no_mesmo_dia_sao_validos(self):
        RegistroPresenca.objects.create(
            escola=self.escola_a, turma=self.turma_a, tempos=[1, 2]
        )
        segundo = RegistroPresenca(
            escola=self.escola_a, turma=self.turma_a, tempos=[3, 4]
        )
        segundo.full_clean()
        segundo.save()
        self.assertEqual(RegistroPresenca.objects.count(), 2)

    def test_bloco_sobreposto_no_mesmo_dia_e_recusado(self):
        RegistroPresenca.objects.create(
            escola=self.escola_a, turma=self.turma_a, tempos=[1, 2]
        )
        conflitante = RegistroPresenca(
            escola=self.escola_a, turma=self.turma_a, tempos=[2, 3]
        )
        with self.assertRaises(ValidationError) as ctx:
            conflitante.full_clean()
        self.assertIn("tempos", ctx.exception.message_dict)

    def test_mesmo_bloco_em_dias_diferentes_e_valido(self):
        RegistroPresenca.objects.create(
            escola=self.escola_a, turma=self.turma_a, tempos=[1]
        )
        outro_dia = RegistroPresenca(
            escola=self.escola_a,
            turma=self.turma_a,
            data=date.today() - timedelta(days=1),
            tempos=[1],
        )
        outro_dia.full_clean()

    def test_bloco_vazio_e_recusado(self):
        registro = RegistroPresenca(
            escola=self.escola_a, turma=self.turma_a, tempos=[]
        )
        with self.assertRaises(ValidationError) as ctx:
            registro.full_clean()
        self.assertIn("tempos", ctx.exception.message_dict)

    def test_tempo_repetido_no_bloco_e_recusado(self):
        registro = RegistroPresenca(
            escola=self.escola_a, turma=self.turma_a, tempos=[1, 1]
        )
        with self.assertRaises(ValidationError) as ctx:
            registro.full_clean()
        self.assertIn("tempos", ctx.exception.message_dict)

    def test_default_e_um_tempo(self):
        """Chamada criada fora da API pesa um tempo, não zero.

        Bloco vazio teria peso zero na frequência e sumiria do
        denominador em silêncio — ver `tempo_unico` em `models.py`.
        """
        registro = RegistroPresenca.objects.create(
            escola=self.escola_a, turma=self.turma_a
        )
        self.assertEqual(registro.tempos, [1])

    def test_mesma_data_turmas_diferentes_ok(self):
        outra_turma = Turma.objects.create(
            escola=self.escola_a, nome="2º A",
            turno=Turma.Turno.MATUTINO, ano_letivo=2026,
        )
        RegistroPresenca.objects.create(escola=self.escola_a, turma=self.turma_a)
        RegistroPresenca.objects.create(escola=self.escola_a, turma=outra_turma)
        self.assertEqual(RegistroPresenca.objects.count(), 2)


class ItemPresencaTests(_BasePresencaSetup):
    """Invariantes e save() do item."""

    def test_save_sincroniza_escola_com_registro(self):
        """`item.escola` é forçado a bater com `registro.escola` no save."""
        registro = RegistroPresenca.objects.create(
            escola=self.escola_a, turma=self.turma_a
        )
        # Mesmo passando uma escola errada, o save corrige.
        item = ItemPresenca(
            registro=registro, aluno=self.aluno_a,
            escola=self.escola_b,  # divergente — deve ser sobrescrito
        )
        item.save()
        item.refresh_from_db()
        self.assertEqual(item.escola_id, self.escola_a.id)

    def test_clean_falha_aluno_de_outra_turma(self):
        outra_turma = Turma.objects.create(
            escola=self.escola_a, nome="2º A",
            turno=Turma.Turno.MATUTINO, ano_letivo=2026,
        )
        outro_aluno = Aluno.objects.create(
            escola=self.escola_a, matricula="A2",
            nome_completo="Aluno X", turma=outra_turma,
        )
        registro = RegistroPresenca.objects.create(
            escola=self.escola_a, turma=self.turma_a
        )
        item = ItemPresenca(
            registro=registro, aluno=outro_aluno, escola=self.escola_a,
        )
        with self.assertRaises(ValidationError) as ctx:
            item.full_clean()
        self.assertIn("aluno", ctx.exception.message_dict)

    def test_clean_falha_aluno_de_outra_escola(self):
        registro = RegistroPresenca.objects.create(
            escola=self.escola_a, turma=self.turma_a
        )
        item = ItemPresenca(
            registro=registro, aluno=self.aluno_b, escola=self.escola_a,
        )
        with self.assertRaises(ValidationError) as ctx:
            item.full_clean()
        self.assertIn("aluno", ctx.exception.message_dict)

    def test_unique_constraint_aluno_no_mesmo_registro(self):
        registro = RegistroPresenca.objects.create(
            escola=self.escola_a, turma=self.turma_a
        )
        ItemPresenca.objects.create(
            registro=registro, aluno=self.aluno_a, escola=self.escola_a
        )
        with self.assertRaises(IntegrityError), transaction.atomic():
            ItemPresenca.objects.create(
                registro=registro, aluno=self.aluno_a, escola=self.escola_a
            )

    def test_status_default_presente(self):
        registro = RegistroPresenca.objects.create(
            escola=self.escola_a, turma=self.turma_a
        )
        item = ItemPresenca.objects.create(
            registro=registro, aluno=self.aluno_a, escola=self.escola_a
        )
        self.assertEqual(item.status, ItemPresenca.Status.PRESENTE)

    def test_cascade_delete_remove_itens(self):
        """Apagar o registro remove os itens em cascade."""
        registro = RegistroPresenca.objects.create(
            escola=self.escola_a, turma=self.turma_a
        )
        ItemPresenca.objects.create(
            registro=registro, aluno=self.aluno_a, escola=self.escola_a
        )
        self.assertEqual(ItemPresenca.objects.count(), 1)
        registro.delete()
        self.assertEqual(ItemPresenca.objects.count(), 0)
