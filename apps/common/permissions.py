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
_PERFIL_SECRETARIA = "secretaria"
_PERFIL_PROFESSOR = "professor"
_PERFIL_INSPETOR = "inspetor"

# Decisão de design: `secretaria` opera como `diretor` e `inspetor` opera
# como `professor` em termos de permissão. A distinção entre eles é só de
# **rótulo de UX** (saudação, lista de usuários, identidade visual da
# sidebar) — útil pra escala atual (escola pequena/média) onde os papéis
# são fluidos no dia a dia. Quando o sistema crescer pra rede grande e
# fizer sentido separar, basta refinar as classes abaixo — os perfis já
# existem distintos no banco (`Usuario.Perfil`).


def _tem_bypass(usuario) -> bool:
    """Retorna True se o usuário é admin global (perfil admin ou superuser).

    Usa `getattr` para tolerar objetos sem `is_superuser` (ex.: AnonymousUser
    chamado fora do fluxo padrão de `has_permission`, que já checa
    `is_authenticated` antes).
    """
    if getattr(usuario, "is_superuser", False):
        return True
    return getattr(usuario, "perfil", None) == _PERFIL_ADMIN


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
    """Apenas administradores (perfil admin ou superuser).

    `PERFIS_PERMITIDOS` é proposital e fica vazio: admin/superuser já passam
    pelo `_tem_bypass`. NÃO adicione `_PERFIL_ADMIN` aqui — duplicaria a
    verificação e fragmentaria a fonte da verdade do que conta como bypass.
    """

    PERFIS_PERMITIDOS = frozenset()


class IsAdminOrDiretor(_BasePerfilPermission):
    """Administradores (bypass), diretores ou secretaria.

    `secretaria` entra aqui como alias funcional de diretor — mesma regra
    do dia a dia escolar (matricula aluno, monta turma, cadastra prof).
    """

    PERFIS_PERMITIDOS = frozenset({_PERFIL_DIRETOR, _PERFIL_SECRETARIA})


class IsAdminOrDiretorOrProfessor(_BasePerfilPermission):
    """Administradores (bypass), diretores, secretaria, professores ou inspetores.

    `inspetor` entra como alias de professor (lança ocorrência/chamada
    como professor faria). `secretaria` continua como alias de diretor.
    """

    PERFIS_PERMITIDOS = frozenset(
        {
            _PERFIL_DIRETOR,
            _PERFIL_SECRETARIA,
            _PERFIL_PROFESSOR,
            _PERFIL_INSPETOR,
        }
    )


class IsAdminOrDiretorOrProfessorOrInspetor(_BasePerfilPermission):
    """Administradores (bypass), diretores, secretaria, professores ou inspetores.

    Hoje equivale a `IsAdminOrDiretorOrProfessor` por causa dos aliases
    (secretaria → diretor, inspetor → professor). Mantida como classe
    separada por compatibilidade de chamadores que referenciam o nome
    e pra deixar explícita a intenção de "leitura ampla incluindo
    monitoramento" — se um dia inspetor virar perfil distinto de
    professor, esta classe é o ponto de retomada.
    """

    PERFIS_PERMITIDOS = frozenset(
        {
            _PERFIL_DIRETOR,
            _PERFIL_SECRETARIA,
            _PERFIL_PROFESSOR,
            _PERFIL_INSPETOR,
        }
    )
