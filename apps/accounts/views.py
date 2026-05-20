"""Views da app accounts."""
from rest_framework import viewsets
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
    """

    serializer_class = UsuarioTokenObtainPairSerializer
