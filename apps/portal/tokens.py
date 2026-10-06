"""Tokens JWT do portal do responsável.

Mesma chave e mesmo backend do staff, mas com identidade própria: claim
`tipo=responsavel` e id em `responsavel_id`. Ver `apps/common/authentication.py`
pro lado do staff e `PORTAL.md`, seção 4.1, pro risco que isto fecha.

Os tokens são montados à mão, sem `for_user()`: o `for_user` do SimpleJWT
grava o pk em `user_id` e, com a blacklist instalada, cria o
`OutstandingToken` com FK pro `AUTH_USER_MODEL` — ligaria o token do
responsável de pk N ao `Usuario` de pk N. Sem `user_id` no payload, o
`outstand()`/`blacklist()` da biblioteca não acha usuário e deixa a FK
nula; a blacklist funciona só pelo `jti`.
"""
import hashlib

from django.utils.translation import gettext_lazy as _
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.settings import api_settings
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

from apps.common.authentication import CLAIM_TIPO, TIPO_RESPONSAVEL

CLAIM_RESPONSAVEL_ID = "responsavel_id"
CLAIM_SENHA = "senha_ver"


def impressao_senha(responsavel) -> str:
    """Impressão curta do hash da senha atual, gravada no token.

    Trocar a senha muda a impressão e derruba todo token emitido antes —
    sem isso, uma sessão roubada sobreviveria ao "esqueci a senha" até o
    refresh expirar (7 dias). Mesma ideia do `CHECK_REVOKE_TOKEN` do
    SimpleJWT, que só funciona via `for_user()` (que o portal não usa).
    É hash do hash: não expõe nada da senha.
    """
    return hashlib.sha256(responsavel.password.encode("utf-8")).hexdigest()[:16]


def token_vale_para(token, responsavel) -> bool:
    """True se o token foi emitido com a senha atual do responsável."""
    return token.get(CLAIM_SENHA) == impressao_senha(responsavel)


def exigir_token_do_portal(token) -> None:
    """Levanta `TokenError` se o token não for de responsável.

    Exige o claim de tipo, o id do responsável e a **ausência** de
    `user_id` — um token com os dois ids é forjado ou bugado, e não deve
    valer em lado nenhum.
    """
    payload = token.payload
    if payload.get(CLAIM_TIPO) != TIPO_RESPONSAVEL:
        raise TokenError(_("Token não é válido para o portal."))
    # Exige id numérico: um id qualquer viraria `ValueError` (500) na busca
    # do responsável, em vez de 401.
    if not str(payload.get(CLAIM_RESPONSAVEL_ID, "")).isdigit():
        raise TokenError(_("Token sem identificação do responsável."))
    if api_settings.USER_ID_CLAIM in payload:
        raise TokenError(_("Token não é válido para o portal."))


class PortalAccessToken(AccessToken):
    def verify(self, *args, **kwargs) -> None:
        super().verify(*args, **kwargs)
        exigir_token_do_portal(self)


class PortalRefreshToken(RefreshToken):
    access_token_class = PortalAccessToken

    def verify(self, *args, **kwargs) -> None:
        super().verify(*args, **kwargs)
        exigir_token_do_portal(self)

    @classmethod
    def para_responsavel(cls, responsavel) -> "PortalRefreshToken":
        """Emite o refresh (e, por `access_token`, o access) do responsável."""
        token = cls()
        token[CLAIM_TIPO] = TIPO_RESPONSAVEL
        token[CLAIM_RESPONSAVEL_ID] = str(responsavel.pk)
        token[CLAIM_SENHA] = impressao_senha(responsavel)
        # Usado pelo `EscolaLogContextMiddleware` pra carimbar o log.
        token["escola_id"] = responsavel.escola_id
        token.outstand()
        return token
