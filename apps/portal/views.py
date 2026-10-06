"""Views de autenticação do portal do responsável.

Rotas sob `/api/v1/portal/` (ver `urls.py`). Isoladas do staff: usam a
`PortalJWTAuthentication` e tokens próprios (`tokens.py`). As leituras do
portal (filhos, boletim, comunicados, ocorrências) entram na fatia 4.
"""
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers, status
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.views import TokenRefreshView

from apps.common.texto import normalizar_email

from .authentication import IsResponsavel, PortalJWTAuthentication
from .models import Responsavel
from .tokens import CLAIM_RESPONSAVEL_ID, PortalRefreshToken

# Mesma mensagem pra email inexistente, conta inativa, conta sem senha e
# senha errada: diferenciar diria a um atacante quais emails têm conta.
ERRO_CREDENCIAIS = _("Email ou senha inválidos.")


class PortalLoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(trim_whitespace=False)


class PortalLoginView(APIView):
    """`POST /portal/auth/login/` — público, com rate limit por IP.

    O email é único por escola, não globalmente. A conta é achada entre as
    ativas com aquele email pela senha que bate; se bater em mais de uma
    (mesmo email e mesma senha em duas escolas), recusa — responsável em
    várias escolas está fora da v1 (`PORTAL.md`, seção 6).
    """

    authentication_classes: list = []
    permission_classes: list = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "portal_login"

    def post(self, request) -> Response:
        serializer = PortalLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = normalizar_email(serializer.validated_data["email"])
        senha = serializer.validated_data["password"]

        candidatos = [
            r
            for r in Responsavel.objects.filter(email=email, ativo=True)
            if r.has_usable_password()
        ]
        if not candidatos:
            # Roda um hash mesmo assim, pra resposta não ser mensuravelmente
            # mais rápida quando não há senha a conferir (enumeração por
            # tempo). Cobre email inexistente, conta inativa e conta sem
            # senha — esta última é toda conta semeada antes do convite, e
            # o `check_password` do Django não faz hash pra senha
            # inutilizável.
            Responsavel().set_password(senha)
        validos = [r for r in candidatos if r.check_password(senha)]

        if not validos:
            # Resposta direta em vez de `AuthenticationFailed`: sem classe de
            # autenticação na view, o DRF converteria a exceção em 403.
            return Response(
                {"detail": ERRO_CREDENCIAIS},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        if len(validos) > 1:
            return Response(
                {
                    "detail": (
                        "Este email tem acesso em mais de uma escola. "
                        "Procure a secretaria da escola."
                    )
                },
                status=status.HTTP_409_CONFLICT,
            )

        refresh = PortalRefreshToken.para_responsavel(validos[0])
        return Response(
            {"access": str(refresh.access_token), "refresh": str(refresh)},
            status=status.HTTP_200_OK,
        )


class PortalTokenRefreshSerializer(TokenRefreshSerializer):
    token_class = PortalRefreshToken

    def validate(self, attrs):
        # O serializer base só checa a conta via `user_id`, que o token do
        # portal não tem. Sem isto, uma conta desativada seguiria
        # renovando a sessão até o refresh expirar (7 dias).
        try:
            refresh = self.token_class(attrs["refresh"])
        except TokenError:
            # Deixa o base levantar o erro no formato padrão do SimpleJWT.
            return super().validate(attrs)
        ativo = Responsavel.objects.filter(
            pk=refresh[CLAIM_RESPONSAVEL_ID], ativo=True
        ).exists()
        if not ativo:
            raise AuthenticationFailed(
                _("Conta não encontrada ou inativa."), code="no_active_account"
            )
        return super().validate(attrs)


class PortalTokenRefreshView(TokenRefreshView):
    """`POST /portal/auth/refresh/` — rotação + blacklist, como no staff."""

    serializer_class = PortalTokenRefreshSerializer


class PortalLogoutView(APIView):
    """`POST /portal/auth/logout/` — invalida o refresh do portal."""

    authentication_classes = [PortalJWTAuthentication]
    permission_classes = [IsResponsavel]

    def post(self, request) -> Response:
        refresh = request.data.get("refresh")
        if not refresh:
            return Response(
                {"detail": "Informe o token de refresh."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            PortalRefreshToken(refresh).blacklist()
        except TokenError:
            # Inválido, expirado ou já na blacklist: a sessão já acabou.
            pass
        return Response(status=status.HTTP_205_RESET_CONTENT)


class PortalMeView(APIView):
    """`GET /portal/me/` — dados do responsável autenticado."""

    authentication_classes = [PortalJWTAuthentication]
    permission_classes = [IsResponsavel]

    def get(self, request) -> Response:
        responsavel = request.user
        return Response(
            {
                "id": responsavel.id,
                "nome": responsavel.nome,
                "email": responsavel.email,
                "escola_id": responsavel.escola_id,
            }
        )
