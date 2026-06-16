"""Middlewares compartilhados do Diário Escolar."""
import logging

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
