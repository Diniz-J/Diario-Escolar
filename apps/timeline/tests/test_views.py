"""Testes do endpoint da timeline do aluno.

Foco no contorno: quem pode ler, o guard de IDOR e os 400 de parâmetro
que a tela pode mandar.
"""
from datetime import date

from django.test import TestCase
from django.urls import reverse

from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import Usuario
from apps.escola.models import Aluno, Escola, Turma
from apps.ocorrencias.models import Ocorrencia


class TimelineEndpointTests(TestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        cls.escola = Escola.objects.create(nome="Escola")
        cls.outra_escola = Escola.objects.create(nome="Outra")
        cls.turma = Turma.objects.create(
            escola=cls.escola,
            nome="2º B",
            turno=Turma.Turno.MATUTINO,
            ano_letivo=2026,
        )
        cls.turma_alheia = Turma.objects.create(
            escola=cls.outra_escola,
            nome="2º B",
            turno=Turma.Turno.MATUTINO,
            ano_letivo=2026,
        )
        cls.aluno = Aluno.objects.create(
            escola=cls.escola,
            matricula="M1",
            nome_completo="Ana",
            turma=cls.turma,
        )
        cls.aluno_alheio = Aluno.objects.create(
            escola=cls.outra_escola,
            matricula="X1",
            nome_completo="Alheio",
            turma=cls.turma_alheia,
        )
        cls.diretor = Usuario.objects.create_user(
            username="dir",
            password="x",
            perfil=Usuario.Perfil.DIRETOR,
            escola=cls.escola,
        )
        cls.professor = Usuario.objects.create_user(
            username="prof",
            password="x",
            perfil=Usuario.Perfil.PROFESSOR,
            escola=cls.escola,
        )
        cls.inspetor = Usuario.objects.create_user(
            username="insp",
            password="x",
            perfil=Usuario.Perfil.INSPETOR,
            escola=cls.escola,
        )
        cls.admin = Usuario.objects.create_user(
            username="adm", password="x", perfil=Usuario.Perfil.ADMIN
        )
        Ocorrencia.objects.create(
            escola=cls.escola,
            turma=cls.turma,
            aluno=cls.aluno,
            descricao="Conversa em sala",
            data_ocorrencia=date(2026, 3, 10),
        )

    def setUp(self) -> None:
        self.client = APIClient()

    def _auth(self, user) -> None:
        token = RefreshToken.for_user(user).access_token
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def _url(self, aluno) -> str:
        return reverse("api_v1:timeline-aluno", args=[aluno.pk])

    def test_sem_token_401(self):
        self.assertEqual(self.client.get(self._url(self.aluno)).status_code, 401)

    def test_diretor_le(self):
        self._auth(self.diretor)
        resp = self.client.get(self._url(self.aluno))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["aluno"]["matricula"], "M1")
        self.assertGreaterEqual(len(resp.data["eventos"]), 1)

    def test_professor_le(self):
        """Quem lança ocorrência e chamada precisa ver o que já lançou."""
        self._auth(self.professor)
        self.assertEqual(
            self.client.get(self._url(self.aluno)).status_code, 200
        )

    def test_inspetor_le(self):
        self._auth(self.inspetor)
        self.assertEqual(
            self.client.get(self._url(self.aluno)).status_code, 200
        )

    def test_aluno_de_outra_escola_403(self):
        """Guard de IDOR, igual ao do boletim."""
        self._auth(self.diretor)
        resp = self.client.get(self._url(self.aluno_alheio))
        self.assertEqual(resp.status_code, 403)

    def test_admin_global_ve_qualquer_escola(self):
        self._auth(self.admin)
        resp = self.client.get(self._url(self.aluno_alheio))
        self.assertEqual(resp.status_code, 200)

    def test_aluno_inexistente_404(self):
        self._auth(self.diretor)
        resp = self.client.get(
            reverse("api_v1:timeline-aluno", args=[999999])
        )
        self.assertEqual(resp.status_code, 404)

    def test_data_invalida_400(self):
        self._auth(self.diretor)
        resp = self.client.get(
            self._url(self.aluno), {"data_inicio": "10/03/2026"}
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("data_inicio", resp.data)

    def test_intervalo_invertido_400(self):
        """Sem o 400, a tela diria 'nenhum evento' pra aluno cheio deles."""
        self._auth(self.diretor)
        resp = self.client.get(
            self._url(self.aluno),
            {"data_inicio": "2026-03-31", "data_fim": "2026-03-01"},
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("data_fim", resp.data)

    def test_janela_recorta(self):
        self._auth(self.diretor)
        resp = self.client.get(
            self._url(self.aluno),
            {"data_inicio": "2026-03-01", "data_fim": "2026-03-31"},
        )
        self.assertEqual(resp.status_code, 200)
        tipos = {evento["tipo"] for evento in resp.data["eventos"]}
        self.assertEqual(tipos, {"ocorrencia"})
