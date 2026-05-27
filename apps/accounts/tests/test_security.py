"""Testes de segurança de autenticação: logout (blacklist) e rate limit.

O rate limit de login fica desligado no resto da suíte (settings.TESTING);
aqui reativamos o rate via override_settings e limpamos o cache para
exercitar o bloqueio de forma isolada e determinística.
"""
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework.throttling import ScopedRateThrottle

from apps.accounts.models import Usuario
from apps.escola.models import Escola


class LogoutBlacklistTests(TestCase):
    """`/api/v1/auth/logout/` invalida o refresh token."""

    @classmethod
    def setUpTestData(cls) -> None:
        cls.escola = Escola.objects.create(nome="Escola Teste")
        cls.usuario = Usuario.objects.create_user(
            username="prof1",
            password="senha-super-segura-123",
            perfil=Usuario.Perfil.PROFESSOR,
            escola=cls.escola,
        )

    def setUp(self) -> None:
        self.client = APIClient()
        resp = self.client.post(
            reverse("api_v1:token_obtain_pair"),
            {"username": "prof1", "password": "senha-super-segura-123"},
            format="json",
        )
        self.access = resp.data["access"]
        self.refresh = resp.data["refresh"]

    def test_logout_exige_autenticacao(self):
        resp = self.client.post(
            reverse("api_v1:logout"),
            {"refresh": self.refresh},
            format="json",
        )
        self.assertEqual(resp.status_code, 401)

    def test_logout_invalida_refresh(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.access}")
        resp = self.client.post(
            reverse("api_v1:logout"),
            {"refresh": self.refresh},
            format="json",
        )
        self.assertEqual(resp.status_code, 205)

        # O refresh agora está na blacklist: não gera mais access.
        nova = APIClient()
        resp_refresh = nova.post(
            reverse("api_v1:token_refresh"),
            {"refresh": self.refresh},
            format="json",
        )
        self.assertEqual(resp_refresh.status_code, 401)

    def test_logout_sem_refresh_400(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.access}")
        resp = self.client.post(reverse("api_v1:logout"), {}, format="json")
        self.assertEqual(resp.status_code, 400)


class LoginThrottleTests(TestCase):
    """Brute force no login é barrado após o limite de tentativas.

    O rate de login fica desligado na suíte (settings.TESTING). O DRF
    captura `ScopedRateThrottle.THROTTLE_RATES` no import do módulo, então
    `override_settings` não basta — forçamos o rate direto no atributo de
    classe e restauramos no tearDown. Em produção o rate "5/min" é o valor
    real (lá TESTING é False).
    """

    @classmethod
    def setUpTestData(cls) -> None:
        cls.escola = Escola.objects.create(nome="Escola Teste")
        Usuario.objects.create_user(
            username="alvo",
            password="senha-super-segura-123",
            perfil=Usuario.Perfil.DIRETOR,
            escola=cls.escola,
        )

    def setUp(self) -> None:
        # Cache limpo: o throttle guarda o histórico de tentativas no cache.
        cache.clear()
        # Força o rate na classe (ver docstring) e guarda o original.
        self._rate_original = ScopedRateThrottle.THROTTLE_RATES
        ScopedRateThrottle.THROTTLE_RATES = {"login": "5/min"}
        self.client = APIClient()
        self.url = reverse("api_v1:token_obtain_pair")

    def tearDown(self) -> None:
        cache.clear()
        ScopedRateThrottle.THROTTLE_RATES = self._rate_original

    def test_excesso_de_tentativas_retorna_429(self):
        # 5 tentativas (senha errada) são permitidas...
        for _ in range(5):
            resp = self.client.post(
                self.url,
                {"username": "alvo", "password": "errada"},
                format="json",
            )
            self.assertEqual(resp.status_code, 401)

        # ...a 6ª é bloqueada pelo rate limit.
        resp = self.client.post(
            self.url,
            {"username": "alvo", "password": "errada"},
            format="json",
        )
        self.assertEqual(resp.status_code, 429)
