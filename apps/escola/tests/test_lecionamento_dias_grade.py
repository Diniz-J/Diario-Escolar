"""`dias_grade`: os dias de aula vêm da grade, não de um campo.

`Lecionamento.dias_semana` foi removido em nov/2026 (fatia 5 do
`PRESENCA.md`): a grade horária diz dia **e** tempo, então o campo era uma
segunda verdade sobre o mesmo fato. O serializer expõe `dias_grade`,
derivado e read-only.

Dois pontos que precisam de trava: o valor tem que vir **anotado** (a
ficha do professor lista todos os vínculos dele, e uma query por linha
voltaria o N+1 que o `ArrayAgg` existe pra evitar), e o campo **não** pode
aceitar escrita — um read-only que engole PATCH em silêncio faria quem
editasse os dias por ali concluir que salvou.
"""
from datetime import time

from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.models import Usuario
from apps.escola.models import Disciplina, Escola, Lecionamento, Professor, Turma
from apps.grade.models import AulaGrade, TempoAula

URL = reverse("api_v1:lecionamento-list")


class DiasGradeTests(TestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        cls.escola = Escola.objects.create(nome="Escola")
        cls.turma = Turma.objects.create(
            escola=cls.escola,
            nome="1º A",
            turno=Turma.Turno.MATUTINO,
            ano_letivo=2026,
        )
        cls.diretora = Usuario.objects.create_user(
            username="dir", password="x", perfil=Usuario.Perfil.DIRETOR,
            escola=cls.escola,
        )
        usuario = Usuario.objects.create_user(
            username="prof", password="x", perfil=Usuario.Perfil.PROFESSOR,
            escola=cls.escola,
        )
        cls.professor = Professor.objects.create(
            escola=cls.escola, usuario=usuario
        )
        cls.tempo1 = TempoAula.objects.create(
            escola=cls.escola, turno=Turma.Turno.MATUTINO, ordem=1,
            hora_inicio=time(7, 0), hora_fim=time(7, 50),
        )
        cls.tempo2 = TempoAula.objects.create(
            escola=cls.escola, turno=Turma.Turno.MATUTINO, ordem=2,
            hora_inicio=time(7, 50), hora_fim=time(8, 40),
        )

    def setUp(self) -> None:
        self.client = APIClient()
        self.client.force_authenticate(user=self.diretora)

    def _lecionamento(self, nome_disciplina: str) -> Lecionamento:
        disciplina = Disciplina.objects.create(
            escola=self.escola, nome=nome_disciplina
        )
        return Lecionamento.objects.create(
            escola=self.escola,
            professor=self.professor,
            turma=self.turma,
            disciplina=disciplina,
        )

    def test_dias_vem_da_grade_sem_repetir_o_dia(self):
        """Bloco duplo na segunda é um dia, não dois."""
        lecionamento = self._lecionamento("Matemática")
        for tempo in (self.tempo1, self.tempo2):
            AulaGrade.objects.create(
                escola=self.escola, lecionamento=lecionamento,
                turma=self.turma, dia_semana=0, tempo=tempo,
            )
        AulaGrade.objects.create(
            escola=self.escola, lecionamento=lecionamento,
            turma=self.turma, dia_semana=2, tempo=self.tempo1,
        )

        linha = self.client.get(URL).data[0]
        self.assertEqual(sorted(linha["dias_grade"]), [0, 2])

    def test_sem_grade_o_campo_vem_vazio(self):
        """O front itera o valor: `None` quebraria a ficha do professor."""
        self._lecionamento("Português")
        linha = self.client.get(URL).data[0]
        self.assertEqual(linha["dias_grade"], [])

    def test_slot_desativado_nao_conta(self):
        lecionamento = self._lecionamento("História")
        AulaGrade.objects.create(
            escola=self.escola, lecionamento=lecionamento,
            turma=self.turma, dia_semana=3, tempo=self.tempo1, ativo=False,
        )
        linha = self.client.get(URL).data[0]
        self.assertEqual(linha["dias_grade"], [])

    def test_patch_no_campo_derivado_nao_finge_que_salvou(self):
        """Read-only: o DRF descarta o valor, e o retorno mostra o real."""
        lecionamento = self._lecionamento("Geografia")
        AulaGrade.objects.create(
            escola=self.escola, lecionamento=lecionamento,
            turma=self.turma, dia_semana=1, tempo=self.tempo1,
        )
        resposta = self.client.patch(
            reverse("api_v1:lecionamento-detail", args=[lecionamento.pk]),
            {"dias_grade": [5, 6]},
            format="json",
        )
        self.assertEqual(resposta.status_code, 200, resposta.data)
        self.assertEqual(resposta.data["dias_grade"], [1])

    def test_lista_nao_faz_uma_query_por_vinculo(self):
        """É a razão do `ArrayAgg` no viewset em vez de ler no serializer."""
        # Um dia por vínculo: o unique da grade impede duas aulas da mesma
        # turma no mesmo dia e tempo.
        for dia, nome in enumerate(("Artes", "Música", "Física", "Química")):
            lecionamento = self._lecionamento(nome)
            AulaGrade.objects.create(
                escola=self.escola, lecionamento=lecionamento,
                turma=self.turma, dia_semana=dia, tempo=self.tempo1,
            )

        with self.assertNumQueries(1):
            self.client.get(URL)
