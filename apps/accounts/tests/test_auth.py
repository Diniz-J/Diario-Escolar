"""Smoke tests do JWT (custom claims) e do roteamento global `/api/v1/`.

Estes testes são os primeiros que exercitam o roteamento real (via
`reverse()` e `APIClient`), em vez de chamar ViewSets diretamente. São
intencionalmente abrangentes — qualquer regressão no wiring deve falhar
aqui.
"""
import jwt
from django.conf import settings
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.models import Usuario
from apps.escola.models import Escola


class TokenObtainTests(TestCase):
    """`/api/v1/auth/token/` — credenciais e claims customizados."""

    @classmethod
    def setUpTestData(cls) -> None:
        cls.escola = Escola.objects.create(nome="Escola Teste")
        cls.usuario = Usuario.objects.create_user(
            username="diretor1",
            password="senha-super-segura-123",
            perfil=Usuario.Perfil.DIRETOR,
            escola=cls.escola,
            first_name="Rodrigo",
            last_name="Diniz",
        )

    def setUp(self) -> None:
        self.client = APIClient()
        self.url = reverse("api_v1:token_obtain_pair")

    def test_credenciais_validas_retornam_par_de_tokens(self):
        resp = self.client.post(
            self.url,
            {"username": "diretor1", "password": "senha-super-segura-123"},
            format="json",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn("access", resp.data)
        self.assertIn("refresh", resp.data)

    def test_credenciais_invalidas_401(self):
        resp = self.client.post(
            self.url,
            {"username": "diretor1", "password": "senha-errada"},
            format="json",
        )
        self.assertEqual(resp.status_code, 401)

    def test_username_inexistente_401(self):
        resp = self.client.post(
            self.url,
            {"username": "ninguem", "password": "qualquer"},
            format="json",
        )
        self.assertEqual(resp.status_code, 401)

    def test_payload_contem_escola_id_e_perfil(self):
        """Custom claims: o frontend lê escopo e perfil do próprio JWT."""
        resp = self.client.post(
            self.url,
            {"username": "diretor1", "password": "senha-super-segura-123"},
            format="json",
        )
        self.assertEqual(resp.status_code, 200)
        # Decodifica sem verificar assinatura — o objetivo aqui é só checar
        # o payload, não a integridade do token (SimpleJWT cuida disso).
        access = resp.data["access"]
        payload = jwt.decode(access, options={"verify_signature": False})
        self.assertEqual(payload["escola_id"], self.escola.id)
        self.assertEqual(payload["perfil"], Usuario.Perfil.DIRETOR)

    def test_payload_contem_dados_de_identidade(self):
        """Claims de identidade: username + first_name + last_name no JWT."""
        resp = self.client.post(
            self.url,
            {"username": "diretor1", "password": "senha-super-segura-123"},
            format="json",
        )
        self.assertEqual(resp.status_code, 200)
        payload = jwt.decode(
            resp.data["access"], options={"verify_signature": False}
        )
        self.assertEqual(payload["username"], "diretor1")
        self.assertEqual(payload["first_name"], "Rodrigo")
        self.assertEqual(payload["last_name"], "Diniz")

    def test_payload_admin_sem_escola_tem_escola_id_none(self):
        """Admin sem escola vinculada (bypass legítimo) reflete no claim."""
        admin = Usuario.objects.create_user(
            username="adm", password="x123x123x", perfil=Usuario.Perfil.ADMIN
        )
        self.assertIsNone(admin.escola_id)
        resp = self.client.post(
            self.url, {"username": "adm", "password": "x123x123x"}, format="json"
        )
        payload = jwt.decode(resp.data["access"], options={"verify_signature": False})
        self.assertIsNone(payload["escola_id"])
        self.assertEqual(payload["perfil"], Usuario.Perfil.ADMIN)


class TokenRefreshTests(TestCase):
    """`/api/v1/auth/token/refresh/` — troca refresh por novo access."""

    @classmethod
    def setUpTestData(cls) -> None:
        cls.escola = Escola.objects.create(nome="Escola Teste Refresh")
        cls.usuario = Usuario.objects.create_user(
            username="prof1",
            password="senha-super-segura-123",
            perfil=Usuario.Perfil.PROFESSOR,
            escola=cls.escola,
            first_name="Maria",
            last_name="Silva",
        )

    def setUp(self) -> None:
        self.client = APIClient()

    def test_refresh_valido_gera_novo_access(self):
        obtain = self.client.post(
            reverse("api_v1:token_obtain_pair"),
            {"username": "prof1", "password": "senha-super-segura-123"},
            format="json",
        )
        refresh_token = obtain.data["refresh"]

        resp = self.client.post(
            reverse("api_v1:token_refresh"),
            {"refresh": refresh_token},
            format="json",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn("access", resp.data)

    def test_refresh_invalido_401(self):
        resp = self.client.post(
            reverse("api_v1:token_refresh"),
            {"refresh": "isso-nao-e-um-token"},
            format="json",
        )
        self.assertEqual(resp.status_code, 401)

    def test_refresh_preserva_custom_claims_no_novo_access(self):
        """Trava o contrato: claims customizados sobrevivem ao refresh.

        SimpleJWT 5.x copia o payload do refresh pro novo access. Este
        teste protege o frontend caso alguém habilite `ROTATE_REFRESH_TOKENS`
        ou troque o serializer do refresh — qualquer regressão silenciosa
        ali quebra a leitura de `escola_id`/`perfil` no app cliente.
        """
        obtain = self.client.post(
            reverse("api_v1:token_obtain_pair"),
            {"username": "prof1", "password": "senha-super-segura-123"},
            format="json",
        )
        refresh_token = obtain.data["refresh"]

        resp = self.client.post(
            reverse("api_v1:token_refresh"),
            {"refresh": refresh_token},
            format="json",
        )
        self.assertEqual(resp.status_code, 200)
        novo_access = resp.data["access"]
        payload = jwt.decode(novo_access, options={"verify_signature": False})
        self.assertEqual(payload["escola_id"], self.escola.id)
        self.assertEqual(payload["perfil"], Usuario.Perfil.PROFESSOR)
        # Claims de identidade também devem persistir.
        self.assertEqual(payload["username"], "prof1")
        self.assertEqual(payload["first_name"], "Maria")
        self.assertEqual(payload["last_name"], "Silva")


class ApiV1RoutingTests(TestCase):
    """Smoke tests do wiring: endpoints respondem e exigem auth."""

    @classmethod
    def setUpTestData(cls) -> None:
        cls.escola = Escola.objects.create(nome="Escola Teste")
        cls.admin = Usuario.objects.create_user(
            username="adm", password="x123x123x", perfil=Usuario.Perfil.ADMIN
        )

    def setUp(self) -> None:
        self.client = APIClient()

    def _bearer(self, user) -> str:
        from rest_framework_simplejwt.tokens import RefreshToken

        token = RefreshToken.for_user(user).access_token
        return f"Bearer {token}"

    def test_endpoint_sem_token_401(self):
        resp = self.client.get("/api/v1/escolas/")
        self.assertEqual(resp.status_code, 401)

    def test_endpoint_com_token_200(self):
        self.client.credentials(HTTP_AUTHORIZATION=self._bearer(self.admin))
        resp = self.client.get("/api/v1/escolas/")
        self.assertEqual(resp.status_code, 200)

    def test_todos_os_dominios_montados(self):
        """Garante que todos os routers das apps estão acessíveis sob /api/v1/."""
        self.client.credentials(HTTP_AUTHORIZATION=self._bearer(self.admin))
        for path in (
            "/api/v1/usuarios/",
            "/api/v1/escolas/",
            "/api/v1/turmas/",
            "/api/v1/disciplinas/",
            "/api/v1/alunos/",
            "/api/v1/professores/",
            "/api/v1/ocorrencias/",
            "/api/v1/registros-presenca/",
            # itens-presenca exige filtro de escopo no list
            # (FiltroEscopoObrigatorioMixin) — passa `?aluno=` só pra valer.
            "/api/v1/itens-presenca/?aluno=1",
        ):
            resp = self.client.get(path)
            self.assertEqual(
                resp.status_code, 200,
                f"Endpoint {path} retornou {resp.status_code}",
            )

    def test_token_obtido_via_api_funciona_em_endpoint_protegido(self):
        """Fluxo end-to-end: obter token via /auth/token/, usar em /escolas/."""
        obtain = self.client.post(
            reverse("api_v1:token_obtain_pair"),
            {"username": "adm", "password": "x123x123x"},
            format="json",
        )
        access = obtain.data["access"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
        resp = self.client.get("/api/v1/escolas/")
        self.assertEqual(resp.status_code, 200)
