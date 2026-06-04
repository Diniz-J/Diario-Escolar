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

    def _validar_escola_habilitada(
        self, escola_id: int | None
    ) -> Response | None:
        """Garante que a escola alvo contratou o pacote de import/export.

        Import/export em massa é serviço operado **exclusivamente** pelo
        admin global (Diniz) — não fica aberto pra diretor mexer sozinho.
        O `Escola.importacao_em_lote_habilitada` é o flag comercial que
        marca quais escolas estão dentro do pacote contratado.

        Retorna `Response` com erro se:
        - `escola_id` é None (sem alvo definido — admin precisa passar
          `?escola=<id>`);
        - escola não existe;
        - escola existe mas o flag está desligado.

        Retorna `None` se tudo OK — chamadora segue o fluxo normal.
        """
        if escola_id is None:
            return Response(
                {
                    "detail": (
                        "Selecione a escola alvo antes de operar "
                        "import/export."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        # Import lazy pra evitar ciclo com apps.escola (que importa este
        # módulo via apps.escola.views).
        from apps.escola.models import Escola

        habilitada = (
            Escola.objects.filter(pk=escola_id)
            .values_list("importacao_em_lote_habilitada", flat=True)
            .first()
        )
        if habilitada is None:
            return Response(
                {"detail": "Escola não encontrada."},
                status=status.HTTP_404_NOT_FOUND,
            )
        if not habilitada:
            return Response(
                {
                    "detail": (
                        "Esta escola não tem o pacote de importação em "
                        "lote contratado. Procure o administrador do "
                        "sistema pra habilitar."
                    )
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        return None

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
        erro_escola = self._validar_escola_habilitada(contexto.escola_id)
        if erro_escola:
            return erro_escola
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
        # Template é só esqueleto (sem dado), mas o gating é comercial:
        # só baixa template pra escola que contratou o pacote. Mantém
        # UX consistente — quem não tem acesso à feature não tem acesso
        # a NADA da feature.
        contexto = self._contexto(request)
        erro_escola = self._validar_escola_habilitada(contexto.escola_id)
        if erro_escola:
            return erro_escola
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
        erro_escola = self._validar_escola_habilitada(contexto.escola_id)
        if erro_escola:
            return erro_escola
        return executar_import(
            resource_class=self.import_export_resource,
            contexto=contexto,
            arquivo=arquivo,
            confirmar=confirmar,
        )

    def get_permissions(self):
        """Import/export/template são admin-only.

        Decisão de produto: a feature inteira é serviço operado
        exclusivamente pelo admin global (Diniz) — escola não mexe
        sozinha, mesmo que tenha contratado o pacote. O flag
        `Escola.importacao_em_lote_habilitada` é a segunda camada
        (gate comercial), validada em `_validar_escola_habilitada`.
        """
        # Import lazy pra evitar circular import (apps.common → apps.common.permissions
        # não cicla, mas mantemos o padrão consistente com o resto do mixin).
        from apps.common.permissions import IsAdmin

        if self.action in ("importar", "export", "template"):
            return [IsAdmin()]
        return super().get_permissions()
