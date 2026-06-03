"""Mixin de ViewSet pra expor 3 actions: `export`, `import`, `template`.

Plugado em qualquer ViewSet que tenha um `Resource` correspondente. O
ViewSet só precisa declarar `import_export_resource = MeuResource` e
opcionalmente `import_export_nome_arquivo = "alunos"` (default: nome do
modelo em snake_case).

Comportamento:
- **`GET .../export/?formato=csv|xlsx`** — exporta queryset escopado.
  Mesma permissão da action `list` (leitura).
- **`GET .../template/?formato=csv|xlsx`** — devolve só o cabeçalho.
  Mesma permissão da `list` (qualquer um que possa ver, pode baixar
  o template — não revela dados).
- **`POST .../import/`** — upload `arquivo` (multipart) + opcionais.
  Sempre roda dry-run primeiro. Com `?confirmar=true` e sem erros,
  persiste. Permissão de escrita (`WRITE_PERMISSION`).

`extras` do `ImportContext` são populados a partir de query params
específicos por entidade (ex.: `turno_padrao` no upload de Aluno). A
view chamadora pode sobrescrever `get_import_extras(request)` pra
controlar isso.
"""
from __future__ import annotations

from rest_framework import status
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.common.import_export import (
    FORMATOS,
    ImportContext,
    executar_export,
    executar_import,
    executar_template,
)


class ImportExportViewSetMixin:
    """Adiciona actions de export/import/template ao ViewSet.

    Configuração (no ViewSet):
        import_export_resource: classe do Resource (obrigatório).
        import_export_nome_arquivo: stem do arquivo de download
            (default: meta.model_name).

    Override opcionais:
        get_import_extras(self, request) -> dict
            Devolve extras pro `ImportContext.extras`. Default: vazio.
    """

    import_export_resource = None
    import_export_nome_arquivo: str | None = None

    # ------------------------------------------------------------------ #
    # Helpers                                                            #
    # ------------------------------------------------------------------ #

    def _validar_formato(self, request) -> tuple[str | None, Response | None]:
        formato = (request.query_params.get("formato") or "csv").lower()
        if formato not in FORMATOS:
            return None, Response(
                {
                    "detail": (
                        f"Formato inválido: '{formato}'. "
                        "Use csv ou xlsx."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        return formato, None

    def _nome_arquivo(self) -> str:
        if self.import_export_nome_arquivo:
            return self.import_export_nome_arquivo
        # Fallback baseado no model. Ex.: Aluno → "aluno".
        model = getattr(self, "queryset", None)
        if model is not None:
            return model.model._meta.model_name
        return "export"

    def _contexto(self, request, *, com_extras: bool = False) -> ImportContext:
        escola_id = None
        if request.user.is_authenticated:
            escola_id = getattr(request.user, "escola_id", None)
            # Admin global pode escolher escola via ?escola=<id> pra export
            # e importar com escopo da escola alvo. Sem isso, o
            # BaseEscolaResource devolve queryset vazio (defensivo).
            forcada = request.query_params.get("escola")
            if forcada and (
                request.user.is_superuser
                or getattr(request.user, "perfil", None) == "admin"
            ):
                try:
                    escola_id = int(forcada)
                except ValueError:
                    pass
        extras = self.get_import_extras(request) if com_extras else {}
        return ImportContext(
            escola_id=escola_id,
            usuario=request.user,
            extras=extras,
        )

    def get_import_extras(self, request) -> dict:
        """Override pra passar parâmetros extras pro Resource."""
        return {}

    # ------------------------------------------------------------------ #
    # Actions                                                            #
    # ------------------------------------------------------------------ #

    @action(
        detail=False,
        methods=["get"],
        url_path="export",
        permission_classes=[IsAuthenticated],
    )
    def export(self, request):
        """`GET /<entidade>/export/?formato=csv|xlsx`."""
        # Reaproveita a permissão de READ (leitura).
        self.check_permissions(request)
        formato, erro = self._validar_formato(request)
        if erro:
            return erro
        contexto = self._contexto(request)
        return executar_export(
            resource_class=self.import_export_resource,
            contexto=contexto,
            formato=formato,
            nome_arquivo=self._nome_arquivo(),
        )

    @action(
        detail=False,
        methods=["get"],
        url_path="template",
        permission_classes=[IsAuthenticated],
    )
    def template(self, request):
        """`GET /<entidade>/template/?formato=csv|xlsx`."""
        formato, erro = self._validar_formato(request)
        if erro:
            return erro
        return executar_template(
            resource_class=self.import_export_resource,
            formato=formato,
            nome_arquivo=self._nome_arquivo(),
        )

    @action(
        detail=False,
        methods=["post"],
        url_path="import",
        parser_classes=[MultiPartParser, FormParser],
    )
    def importar(self, request):
        """`POST /<entidade>/import/` — multipart com campo `arquivo`.

        Query params:
            confirmar=true: persiste após dry-run sem erros (default false).
        """
        arquivo = request.FILES.get("arquivo")
        if not arquivo:
            return Response(
                {
                    "detail": (
                        "Envie o arquivo CSV ou XLSX no campo 'arquivo'."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        confirmar = (
            request.query_params.get("confirmar", "").lower() == "true"
        )
        contexto = self._contexto(request, com_extras=True)
        if contexto.escola_id is None:
            return Response(
                {
                    "detail": (
                        "Sua conta não está vinculada a uma escola. "
                        "Importes em massa exigem escopo de escola."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        return executar_import(
            resource_class=self.import_export_resource,
            contexto=contexto,
            arquivo=arquivo,
            confirmar=confirmar,
        )

    def get_permissions(self):
        """Escrita pro `import`, leitura pro `export`/`template`.

        Reaproveita `READ_PERMISSION`/`WRITE_PERMISSION` do
        `ReadWritePermissionMixin` quando presentes; caso contrário cai
        pro padrão do ViewSet base.
        """
        if self.action == "importar":
            write_perm = getattr(self, "WRITE_PERMISSION", None)
            if write_perm:
                return [write_perm()]
        elif self.action in ("export", "template"):
            read_perm = getattr(self, "READ_PERMISSION", None)
            if read_perm:
                return [read_perm()]
        return super().get_permissions()
