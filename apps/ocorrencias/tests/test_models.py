"""Testes do modelo `Ocorrencia` — invariantes de `clean()` e defaults."""
from datetime import date, timedelta

from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.accounts.models import Usuario
from apps.escola.models import Aluno, Escola, Professor, Turma
from apps.ocorrencias.models import Ocorrencia


class _BaseOcorrenciaSetup(TestCase):
    """Setup compartilhado: duas escolas, com turmas/alunos/professores em cada uma."""

    @classmethod
    def setUpTestData(cls) -> None:
        cls.escola_a = Escola.objects.create(nome="Escola A")
        cls.escola_b = Escola.objects.create(nome="Escola B")

        cls.turma_a = Turma.objects.create(
            escola=cls.escola_a,
            nome="1º A",
            turno=Turma.Turno.MATUTINO,
            ano_letivo=2026,
        )
        cls.turma_a2 = Turma.objects.create(
            escola=cls.escola_a,
            nome="2º A",
            turno=Turma.Turno.MATUTINO,
            ano_letivo=2026,
        )
        cls.turma_b = Turma.objects.create(
            escola=cls.escola_b,
            nome="1º A",
            turno=Turma.Turno.MATUTINO,
            ano_letivo=2026,
        )

        cls.aluno_a = Aluno.objects.create(
            escola=cls.escola_a,
            matricula="A1",
            nome_completo="Aluno A",
            turma=cls.turma_a,
        )
        cls.aluno_b = Aluno.objects.create(
            escola=cls.escola_b,
            matricula="B1",
            nome_completo="Aluno B",
            turma=cls.turma_b,
        )

        cls.usuario_docente_a = Usuario.objects.create_user(
            username="doc_a",
            password="x",
            perfil=Usuario.Perfil.PROFESSOR,
            escola=cls.escola_a,
        )
        cls.usuario_docente_b = Usuario.objects.create_user(
            username="doc_b",
            password="x",
            perfil=Usuario.Perfil.PROFESSOR,
            escola=cls.escola_b,
        )
        cls.professor_a = Professor.objects.create(
            escola=cls.escola_a, usuario=cls.usuario_docente_a
        )
        cls.professor_b = Professor.objects.create(
            escola=cls.escola_b, usuario=cls.usuario_docente_b
        )


class OcorrenciaCleanTests(_BaseOcorrenciaSetup):
    """Cobre as invariantes cruzadas validadas em `Ocorrencia.clean()`."""

    def test_clean_passa_no_caminho_feliz(self):
        ocorrencia = Ocorrencia(
            escola=self.escola_a,
            turma=self.turma_a,
            aluno=self.aluno_a,
            professor=self.professor_a,
            descricao="Conversava em sala",
        )
        ocorrencia.full_clean()  # não deve levantar

    def test_clean_passa_sem_professor(self):
        """Professor é opcional — admin/diretor abrem sem objeto Professor."""
        ocorrencia = Ocorrencia(
            escola=self.escola_a,
            turma=self.turma_a,
            aluno=self.aluno_a,
            descricao="Registro sem professor vinculado",
        )
        ocorrencia.full_clean()

    def test_clean_falha_quando_aluno_de_outra_escola(self):
        ocorrencia = Ocorrencia(
            escola=self.escola_a,
            turma=self.turma_a,
            aluno=self.aluno_b,
            descricao="x",
        )
        with self.assertRaises(ValidationError) as ctx:
            ocorrencia.full_clean()
        self.assertIn("aluno", ctx.exception.message_dict)

    def test_clean_falha_quando_turma_nao_e_do_aluno(self):
        ocorrencia = Ocorrencia(
            escola=self.escola_a,
            turma=self.turma_a2,  # turma da mesma escola, mas não é a do aluno
            aluno=self.aluno_a,
            descricao="x",
        )
        with self.assertRaises(ValidationError) as ctx:
            ocorrencia.full_clean()
        self.assertIn("turma", ctx.exception.message_dict)

    def test_clean_falha_quando_professor_de_outra_escola(self):
        ocorrencia = Ocorrencia(
            escola=self.escola_a,
            turma=self.turma_a,
            aluno=self.aluno_a,
            professor=self.professor_b,
            descricao="x",
        )
        with self.assertRaises(ValidationError) as ctx:
            ocorrencia.full_clean()
        self.assertIn("professor", ctx.exception.message_dict)

    def test_clean_falha_quando_data_no_futuro(self):
        ocorrencia = Ocorrencia(
            escola=self.escola_a,
            turma=self.turma_a,
            aluno=self.aluno_a,
            descricao="x",
            data_ocorrencia=date.today() + timedelta(days=1),
        )
        with self.assertRaises(ValidationError) as ctx:
            ocorrencia.full_clean()
        self.assertIn("data_ocorrencia", ctx.exception.message_dict)

    def test_clean_passa_com_data_de_hoje(self):
        ocorrencia = Ocorrencia(
            escola=self.escola_a,
            turma=self.turma_a,
            aluno=self.aluno_a,
            descricao="x",
            data_ocorrencia=date.today(),
        )
        ocorrencia.full_clean()


class OcorrenciaDefaultsTests(_BaseOcorrenciaSetup):
    """Defaults e ordenação."""

    def test_status_default_aberta(self):
        ocorrencia = Ocorrencia.objects.create(
            escola=self.escola_a,
            turma=self.turma_a,
            aluno=self.aluno_a,
            descricao="x",
        )
        self.assertEqual(ocorrencia.status, Ocorrencia.Status.ABERTA)

    def test_data_ocorrencia_default_hoje(self):
        ocorrencia = Ocorrencia.objects.create(
            escola=self.escola_a,
            turma=self.turma_a,
            aluno=self.aluno_a,
            descricao="x",
        )
        self.assertEqual(ocorrencia.data_ocorrencia, date.today())

    def test_ordering_mais_recente_primeiro(self):
        antiga = Ocorrencia.objects.create(
            escola=self.escola_a,
            turma=self.turma_a,
            aluno=self.aluno_a,
            descricao="antiga",
            data_ocorrencia=date.today() - timedelta(days=10),
        )
        recente = Ocorrencia.objects.create(
            escola=self.escola_a,
            turma=self.turma_a,
            aluno=self.aluno_a,
            descricao="recente",
            data_ocorrencia=date.today(),
        )
        ids = list(Ocorrencia.objects.values_list("id", flat=True))
        self.assertEqual(ids, [recente.id, antiga.id])
