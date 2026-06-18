"""Middlewares compartilhados do Diário Escolar."""
import logging

import sentry_sdk
from django.conf import settings
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import AccessToken

from apps.common.logging import escola_context

logger = logging.getLogger(__name__)


class EscolaLogContextMiddleware:
    """Pina o `escola_id` da request no contexto de logging.

    Lê o claim `escola_id` direto do JWT do header Authorization e o
    publica no `escola_context` (ContextVar), de onde o `EscolaLogFilter`
    carimba todo log da request. Assim o log total fica fatiável por
    escola num sistema multi-tenant.

    Decodifica o token aqui (e não via `request.user`) porque o SimpleJWT
    autentica no nível do DRF, dentro da view — `request.user` ainda não
    está populado no middleware. A validação é a mesma do DRF (assinatura +
    expiração via `AccessToken`), sem hit no banco (o claim já vem no token).

    Best-effort: qualquer falha na leitura do token apenas deixa o contexto
    sem escola (log com `escola_id=None`); NUNCA interrompe a request.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        token = escola_context.set(self._extrair_escola_id(request))
        try:
            return self.get_response(request)
        finally:
            escola_context.reset(token)

    @staticmethod
    def _extrair_escola_id(request):
        header = request.META.get("HTTP_AUTHORIZATION", "")
        if not header.startswith("Bearer "):
            return None
        raw = header[len("Bearer ") :].strip()
        try:
            return AccessToken(raw).get("escola_id")
        except TokenError:
            # Token inválido/expirado — o DRF devolve 401 adiante; aqui só
            # seguimos sem escola no contexto de log.
            return None
        except Exception:
            # Defensivo: logging jamais pode derrubar a request.
            logger.warning("falha inesperada ao extrair escola_id do token pro log")
            return None


class SentryHttpErrorMiddleware:
    """Reporta respostas de erro HTTP ao Sentry.

    Os 5xx por exceção não tratada já são capturados pela `DjangoIntegration`
    (com stack trace). O gap são os **4xx** que o DRF trata e devolve sem
    propagar exceção (400/403/404/422...) e os erros retornados direto via
    `Response(status=...)`. Este middleware fecha esse gap: pra toda resposta
    com status na faixa 4xx (fora da lista de exclusão) envia um evento ao
    Sentry com nível `warning`. Os 5xx continuam a cargo da integração nativa,
    pra não duplicar evento nem gastar quota à toa.

    No-op barato quando o Sentry não está ativo (sem `SENTRY_DSN`, ou em
    testes): só lê o `status_code` e retorna.

    Status ignorados vêm de `settings.SENTRY_IGNORE_STATUS_CODES` (default
    `{401}` — churn normal de refresh de token).
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self.ignorados = set(
            getattr(settings, "SENTRY_IGNORE_STATUS_CODES", {401})
        )

    def __call__(self, request):
        response = self.get_response(request)
        self._talvez_reportar(request, response)
        return response

    def _talvez_reportar(self, request, response):
        code = getattr(response, "status_code", 0)
        if not (400 <= code < 500) or code in self.ignorados:
            return
        # Sem cliente ativo (sem DSN / em testes) não monta contexto à toa.
        if not sentry_sdk.get_client().is_active():
            return
        try:
            with sentry_sdk.new_scope() as scope:
                scope.set_tag("http.status_code", code)
                scope.set_tag("http.method", request.method)
                # Sem PII (LGPD): só método, rota e querystring.
                scope.set_context(
                    "request",
                    {
                        "method": request.method,
                        "path": request.path,
                        "query": request.META.get("QUERY_STRING", ""),
                    },
                )
                sentry_sdk.capture_message(
                    f"HTTP {code} {request.method} {request.path}",
                    level="warning",
                )
        except Exception:
            # Observabilidade jamais derruba a request.
            logger.warning("falha ao reportar resposta %s ao Sentry", code)
