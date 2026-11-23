"""Chamada por bloco de tempos: dedução do dia todo e assinatura.

Fatia 3 do `PRESENCA.md`. Duas mudanças de comportamento da API que
precisam de trava própria:

- `tempos` omitido significa **o dia todo** (o turno inteiro da turma, ou
  um tempo onde não há catálogo). É isso que mantém o cliente que ainda
  não manda o campo com a mesma semântica da chamada diária.
- o professor deixou de vir de um select: quem lança assina. A direção
  segue podendo lançar por outro.
"""
from datetime import date, time

from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.models import Usuario
from apps.escola.models import Aluno, Disciplina, Escola, Professor, Turma
from apps.grade.models import TempoAula
from apps.presenca.models import RegistroPresenca

URL = reverse("api_v1:registro-presenca-list")


class _TemposSetup(TestCase):
    """Helpers sem testes, pra subclasse não herdar teste do pai."""

    @classmethod
    def setUpTestData(cls) -> None:
        cls.escola = Escola.objects.create(nome="Escola")
        cls.turma = Turma.objects.create(
            escola=cls.escola,
            nome="1º A",
            turno=Turma.Turno.MATUTINO,
            ano_letivo=2026,
        )
        cls.aluno = Aluno.objects.create(
            escola=cls.escola, matricula="A1", nome_completo="Ana", turma=cls.turma
        )
        cls.matematica = Disciplina.objects.create(
            escola=cls.escola, nome="Matemática"
        )
        cls.diretora = Usuario.objects.create_user(
            username="dir", password="x", perfil=Usuario.Perfil.DIRETOR,
            escola=cls.escola,
        )
        cls.usuario_prof = Usuario.objects.create_user(
            username="prof", password="x", perfil=Usuario.Perfil.PROFESSOR,
            escola=cls.escola,
        )
        cls.professor = Professor.objects.create(
            escola=cls.escola, usuario=cls.usuario_prof
        )
        cls.usuario_prof2 = Usuario.objects.create_user(
            username="prof2", password="x", perfil=Usuario.Perfil.PROFESSOR,
            escola=cls.escola,
        )
        cls.professor2 = Professor.objects.create(
            escola=cls.escola, usuario=cls.usuario_prof2
        )

    def setUp(self) -> None:
        self.client = APIClient()

    def _cadastrar_tempos(self, quantidade: int) -> None:
        for ordem in range(1, quantidade + 1):
            TempoAula.objects.create(
                escola=self.escola,
                turno=Turma.Turno.MATUTINO,
                ordem=ordem,
                hora_inicio=time(6 + ordem, 0),
                hora_fim=time(6 + ordem, 50),
            )

    def _criar(self, usuario, **extra):
        self.client.force_authenticate(user=usuario)
        payload = {"turma": self.turma.id, "data": date.today().isoformat()}
        payload.update(extra)
        return self.client.post(URL, payload, format="json")


class TemposDaChamadaTests(_TemposSetup):
    """Dedução do bloco e validação contra o catálogo."""

    def test_sem_tempos_com_catalogo_cobre_o_dia_todo(self):
        self._cadastrar_tempos(4)
        resposta = self._criar(self.diretora)
        self.assertEqual(resposta.status_code, 201, resposta.data)
        self.assertEqual(resposta.data["tempos"], [1, 2, 3, 4])

    def test_sem_tempos_e_sem_catalogo_vale_um_tempo(self):
        """Instalação que ainda não montou a grade segue lançando chamada."""
        resposta = self._criar(self.diretora)
        self.assertEqual(resposta.status_code, 201, resposta.data)
        self.assertEqual(resposta.data["tempos"], [1])

    def test_bloco_explicito_e_respeitado(self):
        self._cadastrar_tempos(4)
        resposta = self._criar(self.diretora, tempos=[1, 2])
        self.assertEqual(resposta.status_code, 201, resposta.data)
        self.assertEqual(resposta.data["tempos"], [1, 2])

    def test_tempo_fora_do_catalogo_da_400(self):
        self._cadastrar_tempos(2)
        resposta = self._criar(self.diretora, tempos=[5])
        self.assertEqual(resposta.status_code, 400, resposta.data)
        self.assertIn("tempos", resposta.data)

    def test_tempos_detalhe_traz_o_horario_do_catalogo(self):
        self._cadastrar_tempos(2)
        resposta = self._criar(self.diretora, tempos=[2])
        self.assertEqual(resposta.status_code, 201, resposta.data)
        detalhe = resposta.data["tempos_detalhe"]
        self.assertEqual(detalhe[0]["ordem"], 2)
        self.assertEqual(detalhe[0]["hora_inicio"], "08:00:00")

    def test_disciplina_e_opcional(self):
        """Nulo = chamada do dia; é o que serve o fundamental I."""
        sem = self._criar(self.diretora)
        self.assertEqual(sem.status_code, 201, sem.data)
        self.assertIsNone(sem.data["disciplina"])

        com = self._criar(
            self.diretora,
            tempos=[2],
            disciplina=self.matematica.id,
        )
        self.assertEqual(com.status_code, 201, com.data)
        self.assertEqual(com.data["disciplina"], self.matematica.id)
        self.assertEqual(com.data["disciplina_nome"], "Matemática")


class AssinaturaDaChamadaTests(_TemposSetup):
    """Quem lança assina — molde do diário de aula."""

    def test_professor_lanca_no_proprio_nome_sem_mandar_o_campo(self):
        resposta = self._criar(self.usuario_prof)
        self.assertEqual(resposta.status_code, 201, resposta.data)
        self.assertEqual(resposta.data["professor"], self.professor.id)

    def test_professor_nao_lanca_em_nome_de_outro(self):
        resposta = self._criar(self.usuario_prof, professor=self.professor2.id)
        self.assertEqual(resposta.status_code, 403, resposta.data)
        self.assertFalse(RegistroPresenca.objects.exists())

    def test_direcao_lanca_por_outro_professor(self):
        """Cobertura de falta e correção de lançamento são da direção."""
        resposta = self._criar(self.diretora, professor=self.professor2.id)
        self.assertEqual(resposta.status_code, 201, resposta.data)
        self.assertEqual(resposta.data["professor"], self.professor2.id)

    def test_direcao_sem_professor_fica_sem_assinatura(self):
        resposta = self._criar(self.diretora)
        self.assertEqual(resposta.status_code, 201, resposta.data)
        self.assertIsNone(resposta.data["professor"])

    def test_inspetor_lanca_sem_assinatura(self):
        """Inspetor opera como professor mas não tem cadastro de Professor."""
        inspetor = Usuario.objects.create_user(
            username="ins", password="x", perfil=Usuario.Perfil.INSPETOR,
            escola=self.escola,
        )
        resposta = self._criar(inspetor)
        self.assertEqual(resposta.status_code, 201, resposta.data)
        self.assertIsNone(resposta.data["professor"])
