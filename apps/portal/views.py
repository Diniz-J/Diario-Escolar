"""Views de autenticação do portal do responsável.

Rotas sob `/api/v1/portal/` (ver `urls.py`). Isoladas do staff: usam a
`PortalJWTAuthentication` e tokens próprios (`tokens.py`). As leituras do
portal (filhos, boletim, comunicados, ocorrências) entram na fatia 4.

Exceção: `ConvidarResponsavelView` é endpoint do **staff** (autenticação
padrão), roteado em `config/urls.py` fora do prefixo do portal.
"""
import logging

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.shortcuts import get_object_or_404
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers, status
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle, UserRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.views import TokenRefreshView

from apps.common.permissions import IsAdminOrDiretor, eh_admin_global
from apps.common.texto import normalizar_email

from .authentication import IsResponsavel, PortalJWTAuthentication
from .models import ConviteResponsavel, Responsavel
from .services import definir_senha, emitir_link, solicitar_redefinicao
from .tokens import CLAIM_RESPONSAVEL_ID, PortalRefreshToken, token_vale_para

logger = logging.getLogger(__name__)

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
        # portal não tem. Sem isto, uma conta desativada — ou com a senha
        # trocada — seguiria renovando a sessão até o refresh expirar (7 dias).
        try:
            refresh = self.token_class(attrs["refresh"])
        except TokenError:
            # Deixa o base levantar o erro no formato padrão do SimpleJWT.
            return super().validate(attrs)
        responsavel = Responsavel.objects.filter(
            pk=refresh[CLAIM_RESPONSAVEL_ID], ativo=True
        ).first()
        if responsavel is None or not token_vale_para(refresh, responsavel):
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


# --------------------------------------------------------------------------
# Convite e senha (fatia 3)
# --------------------------------------------------------------------------


class ConviteThrottle(UserRateThrottle):
    """Rate limit do convite, por usuário da escola.

    Cada convite é um email, e a cota do provedor é compartilhada com os
    comunicados e as ocorrências. Ver `convite_responsavel` em settings.
    """

    scope = "convite_responsavel"


class ConvidarResponsavelView(APIView):
    """`POST /responsaveis/<id>/convidar/` — staff de nível diretor.

    Endpoint do **staff** (autenticação padrão), não do portal. Envia o
    convite de primeira ativação. Responsável de outra escola dá 404,
    conta inativa ou que já definiu senha dá 400 — pra essa, o caminho é o
    "esqueci a senha" do próprio responsável.

    O envio é síncrono e a falha é devolvida: aqui quem chama é a escola,
    então não há o que esconder, e a secretaria precisa saber que o convite
    não saiu.
    """

    permission_classes = [IsAdminOrDiretor]
    throttle_classes = [ConviteThrottle]

    def post(self, request, pk: int) -> Response:
        qs = Responsavel.objects.select_related("escola")
        usuario = request.user
        if not eh_admin_global(usuario):
            # Sem escola vinculada, nada — mesmo princípio do EscopoEscolaMixin.
            qs = qs.filter(escola_id=usuario.escola_id) if usuario.escola_id else qs.none()
        responsavel = get_object_or_404(qs, pk=pk)

        if not responsavel.ativo:
            return Response(
                {"detail": "Conta de responsável inativa."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if responsavel.has_usable_password():
            return Response(
                {
                    "detail": (
                        "Este responsável já ativou o acesso. Se esqueceu a "
                        "senha, ele pode usar o \"esqueci a senha\" do portal."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            convite = emitir_link(
                responsavel, ConviteResponsavel.Finalidade.CONVITE, enviado_por=usuario
            )
        except Exception:  # noqa: BLE001 — vira evento no Sentry
            logger.exception(
                "Falha ao enviar convite do portal",
                extra={"responsavel_id": responsavel.pk},
            )
            return Response(
                {
                    "detail": (
                        "Não foi possível enviar o email agora. Tente de novo "
                        "mais tarde."
                    )
                },
                status=status.HTTP_502_BAD_GATEWAY,
            )
        return Response(
            {"detail": f"Convite enviado para {responsavel.email}.", "expira_em": convite.expira_em},
            status=status.HTTP_200_OK,
        )


class EsqueciSenhaSerializer(serializers.Serializer):
    email = serializers.EmailField()


class PortalEsqueciSenhaView(APIView):
    """`POST /portal/auth/senha/esqueci/` — público, resposta sempre igual.

    Só envia pra conta ativa **com senha**: conta sem senha nunca foi
    ativada e precisa do convite da escola. O envio sai fora da request
    (`solicitar_redefinicao`), pra o tempo de resposta não denunciar quais
    emails têm conta.
    """

    authentication_classes: list = []
    permission_classes: list = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "portal_login"  # reaproveita o bucket do login

    def post(self, request) -> Response:
        serializer = EsqueciSenhaSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = normalizar_email(serializer.validated_data["email"])
        solicitar_redefinicao(
            r
            for r in Responsavel.objects.filter(email=email, ativo=True)
            if r.has_usable_password()
        )
        return Response(
            {
                "detail": (
                    "Se houver uma conta ativa com este email, enviamos um "
                    "link para redefinir a senha."
                )
            },
            status=status.HTTP_200_OK,
        )


class DefinirSenhaSerializer(serializers.Serializer):
    token = serializers.CharField(max_length=128)
    password = serializers.CharField(max_length=128, trim_whitespace=False)


class PortalDefinirSenhaView(APIView):
    """`POST /portal/auth/senha/definir/` — público.

    Atende os dois links (convite e redefinição). Não devolve tokens: o
    responsável entra pelo login, com a senha que acabou de definir.
    """

    authentication_classes: list = []
    permission_classes: list = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "portal_login"

    def post(self, request) -> Response:
        serializer = DefinirSenhaSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        convite = ConviteResponsavel.buscar_valido(serializer.validated_data["token"])
        if convite is None:
            return Response(
                {"detail": "Link inválido ou expirado."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        senha = serializer.validated_data["password"]
        try:
            # Com o responsável: o validador de similaridade compara a senha
            # com o email dele.
            validate_password(senha, user=convite.responsavel)
        except DjangoValidationError as exc:
            return Response(
                {"password": list(exc.messages)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        definir_senha(convite, senha)
        return Response(
            {"detail": "Senha definida. Você já pode entrar no portal."},
            status=status.HTTP_200_OK,
        )
