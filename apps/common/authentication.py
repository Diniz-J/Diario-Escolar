"""Autenticação JWT do staff, fechada para tokens do portal do responsável.

O staff e o portal assinam tokens com a mesma chave e o mesmo backend do
SimpleJWT. Sem separação explícita, o `JWTAuthentication` padrão aceitaria
um token do portal num endpoint de staff — e, se o token carregasse
`user_id`, resolveria esse pk contra o `Usuario`: o responsável de pk 3
viraria o funcionário de pk 3. Ver `PORTAL.md`, seção 4.1.

A separação tem duas camadas independentes:

1. O token do portal leva `CLAIM_TIPO = TIPO_RESPONSAVEL`; o staff recusa
   qualquer token com esse claim (aqui) e o portal recusa qualquer token
   sem ele (`apps/portal/tokens.py`).
2. O token do portal guarda o id em `responsavel_id`, nunca em `user_id`.
   Mesmo se a camada 1 falhasse, o staff não acharia `user_id` e
   recusaria.

As constantes moram aqui, e não em `apps/portal`, porque `common` não pode
depender de uma app de domínio.
"""
from django.utils.translation import gettext_lazy as _
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

CLAIM_TIPO = "tipo"
TIPO_RESPONSAVEL = "responsavel"


def recusar_token_do_portal(token) -> None:
    """Levanta `TokenError` se o token for do portal do responsável."""
    if CLAIM_TIPO in token.payload:
        raise TokenError(_("Token não é válido para esta área."))


class StaffAccessToken(AccessToken):
    """Access token do staff: recusa token emitido pelo portal."""

    def verify(self, *args, **kwargs) -> None:
        super().verify(*args, **kwargs)
        recusar_token_do_portal(self)


class StaffRefreshToken(RefreshToken):
    """Refresh token do staff: recusa refresh emitido pelo portal.

    Sem isto, o refresh do staff aceitaria um refresh do portal e
    devolveria tokens novos — inúteis no staff (o access sai com o claim
    do portal), mas válidos no portal, por um caminho que não é o dele.
    """

    access_token_class = StaffAccessToken

    def verify(self, *args, **kwargs) -> None:
        super().verify(*args, **kwargs)
        recusar_token_do_portal(self)


class StaffJWTAuthentication(JWTAuthentication):
    """Autenticação padrão da API do staff (ver `DEFAULT_AUTHENTICATION_CLASSES`)."""

    def get_validated_token(self, raw_token):
        try:
            return StaffAccessToken(raw_token)
        except TokenError as exc:
            raise InvalidToken({"detail": str(exc)}) from exc
