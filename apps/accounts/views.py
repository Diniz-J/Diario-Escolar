"""Views da app accounts."""
from rest_framework import viewsets

from .models import Usuario
from .serializers import UsuarioSerializer


class UsuarioViewSet(viewsets.ModelViewSet):
    """CRUD de usuários do sistema."""

    queryset = Usuario.objects.all().order_by("id")
    serializer_class = UsuarioSerializer
