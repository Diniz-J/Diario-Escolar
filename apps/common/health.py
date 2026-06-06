"""Endpoints de saúde do serviço — estilo Kubernetes liveness/readiness.

Dois endpoints públicos (sem auth — load balancer/uptime monitor precisa
bater sem token):

- `GET /api/v1/ping/` — **liveness**. Só responde 200 `{"status":"ok"}`.
  Não toca DB, cache, nem nada externo. Serve pra responder "o processo
  Python tá vivo e atendendo HTTP". Em K8s: `livenessProbe`.

- `GET /api/v1/health/` — **readiness**. Checa que o DB responde com
  `SELECT 1`. 200 se ok, 503 se falhou. Em K8s: `readinessProbe` (load
  balancer para de mandar tráfego). Em uptime monitors (UptimeRobot,
  Better Stack), use este — alarme dispara só quando o serviço de
  verdade tá com problema, não em deploy normal.

Por que dois endpoints (e não um só): se você usar o readiness pra
liveness, um Postgres lento causa pod restart loop em K8s. Em Render
free não tem K8s, mas o padrão escala.
"""
from __future__ import annotations

import logging

from django.db import DatabaseError, connection
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET

logger = logging.getLogger(__name__)


@csrf_exempt
@require_GET
def ping(_request):
    """Liveness — processo tá vivo. Sub-milissegundo, sem I/O externo."""
    return JsonResponse({"status": "ok"})


@csrf_exempt
@require_GET
def health(_request):
    """Readiness — checa que o DB responde. 503 se Postgres caiu.

    `SELECT 1` é o probe canônico: barato, sem dependência de schema.
    Catch genérico (`Exception`) porque psycopg pode levantar várias
    classes diferentes (DatabaseError, OperationalError, InterfaceError)
    dependendo do tipo de falha — o que importa pro load balancer é só
    "DB respondeu ou não".
    """
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except (DatabaseError, Exception) as exc:  # noqa: BLE001 — ver docstring
        logger.warning("health check falhou no DB: %s", exc)
        return JsonResponse(
            {"status": "error", "database": "down", "detail": str(exc)},
            status=503,
        )
    return JsonResponse({"status": "ok", "database": "ok"})
