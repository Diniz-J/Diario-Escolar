"""Testes da autenticação isolada do portal (fatia 2 do `PORTAL.md`).

Os primeiros testes são a separação entre os dois mundos (seção 4.1): token
de cada lado recusado no outro, nos dois sentidos, e token forjado
recusado nos dois. Depois vêm login, refresh, logout e rate limit.
"""
from unittest import mock

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework.throttling import ScopedRateThrottle
from rest_framework_simplejwt.token_blacklist.models import OutstandingToken
from rest_framework_simplejwt.tokens import AccessToken, UntypedToken

from apps.accounts.models import Usuario
from apps.common.authentication import CLAIM_TIPO, TIPO_RESPONSAVEL
from apps.escola.models import Escola
from apps.portal.models import Responsavel
from apps.portal.tokens import CLAIM_RESPONSAVEL_ID, PortalRefreshToken

SENHA = "senha-do-responsavel-123"
SENHA_STAFF = "senha-super-segura-123"

URL_LOGIN = reverse("api_v1:portal_login")
URL_REFRESH = reverse("api_v1:portal_refresh")
URL_LOGOUT = reverse("api_v1:portal_logout")
URL_ME = reverse("api_v1:portal_me")
URL_STAFF_LOGIN = reverse("api_v1:token_obtain_pair")
URL_STAFF_REFRESH = reverse("api_v1:token_refresh")
URL_STAFF_LOGOUT = reverse("api_v1:logout")
URL_STAFF = reverse("api_v1:turma-list")


class _PortalAuthSetup(TestCase):
    """Helpers sem testes, pra subclasse não herdar teste do pai."""

    @classmethod
    def setUpTestData(cls) -> None:
        cls.escola = Escola.objects.create(nome="Escola A")
        cls.outra_escola = Escola.objects.create(nome="Escola B")
        cls.responsavel = cls._responsavel(cls.escola, "maria@example.com")
        # Staff com o MESMO pk do responsável: é o alvo do risco central —
        # um token do portal resolvido contra `Usuario` cairia nele.
        # pk forçado: a sequência do Postgres não volta entre testes.
        cls.staff = Usuario.objects.create_user(
            id=cls.responsavel.pk,
            username="diretora",
            password=SENHA_STAFF,
            perfil=Usuario.Perfil.DIRETOR,
            escola=cls.escola,
        )

    @staticmethod
    def _responsavel(escola, email, senha=SENHA, ativo=True):
        r = Responsavel(escola=escola, email=email, nome="Maria", ativo=ativo)
        if senha is None:
            r.set_unusable_password()
        else:
            r.set_password(senha)
        r.save()
        return r

    def setUp(self) -> None:
        self.client = APIClient()

    def _login_portal(self, email="maria@example.com", senha=SENHA):
        return self.client.post(
            URL_LOGIN, {"email": email, "password": senha}, format="json"
        )

    def _tokens_portal(self):
        resp = self._login_portal()
        self.assertEqual(resp.status_code, 200, resp.data)
        return resp.data["access"], resp.data["refresh"]

    def _tokens_staff(self):
        resp = self.client.post(
            URL_STAFF_LOGIN,
            {"username": "diretora", "password": SENHA_STAFF},
            format="json",
        )
        self.assertEqual(resp.status_code, 200, resp.data)
        return resp.data["access"], resp.data["refresh"]

    def _get(self, url, access):
        return self.client.get(url, HTTP_AUTHORIZATION=f"Bearer {access}")


class SeparacaoDeTokenTests(_PortalAuthSetup):
    """`PORTAL.md`, seção 4.1 — o primeiro requisito da fatia."""

    def test_pks_coincidem_no_cenario_de_teste(self):
        # Pré-condição dos testes abaixo: sem isso, a recusa poderia passar
        # só porque o pk não existe do outro lado.
        self.assertEqual(self.responsavel.pk, self.staff.pk)

    def test_access_do_portal_e_recusado_no_staff(self):
        access, _ = self._tokens_portal()
        self.assertEqual(self._get(URL_STAFF, access).status_code, 401)

    def test_access_do_staff_e_recusado_no_portal(self):
        access, _ = self._tokens_staff()
        self.assertEqual(self._get(URL_ME, access).status_code, 401)

    def test_staff_continua_funcionando_com_o_proprio_token(self):
        access, _ = self._tokens_staff()
        self.assertEqual(self._get(URL_STAFF, access).status_code, 200)

    def test_token_sem_claim_de_tipo_e_recusado_no_portal(self):
        token = AccessToken()
        token[CLAIM_RESPONSAVEL_ID] = str(self.responsavel.pk)
        self.assertEqual(self._get(URL_ME, str(token)).status_code, 401)

    def test_token_com_tipo_e_user_id_e_recusado_nos_dois(self):
        """Forjado com os dois ids: não vale em lado nenhum."""
        token = AccessToken()
        token[CLAIM_TIPO] = TIPO_RESPONSAVEL
        token[CLAIM_RESPONSAVEL_ID] = str(self.responsavel.pk)
        token["user_id"] = str(self.staff.pk)
        self.assertEqual(self._get(URL_STAFF, str(token)).status_code, 401)
        self.assertEqual(self._get(URL_ME, str(token)).status_code, 401)

    def test_token_com_tipo_sem_id_do_responsavel_e_recusado(self):
        token = AccessToken()
        token[CLAIM_TIPO] = TIPO_RESPONSAVEL
        self.assertEqual(self._get(URL_ME, str(token)).status_code, 401)

    def test_id_nao_numerico_e_recusado_com_401_e_nao_500(self):
        """Com id não numérico, a busca do responsável levantaria
        `ValueError` — o refresh devolvia 500."""
        token = PortalRefreshToken()
        token[CLAIM_TIPO] = TIPO_RESPONSAVEL
        token[CLAIM_RESPONSAVEL_ID] = "abc"
        resp = self.client.post(URL_REFRESH, {"refresh": str(token)}, format="json")
        self.assertEqual(resp.status_code, 401)
        self.assertEqual(self._get(URL_ME, str(token.access_token)).status_code, 401)

    def test_refresh_do_portal_e_recusado_no_refresh_do_staff(self):
        _, refresh = self._tokens_portal()
        resp = self.client.post(
            URL_STAFF_REFRESH, {"refresh": refresh}, format="json"
        )
        self.assertEqual(resp.status_code, 401)

    def test_refresh_do_staff_e_recusado_no_refresh_do_portal(self):
        _, refresh = self._tokens_staff()
        resp = self.client.post(URL_REFRESH, {"refresh": refresh}, format="json")
        self.assertEqual(resp.status_code, 401)

    def test_logout_do_staff_nao_invalida_refresh_do_portal(self):
        """O logout do staff usava `RefreshToken` cru e blacklistava o
        refresh do portal — contradizia "cada lado recusa o token do outro"."""
        access_staff, _ = self._tokens_staff()
        _, refresh_portal = self._tokens_portal()
        resp = self.client.post(
            URL_STAFF_LOGOUT,
            {"refresh": refresh_portal},
            format="json",
            HTTP_AUTHORIZATION=f"Bearer {access_staff}",
        )
        self.assertEqual(resp.status_code, 205)
        # O refresh do portal segue válido: o logout do staff não agiu nele.
        resp = self.client.post(URL_REFRESH, {"refresh": refresh_portal}, format="json")
        self.assertEqual(resp.status_code, 200)

    def test_token_do_portal_nao_liga_ao_usuario_na_blacklist(self):
        """O `OutstandingToken` tem FK pro `Usuario`: tem que ficar nula."""
        _, refresh = self._tokens_portal()
        jti = UntypedToken(refresh)["jti"]
        self.assertIsNone(OutstandingToken.objects.get(jti=jti).user)


class LoginTests(_PortalAuthSetup):
    def test_login_valido_devolve_tokens_e_me_responde(self):
        access, _ = self._tokens_portal()
        resp = self._get(URL_ME, access)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["id"], self.responsavel.pk)
        self.assertEqual(resp.data["escola_id"], self.escola.pk)

    def test_email_e_normalizado_no_login(self):
        resp = self._login_portal(email="  MARIA@Example.com ")
        self.assertEqual(resp.status_code, 200)

    def test_falhas_devolvem_o_mesmo_erro_generico(self):
        """Senha errada, email inexistente, conta inativa e conta sem senha
        respondem igual — diferenciar revelaria quais emails têm conta."""
        self._responsavel(self.escola, "inativa@example.com", ativo=False)
        self._responsavel(self.escola, "semsenha@example.com", senha=None)
        casos = [
            ("maria@example.com", "errada"),
            ("ninguem@example.com", SENHA),
            ("inativa@example.com", SENHA),
            ("semsenha@example.com", "qualquer-coisa"),
        ]
        respostas = [self._login_portal(e, s) for e, s in casos]
        self.assertEqual({r.status_code for r in respostas}, {401})
        self.assertEqual(len({str(r.data["detail"]) for r in respostas}), 1)

    def test_conta_sem_senha_tambem_roda_hash(self):
        """Sem o hash, a conta semeada (sem senha até o convite) respondia
        mais rápido que email inexistente — enumeração de pais por tempo."""
        self._responsavel(self.escola, "semeada@example.com", senha=None)
        with mock.patch.object(
            Responsavel, "set_password", autospec=True
        ) as hash_ficticio:
            resp = self._login_portal("semeada@example.com", "qualquer-coisa")
        self.assertEqual(resp.status_code, 401)
        hash_ficticio.assert_called_once()

    def test_mesmo_email_em_duas_escolas_entra_na_da_senha_certa(self):
        outra = self._responsavel(
            self.outra_escola, "maria@example.com", senha="outra-senha-456"
        )
        access = self._login_portal(senha="outra-senha-456").data["access"]
        self.assertEqual(self._get(URL_ME, access).data["id"], outra.pk)

    def test_mesmo_email_e_senha_em_duas_escolas_e_recusado(self):
        self._responsavel(self.outra_escola, "maria@example.com")
        self.assertEqual(self._login_portal().status_code, 409)


class SessaoTests(_PortalAuthSetup):
    def test_refresh_rotaciona_e_invalida_o_anterior(self):
        _, refresh = self._tokens_portal()
        resp = self.client.post(URL_REFRESH, {"refresh": refresh}, format="json")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(self._get(URL_ME, resp.data["access"]).status_code, 200)
        # O refresh antigo foi pra blacklist na rotação.
        resp = self.client.post(URL_REFRESH, {"refresh": refresh}, format="json")
        self.assertEqual(resp.status_code, 401)

    def test_conta_desativada_perde_acesso_e_refresh(self):
        access, refresh = self._tokens_portal()
        Responsavel.objects.filter(pk=self.responsavel.pk).update(ativo=False)
        self.assertEqual(self._get(URL_ME, access).status_code, 401)
        resp = self.client.post(URL_REFRESH, {"refresh": refresh}, format="json")
        self.assertEqual(resp.status_code, 401)

    def test_logout_invalida_o_refresh(self):
        access, refresh = self._tokens_portal()
        resp = self.client.post(
            URL_LOGOUT,
            {"refresh": refresh},
            format="json",
            HTTP_AUTHORIZATION=f"Bearer {access}",
        )
        self.assertEqual(resp.status_code, 205)
        resp = self.client.post(URL_REFRESH, {"refresh": refresh}, format="json")
        self.assertEqual(resp.status_code, 401)

    def test_logout_exige_token_do_portal(self):
        access, refresh = self._tokens_staff()
        resp = self.client.post(
            URL_LOGOUT,
            {"refresh": refresh},
            format="json",
            HTTP_AUTHORIZATION=f"Bearer {access}",
        )
        self.assertEqual(resp.status_code, 401)


class PortalLoginThrottleTests(_PortalAuthSetup):
    """Brute force no login do portal é barrado, em bucket próprio.

    Mesmo truque do `LoginThrottleTests` do staff: o DRF captura os rates
    no import, então forçamos direto no atributo de classe.
    """

    def setUp(self) -> None:
        super().setUp()
        cache.clear()
        self._rate_original = ScopedRateThrottle.THROTTLE_RATES
        ScopedRateThrottle.THROTTLE_RATES = {
            "portal_login": "5/min",
            "login": "5/min",
        }

    def tearDown(self) -> None:
        cache.clear()
        ScopedRateThrottle.THROTTLE_RATES = self._rate_original

    def test_sexta_tentativa_no_minuto_retorna_429(self):
        for _ in range(5):
            self.assertEqual(self._login_portal(senha="errada").status_code, 401)
        self.assertEqual(self._login_portal(senha="errada").status_code, 429)

    def test_bloqueio_do_portal_nao_bloqueia_o_login_do_staff(self):
        for _ in range(6):
            self._login_portal(senha="errada")
        access, _ = self._tokens_staff()
        self.assertTrue(access)
