"""Autenticação e permissão das views do portal do responsável."""
from django.utils.translation import gettext_lazy as _
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.permissions import BasePermission
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError

from .models import Responsavel
from .tokens import CLAIM_RESPONSAVEL_ID, PortalAccessToken, token_vale_para


class PortalJWTAuthentication(JWTAuthentication):
    """Autentica só token do portal e resolve contra `Responsavel`.

    Reaproveita do `JWTAuthentication` a leitura do header; troca a
    validação (só `PortalAccessToken`, que exige o claim de tipo) e a
    busca do usuário (nunca o `AUTH_USER_MODEL`).
    """

    def get_validated_token(self, raw_token):
        try:
            return PortalAccessToken(raw_token)
        except TokenError as exc:
            raise InvalidToken({"detail": str(exc)}) from exc

    def get_user(self, validated_token):
        # Conta desativada depois do login perde o acesso já no próximo
        # request, sem esperar o access expirar.
        try:
            responsavel = Responsavel.objects.get(
                pk=validated_token[CLAIM_RESPONSAVEL_ID], ativo=True
            )
        except (Responsavel.DoesNotExist, ValueError) as exc:
            raise AuthenticationFailed(
                _("Conta não encontrada ou inativa."), code="user_not_found"
            ) from exc
        # Senha trocada depois da emissão: a sessão antiga cai.
        if not token_vale_para(validated_token, responsavel):
            raise AuthenticationFailed(
                _("Sessão encerrada. Entre de novo."), code="token_revoked"
            )
        return responsavel


class IsResponsavel(BasePermission):
    """Só deixa passar requisição autenticada como `Responsavel`.

    Redundante com a `PortalJWTAuthentication` por desenho: se alguém
    trocar a autenticação de uma view do portal, a permissão continua
    barrando um `Usuario`.
    """

    def has_permission(self, request, view) -> bool:
        return isinstance(request.user, Responsavel)
