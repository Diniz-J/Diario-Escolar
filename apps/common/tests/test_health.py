"""Testes dos endpoints `/api/v1/ping/` e `/api/v1/health/`."""
from __future__ import annotations

from unittest.mock import patch

from django.db import DatabaseError
from django.test import TestCase
from django.urls import reverse


class PingTests(TestCase):
    def test_200_publico(self):
        """Sem auth, sem nada — responde 200."""
        resp = self.client.get(reverse("api_v1:ping"))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {"status": "ok"})

    def test_405_metodo_errado(self):
        """`require_GET` rejeita POST."""
        resp = self.client.post(reverse("api_v1:ping"))
        self.assertEqual(resp.status_code, 405)


class HealthTests(TestCase):
    def test_200_com_db_ok(self):
        """DB respondeu o SELECT 1 — readiness ok."""
        resp = self.client.get(reverse("api_v1:health"))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {"status": "ok", "database": "ok"})

    @patch("apps.common.health.connection")
    def test_503_quando_db_falha(self, mock_connection):
        """DB recusou conexão — 503 com detalhe."""
        # Simula falha do cursor (psycopg pode levantar OperationalError,
        # InterfaceError, etc — testamos com DatabaseError genérico).
        mock_connection.cursor.side_effect = DatabaseError("connection refused")

        resp = self.client.get(reverse("api_v1:health"))
        self.assertEqual(resp.status_code, 503)
        body = resp.json()
        self.assertEqual(body["status"], "error")
        self.assertEqual(body["database"], "down")
        self.assertIn("connection refused", body["detail"])

    def test_405_metodo_errado(self):
        resp = self.client.post(reverse("api_v1:health"))
        self.assertEqual(resp.status_code, 405)
