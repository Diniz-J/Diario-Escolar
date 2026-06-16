"""Testes de modelo de `RegistroAula` — invariantes do `clean()`."""
from datetime import date, timedelta

from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.accounts.models import Usuario
from apps.aulas.models import RegistroAula
from apps.escola.models import (
    Disciplina,
    Escola,
    Lecionamento,
    Professor,
    Turma,
)


class RegistroAulaModelTests(TestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        cls.escola = Escola.objects.create(nome="Escola Teste")
        cls.turma = Turma.objects.create(
            escola=cls.escola,
            nome="1º A",
            turno=Turma.Turno.MATUTINO,
            ano_letivo=2026,
        )
        cls.disciplina = Disciplina.objects.create(
            escola=cls.escola, nome="Matemática"
        )
        cls.usuario = Usuario.objects.create_user(
            username="doc",
            password="x",
            perfil=Usuario.Perfil.PROFESSOR,
            escola=cls.escola,
        )
        cls.professor = Professor.objects.create(
            escola=cls.escola, usuario=cls.usuario
        )
        cls.lecionamento = Lecionamento.objects.create(
            escola=cls.escola,
            professor=cls.professor,
            turma=cls.turma,
            disciplina=cls.disciplina,
            dias_semana=[0, 2],  # segunda e quarta
        )

    def _registro(self, **overrides) -> RegistroAula:
        dados = {
            "escola": self.escola,
            "turma": self.turma,
            "disciplina": self.disciplina,
            "professor": self.professor,
            "data": date.today(),
            "conteudo": "Equação do 2º grau",
            "status": RegistroAula.Status.LANCADO,
        }
        dados.update(overrides)
        return RegistroAula(**dados)

    def test_registro_valido_passa_no_clean(self):
        self._registro().full_clean()  # não levanta

    def test_rascunho_sem_conteudo_e_valido(self):
        self._registro(
            status=RegistroAula.Status.RASCUNHO, conteudo=""
        ).full_clean()

    def test_lancado_sem_conteudo_falha(self):
        with self.assertRaises(ValidationError) as ctx:
            self._registro(
                status=RegistroAula.Status.LANCADO, conteudo="   "
            ).full_clean()
        self.assertIn("conteudo", ctx.exception.error_dict)

    def test_data_futura_falha(self):
        amanha = date.today() + timedelta(days=1)
        with self.assertRaises(ValidationError) as ctx:
            self._registro(data=amanha).full_clean()
        self.assertIn("data", ctx.exception.error_dict)

    def test_sem_lecionamento_falha(self):
        outra_disc = Disciplina.objects.create(
            escola=self.escola, nome="História"
        )
        with self.assertRaises(ValidationError) as ctx:
            self._registro(disciplina=outra_disc).full_clean()
        self.assertIn("professor", ctx.exception.error_dict)

    def test_turma_de_outra_escola_falha(self):
        outra_escola = Escola.objects.create(nome="Outra")
        outra_turma = Turma.objects.create(
            escola=outra_escola,
            nome="1B",
            turno=Turma.Turno.MATUTINO,
            ano_letivo=2026,
        )
        with self.assertRaises(ValidationError) as ctx:
            self._registro(turma=outra_turma).full_clean()
        self.assertIn("turma", ctx.exception.error_dict)
