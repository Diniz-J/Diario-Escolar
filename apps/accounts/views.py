"""Views da app accounts."""
from rest_framework import viewsets

from .models import Usuario
from .permissions import PodeGerenciarUsuarios
from .serializers import UsuarioSerializer


class UsuarioViewSet(viewsets.ModelViewSet):
    """CRUD de usuários do sistema. Restrito a perfis admin e diretor."""

    queryset = Usuario.objects.all().order_by("id")
    serializer_class = UsuarioSerializer
    permission_classes = [PodeGerenciarUsuarios]
