"""`projetar_agenda` ignora lecionamento inativo.

Antes da remoção de `dias_semana`, se o vínculo estivesse inativo o
`first()` ainda achava e o `dias_semana` vazio (ou o `if lecionamento is
None`) escondia o caso. Com a leitura vindo da grade, um `AulaGrade`
ativo pendurado num `Lecionamento.ativo=False` continuaria projetando
agenda se o filtro não exigisse `lecionamento__ativo=True`. Esse teste
fecha essa borda.
"""
from datetime import time

from django.test import TestCase

from apps.accounts.models import Usuario
from apps.aulas.services import projetar_agenda
from apps.escola.models import Disciplina, Escola, Lecionamento, Professor, Turma
from apps.grade.models import AulaGrade, TempoAula


class ProjetarAgendaLecionamentoInativoTests(TestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        cls.escola = Escola.objects.create(nome="Escola")
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
            username="prof",
            password="x",
            perfil=Usuario.Perfil.PROFESSOR,
            escola=cls.escola,
        )
        cls.professor = Professor.objects.create(
            escola=cls.escola, usuario=cls.usuario
        )
        cls.tempo = TempoAula.objects.create(
            escola=cls.escola,
            turno=cls.turma.turno,
            ordem=1,
            hora_inicio=time(7, 0),
            hora_fim=time(7, 50),
        )

    def _kwargs(self) -> dict:
        return dict(
            escola_id=self.escola.id,
            professor_id=self.professor.id,
            turma_id=self.turma.id,
            disciplina_id=self.disciplina.id,
            ano=2026,
            mes=11,
        )

    def test_lecionamento_inativo_nao_projeta_agenda(self):
        lec = Lecionamento.objects.create(
            escola=self.escola,
            professor=self.professor,
            turma=self.turma,
            disciplina=self.disciplina,
            ativo=False,
        )
        AulaGrade.objects.create(
            escola=self.escola,
            lecionamento=lec,
            turma=self.turma,
            dia_semana=0,
            tempo=self.tempo,
            ativo=True,
        )

        self.assertEqual(projetar_agenda(**self._kwargs()), [])

    def test_lecionamento_ativo_projeta_normalmente(self):
        lec = Lecionamento.objects.create(
            escola=self.escola,
            professor=self.professor,
            turma=self.turma,
            disciplina=self.disciplina,
            ativo=True,
        )
        AulaGrade.objects.create(
            escola=self.escola,
            lecionamento=lec,
            turma=self.turma,
            dia_semana=0,  # segunda
            tempo=self.tempo,
            ativo=True,
        )

        slots = projetar_agenda(**self._kwargs())

        # Novembro/2026 tem 4 segundas: 2, 9, 16, 23, 30 — cinco segundas.
        self.assertEqual(len(slots), 5)
        self.assertTrue(all(slot["dia_semana"] == 0 for slot in slots))
