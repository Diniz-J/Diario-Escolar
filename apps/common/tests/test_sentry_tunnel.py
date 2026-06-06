"""Testes do proxy `/api/v1/_sentry/` que tuneliza envelopes do frontend.

Cobre:
- 503 quando whitelist não configurada (envs vazias).
- 400 quando o envelope é malformado ou aponta host/projeto fora da whitelist.
- 200 quando válido — confere que `requests.post` é chamado com a URL upstream
  correta (mockado).
"""
from __future__ import annotations

import json
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.urls import reverse


HOST_VALIDO = "o4511493890572288.ingest.us.sentry.io"
PROJECT_VALIDO = "4511493892210688"
DSN_VALIDA = (
    f"https://c830f3b5006f2da719d05cb4866207a8@{HOST_VALIDO}/{PROJECT_VALIDO}"
)


def _envelope(dsn: str | None = DSN_VALIDA) -> bytes:
    """Monta um envelope mínimo no formato que o Sentry SDK enviaria."""
    header = {"event_id": "abc", "sent_at": "2026-06-06T00:00:00Z"}
    if dsn is not None:
        header["dsn"] = dsn
    return (
        json.dumps(header).encode()
        + b"\n"
        + b'{"type":"event"}\n'
        + b'{"message":"hi"}'
    )


class SentryTunnelTests(TestCase):
    def setUp(self) -> None:
        self.url = reverse("api_v1:sentry_tunnel")

    @override_settings(SENTRY_TUNNEL_HOST="", SENTRY_TUNNEL_PROJECT_IDS=[])
    def test_503_sem_whitelist(self):
        resp = self.client.post(
            self.url,
            data=_envelope(),
            content_type="application/x-sentry-envelope",
        )
        self.assertEqual(resp.status_code, 503)

    @override_settings(
        SENTRY_TUNNEL_HOST=HOST_VALIDO,
        SENTRY_TUNNEL_PROJECT_IDS=[PROJECT_VALIDO],
    )
    def test_400_envelope_vazio(self):
        resp = self.client.post(
            self.url, data=b"", content_type="application/x-sentry-envelope"
        )
        self.assertEqual(resp.status_code, 400)

    @override_settings(
        SENTRY_TUNNEL_HOST=HOST_VALIDO,
        SENTRY_TUNNEL_PROJECT_IDS=[PROJECT_VALIDO],
    )
    def test_400_sem_dsn_no_header(self):
        resp = self.client.post(
            self.url,
            data=_envelope(dsn=None),
            content_type="application/x-sentry-envelope",
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn(b"DSN ausente", resp.content)

    @override_settings(
        SENTRY_TUNNEL_HOST=HOST_VALIDO,
        SENTRY_TUNNEL_PROJECT_IDS=[PROJECT_VALIDO],
    )
    def test_400_host_fora_da_whitelist(self):
        dsn = f"https://k@evil.sentry.io/{PROJECT_VALIDO}"
        resp = self.client.post(
            self.url,
            data=_envelope(dsn=dsn),
            content_type="application/x-sentry-envelope",
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn(b"evil.sentry.io", resp.content)

    @override_settings(
        SENTRY_TUNNEL_HOST=HOST_VALIDO,
        SENTRY_TUNNEL_PROJECT_IDS=[PROJECT_VALIDO],
    )
    def test_400_project_fora_da_whitelist(self):
        dsn = f"https://k@{HOST_VALIDO}/99999999"
        resp = self.client.post(
            self.url,
            data=_envelope(dsn=dsn),
            content_type="application/x-sentry-envelope",
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn(b"99999999", resp.content)

    @override_settings(
        SENTRY_TUNNEL_HOST=HOST_VALIDO,
        SENTRY_TUNNEL_PROJECT_IDS=[PROJECT_VALIDO],
    )
    @patch("apps.common.sentry_tunnel.requests.post")
    def test_200_encaminha_pra_url_correta(self, mock_post):
        # Mock do upstream — retorna 200 sem nada.
        mock_post.return_value.status_code = 200
        mock_post.return_value.content = b'{"id":"xyz"}'
        mock_post.return_value.headers = {"Content-Type": "application/json"}

        envelope = _envelope()
        resp = self.client.post(
            self.url,
            data=envelope,
            content_type="application/x-sentry-envelope",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.content, b'{"id":"xyz"}')

        # Confere que o upstream foi chamado com URL e body certos.
        chamadas = mock_post.call_args_list
        self.assertEqual(len(chamadas), 1)
        url_chamada = chamadas[0].kwargs.get("url") or chamadas[0].args[0]
        self.assertEqual(
            url_chamada,
            f"https://{HOST_VALIDO}/api/{PROJECT_VALIDO}/envelope/",
        )
        self.assertEqual(chamadas[0].kwargs["data"], envelope)

    @override_settings(
        SENTRY_TUNNEL_HOST=HOST_VALIDO,
        SENTRY_TUNNEL_PROJECT_IDS=[PROJECT_VALIDO],
    )
    @patch("apps.common.sentry_tunnel.requests.post")
    def test_502_quando_upstream_falha(self, mock_post):
        import requests

        mock_post.side_effect = requests.RequestException("connection refused")
        resp = self.client.post(
            self.url,
            data=_envelope(),
            content_type="application/x-sentry-envelope",
        )
        self.assertEqual(resp.status_code, 502)

    def test_405_get_nao_aceito(self):
        # `require_POST` rejeita GET com 405.
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 405)
