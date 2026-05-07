"""Permissões customizadas da app accounts."""
from rest_framework.permissions import BasePermission

from .models import Usuario


class PodeGerenciarUsuarios(BasePermission):
    """Restringe acesso ao CRUD de usuários a perfis admin e diretor.

    Outros perfis autenticados (professor, secretaria, inspetor) não conseguem
    listar, criar, editar nem remover usuários por esta API.
    """

    PERFIS_PERMITIDOS = {Usuario.Perfil.ADMIN, Usuario.Perfil.DIRETOR}

    def has_permission(self, request, view) -> bool:
        usuario = request.user
        if not usuario.is_authenticated:
            return False
        # Superusuário do Django sempre pode gerenciar
        if usuario.is_superuser:
            return True
        return usuario.perfil in self.PERFIS_PERMITIDOS
