"""Mixins de view reutilizáveis."""


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
