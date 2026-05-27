"""Views da app accounts."""
from rest_framework import status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView

from apps.common.permissions import IsAdminOrDiretor

from .models import Usuario
from .serializers import UsuarioSerializer, UsuarioTokenObtainPairSerializer


class UsuarioViewSet(viewsets.ModelViewSet):
    """CRUD de usuários do sistema. Restrito a perfis admin e diretor."""

    queryset = Usuario.objects.all().order_by("id")
    serializer_class = UsuarioSerializer
    permission_classes = [IsAdminOrDiretor]


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
