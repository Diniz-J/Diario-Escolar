"""Views da app accounts."""
import logging

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView

from apps.common.permissions import IsAdminOrDiretor

from .models import PasswordResetToken, Usuario
from .serializers import (
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    UsuarioSerializer,
    UsuarioTokenObtainPairSerializer,
)
from .services import enviar_link_redefinicao

logger = logging.getLogger(__name__)


class UsuarioViewSet(viewsets.ModelViewSet):
    """CRUD de usuários do sistema. Restrito a perfis admin e diretor."""

    queryset = Usuario.objects.all().order_by("id")
    serializer_class = UsuarioSerializer
    permission_classes = [IsAdminOrDiretor]

    @action(detail=True, methods=["post"], url_path="enviar-reset-senha")
    def enviar_reset_senha(self, request, pk=None):
        """`POST /usuarios/<id>/enviar-reset-senha/` — admin/diretor/secretaria/coordenador.

        Dispara um link de redefinição de senha pro email do usuário alvo.
        Reusa toda a plumbing do "Esqueci senha" (`PasswordResetToken.gerar`
        + `enviar_link_redefinicao`); a única diferença é o gatilho ser de
        um usuário de nível diretor, não do próprio dono da conta.

        Guard de escola: admin/superuser passa qualquer escola; o resto
        só dispara reset pra alguém da mesma escola. Protege contra IDOR,
        já que o ViewSet hoje não filtra `get_queryset` por escola.
        """
        usuario = self.get_object()

        eh_admin_global = (
            request.user.is_superuser
            or request.user.perfil == Usuario.Perfil.ADMIN
        )
        if not eh_admin_global and request.user.escola_id != usuario.escola_id:
            return Response(
                {"detail": "Não encontrado."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if not usuario.email:
            return Response(
                {
                    "detail": (
                        "Este usuário não tem email cadastrado. Defina "
                        "um email no perfil antes de enviar o link de "
                        "redefinição."
                    )
                },
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        _token_obj, token_cru = PasswordResetToken.gerar(usuario)
        enviar_link_redefinicao(usuario, token_cru)
        logger.info(
            "Reset de senha disparado por %s para %s",
            request.user.username,
            usuario.username,
        )
        return Response(
            {
                "detail": f"Link de redefinição enviado para {usuario.email}.",
                "email": usuario.email,
            },
            status=status.HTTP_200_OK,
        )


class UsuarioTokenObtainPairView(TokenObtainPairView):
    """Endpoint de obtenção de JWT com claims customizados.

    Mantém o contrato da SimpleJWT (username + password → access + refresh)
    e adiciona `escola_id` e `perfil` ao payload via
    `UsuarioTokenObtainPairSerializer`.

    Protegido por rate limit (`throttle_scope="login"`, ver
    DEFAULT_THROTTLE_RATES) contra brute force de senha.
    """

    serializer_class = UsuarioTokenObtainPairSerializer
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "login"


class PasswordResetRequestView(APIView):
    """`POST /auth/password/reset/request/` — público.

    Recebe `{"username": ...}`. Resolve o email cadastrado do usuário
    e dispara o link de redefinição pra esse email. Resposta sempre 200
    (anti-enumeração) — não revela se o username existe ou não.

    Throttle de 5/min por IP (mesmo limite do login) pra dificultar
    enumeração massiva por força bruta de usernames.
    """

    permission_classes: list = []  # público
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "login"  # reaproveita o bucket do login

    def post(self, request) -> Response:
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        username = serializer.validated_data["username"]

        try:
            usuario = Usuario.objects.get(username=username, is_active=True)
        except Usuario.DoesNotExist:
            usuario = None

        if usuario is not None and usuario.email:
            token_obj, token_cru = PasswordResetToken.gerar(usuario)
            try:
                enviar_link_redefinicao(usuario, token_cru)
            except Exception:  # noqa: BLE001 — defesa adicional
                # `enviar_link_redefinicao` já loga, mas garantimos que
                # qualquer exceção residual aqui não derrube a resposta.
                logger.exception(
                    "Falha inesperada no fluxo de reset request",
                    extra={"usuario_id": usuario.id, "token_id": token_obj.id},
                )

        # Resposta neutra independente do resultado interno.
        return Response(
            {
                "detail": (
                    "Se o usuário existir e tiver email cadastrado, um "
                    "link de redefinição foi enviado."
                )
            },
            status=status.HTTP_200_OK,
        )


class PasswordResetConfirmView(APIView):
    """`POST /auth/password/reset/confirm/` — público.

    Recebe `{"token", "new_password"}`. Valida o token (existe, não usado,
    não expirado), aplica os validators de senha do Django e troca a
    senha. Marca o token como usado pra impedir replay.
    """

    permission_classes: list = []  # público

    def post(self, request) -> Response:
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        token_cru = serializer.validated_data["token"]
        nova_senha = serializer.validated_data["new_password"]

        token_obj = PasswordResetToken.buscar_valido(token_cru)
        if token_obj is None:
            return Response(
                {"detail": "Token inválido ou expirado."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        usuario = token_obj.usuario
        usuario.set_password(nova_senha)
        usuario.save(update_fields=["password"])
        token_obj.marcar_usado()

        return Response(
            {"detail": "Senha redefinida com sucesso."},
            status=status.HTTP_200_OK,
        )


class PasswordChangeRequestView(APIView):
    """`POST /auth/password/change/` — protegido.

    Sem corpo. Usa o email do usuário autenticado pra mandar o link de
    redefinição — não pede senha atual. Mesmo fluxo do reset (token
    single-use de 1h), apenas eliminando a etapa de "digite seu username".

    Se o usuário autenticado por algum motivo não tem email cadastrado
    (não devia acontecer pós-migration 0004), devolve 422 com mensagem
    clara em vez de cair silenciosamente.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request) -> Response:
        usuario = request.user
        if not usuario.email:
            return Response(
                {
                    "detail": (
                        "Seu usuário não tem email cadastrado. Peça pra "
                        "um administrador definir um email no seu perfil "
                        "antes de redefinir a senha."
                    )
                },
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        _token_obj, token_cru = PasswordResetToken.gerar(usuario)
        enviar_link_redefinicao(usuario, token_cru)
        return Response(
            {
                "detail": f"Link de redefinição enviado para {usuario.email}.",
                "email": usuario.email,
            },
            status=status.HTTP_200_OK,
        )


class LogoutView(APIView):
    """Invalida (blacklist) o refresh token — logout efetivo.

    Recebe `{"refresh": "<token>"}`. Depois disso o refresh não gera mais
    access novo. O access atual ainda vale até expirar (curto, 1h), mas
    sem refresh válido a sessão não se renova. Exige autenticação para
    evitar que terceiros invalidem tokens alheios por tentativa.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request) -> Response:
        refresh = request.data.get("refresh")
        if not refresh:
            return Response(
                {"detail": "Informe o token de refresh."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            RefreshToken(refresh).blacklist()
        except TokenError:
            # Token inválido/expirado/já na blacklist — do ponto de vista
            # do usuário a sessão já está encerrada, então respondemos ok.
            pass
        return Response(status=status.HTTP_205_RESET_CONTENT)
