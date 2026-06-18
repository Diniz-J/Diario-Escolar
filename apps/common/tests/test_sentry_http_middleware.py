"""Testes do SentryHttpErrorMiddleware — matriz de status codes.

Sem Sentry real: mockamos o `sentry_sdk` do módulo do middleware e
verificamos quando `capture_message` é (ou não) chamado.
"""
from unittest import mock

from django.http import HttpResponse
from django.test import RequestFactory, TestCase, override_settings

from apps.common.middleware import SentryHttpErrorMiddleware


class SentryHttpErrorMiddlewareTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def _rodar(self, status_code):
        """Roda o middleware com Sentry ativo (mockado) e devolve o mock."""
        request = self.factory.get("/api/v1/qualquer/")

        def get_response(_req):
            return HttpResponse(status=status_code)

        middleware = SentryHttpErrorMiddleware(get_response)
        with mock.patch("apps.common.middleware.sentry_sdk") as sentry:
            sentry.get_client.return_value.is_active.return_value = True
            resp = middleware(request)
        self.assertEqual(resp.status_code, status_code)
        return sentry

    @override_settings(SENTRY_IGNORE_STATUS_CODES={401})
    def test_4xx_reportado(self):
        for code in (400, 403, 404, 422):
            with self.subTest(code=code):
                sentry = self._rodar(code)
                sentry.capture_message.assert_called_once()

    @override_settings(SENTRY_IGNORE_STATUS_CODES={401})
    def test_401_ignorado(self):
        sentry = self._rodar(401)
        sentry.capture_message.assert_not_called()

    @override_settings(SENTRY_IGNORE_STATUS_CODES={401})
    def test_2xx_nao_reporta(self):
        sentry = self._rodar(200)
        sentry.capture_message.assert_not_called()

    @override_settings(SENTRY_IGNORE_STATUS_CODES={401})
    def test_5xx_fica_com_a_integracao(self):
        """5xx é capturado pela DjangoIntegration; o middleware não duplica."""
        sentry = self._rodar(500)
        sentry.capture_message.assert_not_called()

    @override_settings(SENTRY_IGNORE_STATUS_CODES={401, 404})
    def test_lista_de_exclusao_configuravel(self):
        sentry = self._rodar(404)
        sentry.capture_message.assert_not_called()

    def test_no_op_quando_sentry_inativo(self):
        """Sem cliente ativo (sem DSN) não tenta montar/enviar evento."""
        request = self.factory.get("/api/v1/qualquer/")

        def get_response(_req):
            return HttpResponse(status=400)

        middleware = SentryHttpErrorMiddleware(get_response)
        with mock.patch("apps.common.middleware.sentry_sdk") as sentry:
            sentry.get_client.return_value.is_active.return_value = False
            middleware(request)
            sentry.capture_message.assert_not_called()
