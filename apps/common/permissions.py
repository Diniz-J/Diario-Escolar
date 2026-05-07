"""Permissões reutilizáveis baseadas no perfil de `Usuario`.

Convenção: superuser do Django e usuário com `perfil="admin"` têm bypass total
em todas as classes definidas aqui.

Os strings de perfil são mantidos hardcoded propositalmente para evitar import
da app `accounts` (poderia gerar ciclos quando outras apps consumirem o módulo).
Devem corresponder ao enum `apps.accounts.models.Usuario.Perfil`.
"""
from rest_framework.permissions import BasePermission

_PERFIL_ADMIN = "admin"
_PERFIL_DIRETOR = "diretor"
_PERFIL_PROFESSOR = "professor"


def _tem_bypass(usuario) -> bool:
    """Retorna True se o usuário é admin global (perfil admin ou superuser)."""
    return usuario.is_superuser or getattr(usuario, "perfil", None) == _PERFIL_ADMIN


class _BasePerfilPermission(BasePermission):
    """Base interna — subclasses devem definir `PERFIS_PERMITIDOS`."""

    PERFIS_PERMITIDOS: frozenset[str] = frozenset()

    def has_permission(self, request, view) -> bool:
        usuario = request.user
        if not usuario.is_authenticated:
            return False
        if _tem_bypass(usuario):
            return True
        return getattr(usuario, "perfil", None) in self.PERFIS_PERMITIDOS


class IsAdmin(_BasePerfilPermission):
    """Apenas administradores (perfil admin ou superuser)."""

    PERFIS_PERMITIDOS = frozenset()


class IsAdminOrDiretor(_BasePerfilPermission):
    """Administradores (bypass) ou diretores."""

    PERFIS_PERMITIDOS = frozenset({_PERFIL_DIRETOR})


class IsAdminOrDiretorOrProfessor(_BasePerfilPermission):
    """Administradores (bypass), diretores ou professores."""

    PERFIS_PERMITIDOS = frozenset({_PERFIL_DIRETOR, _PERFIL_PROFESSOR})
