"""Proxy `tunnel` do Sentry pra contornar adblockers do cliente.

Background: adblockers populares (Opera built-in, uBlock, Brave Shield)
bloqueiam requisições pra `*.ingest.sentry.io` por reputação — alguns
sites usam Sentry pra telemetria invasiva. Resultado: erros de usuários
com adblocker somem silenciosamente do nosso painel.

Solução padrão recomendada pelo Sentry: o frontend manda o envelope
pra um endpoint do **nosso próprio domínio** (`/api/v1/_sentry/`), que
faz proxy pro Sentry. Como o host não é Sentry, adblocker não bloqueia.

Esta view é o proxy. Pra evitar virar relay aberto pra qualquer
projeto Sentry no mundo (alguém poderia abusar do endpoint pra mandar
erros falsos pra QUALQUER painel Sentry), validamos o envelope contra
whitelist em settings:

- `SENTRY_TUNNEL_HOST`: host único permitido (ex.: `o4511493890572288.ingest.us.sentry.io`).
- `SENTRY_TUNNEL_PROJECT_IDS`: lista CSV de project_ids permitidos.

Sem essas envs setadas, o endpoint devolve 503 (não vira proxy aberto).
"""
from __future__ import annotations

import json
import logging
from urllib.parse import urlparse

import requests
from django.conf import settings
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

logger = logging.getLogger(__name__)


@csrf_exempt
@require_POST
def sentry_tunnel(request):
    """`POST /api/v1/_sentry/` — proxy do envelope pro Sentry.

    Espera body `application/x-sentry-envelope`. Valida o header
    (primeira linha — JSON com a DSN) contra a whitelist e reencaminha
    pro `ingest.us.sentry.io`. Falhas silenciosas no upstream viram log
    (sem propagar erro pro frontend — não queremos quebrar UX por causa
    de telemetria).
    """
    host_permitido: str = getattr(settings, "SENTRY_TUNNEL_HOST", "") or ""
    projects_permitidos: list[str] = (
        getattr(settings, "SENTRY_TUNNEL_PROJECT_IDS", []) or []
    )

    if not host_permitido or not projects_permitidos:
        # Endpoint desabilitado por config. Retorna 503 explícito pro
        # frontend saber que o tunnel não tá ativo e cair pro modo
        # direto (que pode ser bloqueado por adblock, mas é tudo que
        # podemos fazer).
        return HttpResponse(
            "Tunnel não configurado (faltam SENTRY_TUNNEL_HOST/PROJECT_IDS).",
            status=503,
        )

    envelope = request.body
    if not envelope:
        return HttpResponse("Envelope vazio.", status=400)

    # Primeira linha do envelope é o header (JSON) com a DSN do projeto
    # de origem. Sentry SDK garante esse formato quando `tunnel` está
    # ativo no init.
    try:
        header_line = envelope.split(b"\n", 1)[0]
        header = json.loads(header_line.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return HttpResponse("Envelope malformado.", status=400)

    dsn = header.get("dsn")
    if not dsn:
        return HttpResponse("DSN ausente no envelope.", status=400)

    parsed = urlparse(dsn)
    if parsed.hostname != host_permitido:
        return HttpResponse(
            f"Host '{parsed.hostname}' fora da whitelist.", status=400
        )

    project_id = parsed.path.strip("/")
    if project_id not in projects_permitidos:
        return HttpResponse(
            f"Projeto '{project_id}' fora da whitelist.", status=400
        )

    upstream_url = f"https://{host_permitido}/api/{project_id}/envelope/"
    try:
        resp = requests.post(
            upstream_url,
            data=envelope,
            headers={"Content-Type": "application/x-sentry-envelope"},
            timeout=5,
        )
    except requests.RequestException as exc:
        # Sentry fora do ar não pode quebrar UX do usuário — log e
        # devolve 502 sem detalhes. O frontend ignora a resposta
        # mesmo (telemetria fire-and-forget).
        logger.warning("sentry tunnel upstream falhou: %s", exc)
        return HttpResponse("Upstream Sentry indisponível.", status=502)

    return HttpResponse(
        resp.content,
        status=resp.status_code,
        content_type=resp.headers.get("Content-Type", "application/json"),
    )
