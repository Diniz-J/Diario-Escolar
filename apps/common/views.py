"""Mixins de view reutilizáveis."""
from apps.common.permissions import (
    IsAdminOrDiretor,
    IsAdminOrDiretorOrProfessor,
)


class EscopoEscolaMixin:
    """Restringe `get_queryset()` à escola do `request.user`.

    Usar em ViewSets cujo modelo herda de `BaseModelEscopado` (tem campo
    `escola` FK pra `escola.Escola`).

    Bypass:
    - `is_superuser=True` ou `perfil="admin"` → vê todas as escolas.

    Usuário autenticado sem `escola` vinculada (ex.: superuser sem escola
    operando como diretor de mentira) recebe queryset vazio — assim o vazamento
    entre escolas é impossível mesmo se a permission classe falhar.

    Convenção: este mixin assume queryset sobre um modelo com campo `escola_id`.
    Para `EscolaViewSet`, sobrescrever `get_queryset` manualmente porque o
    filtro precisa ser por `id` (a Escola é o tenant root, não tem FK pra si).
    """

    _PERFIL_ADMIN = "admin"

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if not user.is_authenticated:
            return qs.none()
        if user.is_superuser or getattr(user, "perfil", None) == self._PERFIL_ADMIN:
            return qs
        if not getattr(user, "escola_id", None):
            return qs.none()
        return qs.filter(escola_id=user.escola_id)


class ReadWritePermissionMixin:
    """Resolve `permission_classes` por ação: leitura mais ampla que escrita.

    Subclasses customizam `READ_PERMISSION` e `WRITE_PERMISSION`. As ações
    `list` e `retrieve` usam READ; o restante usa WRITE.

    Defaults imitam o padrão do projeto:
    - Leitura: admin/diretor/professor.
    - Escrita: admin/diretor.

    Apps com necessidades diferentes (ex.: `presenca` inclui inspetor na
    leitura; `ocorrencias` libera escrita pra professor) sobrescrevem os
    atributos de classe.
    """

    READ_PERMISSION = IsAdminOrDiretorOrProfessor
    WRITE_PERMISSION = IsAdminOrDiretor

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [self.READ_PERMISSION()]
        return [self.WRITE_PERMISSION()]
