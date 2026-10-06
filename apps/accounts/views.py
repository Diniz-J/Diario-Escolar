"""Views da app accounts."""
import logging

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle, UserRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from apps.common.authentication import StaffRefreshToken
from apps.common.permissions import (
    PERFIS_PRIVILEGIADOS,
    IsAdminOrDiretor,
    eh_admin_global,
)

from .models import PasswordResetToken, Usuario
from .serializers import (
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    UsuarioSerializer,
    UsuarioTokenObtainPairSerializer,
)
from .services import enviar_link_redefinicao

logger = logging.getLogger(__name__)


class ResetSenhaThrottle(UserRateThrottle):
    """Rate limit da action de reset disparado pela direção.

    Escopo próprio (`reset_senha` em `DEFAULT_THROTTLE_RATES`) e chaveado
    por usuário — quem dispara está sempre autenticado. Ver o comentário
    em `config/settings.py` pro racional do limite.
    """

    scope = "reset_senha"


class UsuarioViewSet(viewsets.ModelViewSet):
    """CRUD de usuários do sistema. Restrito a perfis admin e diretor.

    Escopo e escalada (ver também `UsuarioSerializer.validate`):

    - `get_queryset` filtra pela escola do usuário logado. Antes era
      `Usuario.objects.all()` sem escopo, então uma secretaria da Escola A
      lia e editava usuários da Escola B.
    - Conta com perfil privilegiado (admin/diretor/secretaria/coordenador)
      só é alterada pelo admin global — ou pelo próprio dono. Sem isto, a
      secretaria trocava o email do admin e disparava
      `enviar-reset-senha` pra receber o link na própria caixa: takeover
      sem nunca tocar no campo `password`.
    """

    queryset = Usuario.objects.all().order_by("id")
    serializer_class = UsuarioSerializer
    permission_classes = [IsAdminOrDiretor]

    def get_queryset(self):
        """Restringe à escola do usuário logado; admin global vê tudo.

        Usuário não-admin sem escola vinculada recebe queryset vazio — o
        mesmo princípio do `EscopoEscolaMixin`: na dúvida, não vazar.
        Isto também cobre o caso em que autor e alvo têm `escola_id` nulo,
        que uma comparação `!=` deixaria passar.
        """
        qs = super().get_queryset()
        usuario = self.request.user
        if not usuario.is_authenticated:
            return qs.none()
        if eh_admin_global(usuario):
            return qs
        if not usuario.escola_id:
            return qs.none()
        return qs.filter(escola_id=usuario.escola_id)

    def get_throttles(self):
        """Aplica o rate limit só na action de reset.

        Passar `throttle_classes` como kwarg do `@action` **não funciona**:
        o DRF não propaga isso pelos `initkwargs` e a view cai no throttle
        default. Resolver aqui é explícito e testável.
        """
        if self.action == "enviar_reset_senha":
            return [ResetSenhaThrottle()]
        return super().get_throttles()

    def _checar_alvo_privilegiado(self, alvo) -> None:
        """Barra não-admin de mexer em conta privilegiada que não é a sua."""
        usuario = self.request.user
        if eh_admin_global(usuario):
            return
        if alvo.pk == usuario.pk:
            return
        if alvo.perfil in PERFIS_PRIVILEGIADOS:
            raise PermissionDenied(
                "Apenas um administrador pode operar sobre contas de "
                "administração."
            )

    def perform_update(self, serializer) -> None:
        self._checar_alvo_privilegiado(serializer.instance)
        serializer.save()

    def perform_destroy(self, instance) -> None:
        self._checar_alvo_privilegiado(instance)
        instance.delete()

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
        # O escopo por escola agora vem do `get_queryset` (cross-escola já
        # devolve 404 aqui), então só resta barrar alvo privilegiado: sem
        # isto, a secretaria dispararia o link de redefinição da conta do
        # admin — e bastaria ter trocado o email dele antes.
        self._checar_alvo_privilegiado(usuario)

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


class StaffTokenRefreshSerializer(TokenRefreshSerializer):
    token_class = StaffRefreshToken


class StaffTokenRefreshView(TokenRefreshView):
    """`POST /auth/token/refresh/` — igual ao do SimpleJWT, mas recusa o
    refresh do portal do responsável (ver `StaffRefreshToken`)."""

    serializer_class = StaffTokenRefreshSerializer


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
            # `StaffRefreshToken`, não o `RefreshToken` cru: recusa o refresh
            # do portal do responsável, mantendo a invariante de que cada
            # lado recusa o token do outro (PORTAL.md, seção 4.1).
            StaffRefreshToken(refresh).blacklist()
        except TokenError:
            # Token inválido/expirado/já na blacklist/do portal — do ponto de
            # vista da sessão do staff não há o que encerrar, então ok.
            pass
        return Response(status=status.HTTP_205_RESET_CONTENT)
