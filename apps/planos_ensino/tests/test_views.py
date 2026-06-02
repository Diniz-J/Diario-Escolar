"""Testes do `PlanoEnsinoViewSet`."""
from rest_framework.test import APIRequestFactory, force_authenticate

from django.test import TestCase

from apps.accounts.models import Usuario
from apps.escola.models import Disciplina, Escola, Turma
from apps.planos_ensino.models import PlanoEnsino
from apps.planos_ensino.views import PlanoEnsinoViewSet


class _Setup(TestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        cls.factory = APIRequestFactory()
        cls.escola = Escola.objects.create(nome="Escola")
        cls.turma = Turma.objects.create(
            escola=cls.escola, nome="1º A",
            turno=Turma.Turno.MATUTINO, ano_letivo=2026,
        )
        cls.disc = Disciplina.objects.create(escola=cls.escola, nome="Mat")
        cls.usuarios = {
            "admin": Usuario.objects.create_user(
                username="adm", password="x", perfil=Usuario.Perfil.ADMIN
            ),
            "diretor": Usuario.objects.create_user(
                username="dir", password="x",
                perfil=Usuario.Perfil.DIRETOR, escola=cls.escola,
            ),
            "professor": Usuario.objects.create_user(
                username="prof", password="x",
                perfil=Usuario.Perfil.PROFESSOR, escola=cls.escola,
            ),
            "inspetor": Usuario.objects.create_user(
                username="ins", password="x",
                perfil=Usuario.Perfil.INSPETOR, escola=cls.escola,
            ),
            "secretaria": Usuario.objects.create_user(
                username="sec", password="x",
                perfil=Usuario.Perfil.SECRETARIA, escola=cls.escola,
            ),
        }


class PermissionsTests(_Setup):
    def _list(self, perfil):
        req = self.factory.get("/")
        force_authenticate(req, user=self.usuarios[perfil])
        return PlanoEnsinoViewSet.as_view({"get": "list"})(req)

    def _create(self, perfil):
        req = self.factory.post(
            "/",
            {
                "escola": self.escola.id,
                "turma": self.turma.id,
                "disciplina": self.disc.id,
                "ano_letivo": 2026,
            },
            format="json",
        )
        force_authenticate(req, user=self.usuarios[perfil])
        return PlanoEnsinoViewSet.as_view({"post": "create"})(req)

    def test_inspetor_le(self):
        self.assertEqual(self._list("inspetor").status_code, 200)

    def test_inspetor_escreve(self):
        """Alias de professor — lança plano."""
        self.assertEqual(self._create("inspetor").status_code, 201)

    def test_professor_escreve(self):
        self.assertEqual(self._create("professor").status_code, 201)

    def test_secretaria_aceito_em_tudo(self):
        """Alias de diretor — lê e escreve."""
        self.assertEqual(self._list("secretaria").status_code, 200)
        self.assertEqual(self._create("secretaria").status_code, 201)


class ValidationTests(_Setup):
    def _create(self, perfil, payload):
        req = self.factory.post("/", payload, format="json")
        force_authenticate(req, user=self.usuarios[perfil])
        return PlanoEnsinoViewSet.as_view({"post": "create"})(req)

    def test_ano_letivo_inconsistente_falha(self):
        resp = self._create("diretor", {
            "escola": self.escola.id,
            "turma": self.turma.id,
            "disciplina": self.disc.id,
            "ano_letivo": 2027,  # turma é 2026
        })
        self.assertEqual(resp.status_code, 400)
        self.assertIn("ano_letivo", resp.data)


class CrossEscolaIDORTests(TestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        cls.factory = APIRequestFactory()
        cls.escola_a = Escola.objects.create(nome="A")
        cls.escola_b = Escola.objects.create(nome="B")
        cls.turma_b = Turma.objects.create(
            escola=cls.escola_b, nome="1B",
            turno=Turma.Turno.MATUTINO, ano_letivo=2026,
        )
        cls.disc_b = Disciplina.objects.create(escola=cls.escola_b, nome="Mat")
        cls.diretor_a = Usuario.objects.create_user(
            username="da", password="x",
            perfil=Usuario.Perfil.DIRETOR, escola=cls.escola_a,
        )

    def test_diretor_a_nao_cria_em_b(self):
        req = self.factory.post(
            "/",
            {
                "escola": self.escola_b.id,
                "turma": self.turma_b.id,
                "disciplina": self.disc_b.id,
                "ano_letivo": 2026,
            },
            format="json",
        )
        force_authenticate(req, user=self.diretor_a)
        resp = PlanoEnsinoViewSet.as_view({"post": "create"})(req)
        self.assertEqual(resp.status_code, 400)
        self.assertIn("escola", resp.data)
