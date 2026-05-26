"""Smoke tests do endpoint /api/v1/boletins/aluno/{id}/."""
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import Usuario
from apps.escola.models import Aluno, Escola, Turma


class BoletimEndpointTests(TestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        cls.escola = Escola.objects.create(nome="Escola")
        cls.outra_escola = Escola.objects.create(nome="Outra")
        cls.turma = Turma.objects.create(
            escola=cls.escola, nome="1º A",
            turno=Turma.Turno.MATUTINO, ano_letivo=2026,
        )
        cls.outra_turma = Turma.objects.create(
            escola=cls.outra_escola, nome="1º A",
            turno=Turma.Turno.MATUTINO, ano_letivo=2026,
        )
        cls.aluno = Aluno.objects.create(
            escola=cls.escola, matricula="A1",
            nome_completo="Aluno Um", turma=cls.turma,
        )
        cls.aluno_outra_escola = Aluno.objects.create(
            escola=cls.outra_escola, matricula="B1",
            nome_completo="Aluno B", turma=cls.outra_turma,
        )
        cls.diretor = Usuario.objects.create_user(
            username="dir", password="x",
            perfil=Usuario.Perfil.DIRETOR, escola=cls.escola,
        )
        cls.secretaria = Usuario.objects.create_user(
            username="sec", password="x",
            perfil=Usuario.Perfil.SECRETARIA, escola=cls.escola,
        )
        cls.admin = Usuario.objects.create_user(
            username="adm", password="x", perfil=Usuario.Perfil.ADMIN
        )

    def setUp(self) -> None:
        self.client = APIClient()

    def _auth(self, user) -> None:
        token = RefreshToken.for_user(user).access_token
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def _url(self, aluno_id):
        return reverse("api_v1:boletim-aluno", kwargs={"aluno_id": aluno_id})

    def test_sem_token_401(self):
        resp = self.client.get(self._url(self.aluno.id))
        self.assertEqual(resp.status_code, 401)

    def test_secretaria_negada(self):
        self._auth(self.secretaria)
        resp = self.client.get(self._url(self.aluno.id))
        self.assertEqual(resp.status_code, 403)

    def test_diretor_acessa_aluno_da_propria_escola(self):
        self._auth(self.diretor)
        resp = self.client.get(self._url(self.aluno.id))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["aluno"]["id"], self.aluno.id)

    def test_diretor_nao_acessa_aluno_de_outra_escola(self):
        self._auth(self.diretor)
        resp = self.client.get(self._url(self.aluno_outra_escola.id))
        self.assertEqual(resp.status_code, 403)

    def test_admin_acessa_qualquer_aluno(self):
        self._auth(self.admin)
        resp = self.client.get(self._url(self.aluno_outra_escola.id))
        self.assertEqual(resp.status_code, 200)

    def test_aluno_inexistente_404(self):
        self._auth(self.admin)
        resp = self.client.get(self._url(999999))
        self.assertEqual(resp.status_code, 404)

    def test_data_inicio_invalida_400(self):
        self._auth(self.diretor)
        resp = self.client.get(
            self._url(self.aluno.id) + "?data_inicio=banana"
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("data_inicio", resp.data)
