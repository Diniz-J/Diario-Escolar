"""Helpers compartilhados de import/export.

Camada fina sobre `django-import-export`:

- `BaseEscolaResource`: força o filtro por escola no export e injeta
  `escola_id` em toda linha importada. Subclasses só precisam declarar
  `class Meta` com `model` e `fields`.
- `ImportContext`: estrutura passada da view pro resource carregando
  `escola_id`, `usuario` e parâmetros opcionais do upload (turno padrão,
  ano letivo padrão etc.) — evita usar variáveis globais.
- `executar_export`/`executar_import`: helpers chamados pelas actions
  custom dos ViewSets pra encapsular parsing, dry-run e response.

Decisões importantes:

- **Não habilitamos `import_export` no INSTALLED_APPS.** Não queremos os
  mixins de admin (`ImportExportModelAdmin`); o fluxo é via API REST.
  Importando só `import_export.resources.ModelResource` funciona como
  biblioteca pura.
- **Dedup = pular existentes.** Implementado via `skip_row` que olha a
  chave natural do modelo (`get_instance` do `ModelResource`). Quando
  já existe, conta como "pulado" e a linha não é nem atualizada nem
  recriada.
- **Sempre dry-run primeiro.** A view dispara `import_data(dry_run=True)`
  pra coletar erros por linha; só repete com `dry_run=False` se o
  cliente confirmar (`?confirmar=true`). Em ambos os casos `transaction.atomic()`
  do `django-import-export` garante atomicidade.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import tablib
from django.http import FileResponse, HttpResponse
from import_export import resources
from rest_framework import status
from rest_framework.response import Response


# Formatos suportados pelo export/import. Mapeia o nome amigável
# (passado na query string) pra extensão + content-type.
FORMATOS = {
    "csv": {"ext": "csv", "content_type": "text/csv"},
    "xlsx": {
        "ext": "xlsx",
        "content_type": (
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ),
    },
}


@dataclass
class ImportContext:
    """Contexto carregado da view pro resource durante o import.

    `extras` cobre parâmetros opcionais do upload (turno padrão pra
    criação automática de turma, ano letivo padrão etc.) sem ter que
    estender esta classe pra cada caso novo.
    """

    escola_id: int | None
    usuario: Any  # `apps.accounts.models.Usuario`, mas evitamos o import circular
    extras: dict[str, Any] = field(default_factory=dict)


class BaseEscolaResource(resources.ModelResource):
    """Resource base com escopo de escola e dedup "pular existentes".

    Subclasses devem:
    - Declarar `class Meta` com `model` e `fields` (e opcionalmente
      `import_id_fields` se a chave natural não for o `pk`).
    - Sobrescrever `before_import_row` quando precisarem resolver FK por
      nome (ex.: `turma` por `(nome, ano_letivo)` em vez de id).

    Comportamento herdado:
    - `get_queryset`: filtra pelo `escola_id` recebido via `ImportContext`
      (se `None`, devolve queryset vazio — admin global precisa passar
      `escola_id` explicitamente).
    - `before_import_row`: injeta `escola` quando ausente.
    - `skip_row`: pula registro existente (mesma chave natural).
    - `after_import_row`: contabiliza pulados num atributo da instância
      (acessível pela view via `resource.skipped`).
    """

    def __init__(self, contexto: ImportContext | None = None, **kwargs):
        super().__init__(**kwargs)
        self.contexto = contexto
        # Linhas puladas por já existirem (chave natural duplicada).
        # `import_export` não expõe isso nativamente — `result.totals`
        # só conta new/update/delete/skip_unchanged, e nossos "skip por
        # dedup" caem em `skip` mas misturados com outros. Mantemos
        # nosso próprio contador pra resposta clara.
        self.duplicados: list[dict[str, Any]] = []

    # ------------------------------------------------------------------ #
    # Export                                                             #
    # ------------------------------------------------------------------ #

    def get_queryset(self):
        """Filtra o export pela escola do contexto.

        Sem contexto (ou contexto sem escola), devolve queryset vazio —
        defensivo. A view sempre passa contexto válido.
        """
        qs = super().get_queryset()
        if self.contexto is None or self.contexto.escola_id is None:
            # Admin global: a view passa `escola_id` selecionada
            # explicitamente. Sem isso, evitamos vazar dados de todas
            # as escolas num único arquivo.
            return qs.none()
        return qs.filter(escola_id=self.contexto.escola_id)

    # ------------------------------------------------------------------ #
    # Import — escopo de escola + dedup                                  #
    # ------------------------------------------------------------------ #

    def before_import_row(self, row, **kwargs):  # noqa: ARG002
        """Injeta a escola do contexto na linha (se ausente).

        Roda antes de toda a pipeline de validação/save. Subclasses
        podem chamar `super().before_import_row(row, **kwargs)` e
        depois adicionar resolução de FK por nome.
        """
        if self.contexto and self.contexto.escola_id is not None:
            # `row` é um dict-like. `escola` no resource é um campo FK
            # numérico — o widget converte int → instância no instance loader.
            row.setdefault("escola", self.contexto.escola_id)

    def skip_row(self, instance, original, row, import_validation_errors=None):
        """Pula linha cuja chave natural já existe no banco.

        `original` é a instância carregada por `get_instance` (None se
        não existe). Quando existe e o usuário pediu "pular duplicados"
        (comportamento padrão deste base resource), retornamos True e
        registramos no contador.
        """
        if original is not None and original.pk is not None:
            # Captura o identificador "humano" da linha (definido por
            # subclasse via `_descricao_linha`) pra reportar no resumo.
            self.duplicados.append(
                {
                    "linha": self._descricao_linha(row),
                    "motivo": "Já existe — pulado.",
                }
            )
            return True
        return super().skip_row(
            instance, original, row, import_validation_errors=import_validation_errors
        )

    # ------------------------------------------------------------------ #
    # Hooks customizáveis                                                #
    # ------------------------------------------------------------------ #

    def _descricao_linha(self, row) -> str:
        """Retorna uma string curta identificando a linha no log/resumo.

        Subclasses sobrescrevem pra puxar o campo mais legível (nome do
        aluno, nome da turma etc.). Default cai pro primeiro valor que
        encontrar nas colunas `import_id_fields`.
        """
        ids = getattr(self._meta, "import_id_fields", ("id",))
        partes = [str(row.get(c, "")) for c in ids if row.get(c)]
        return " / ".join(partes) or "linha sem identificação"


# ---------------------------------------------------------------------- #
# Helpers das actions de ViewSet                                         #
# ---------------------------------------------------------------------- #


def executar_export(
    *,
    resource_class: type[BaseEscolaResource],
    contexto: ImportContext,
    formato: str,
    nome_arquivo: str,
) -> HttpResponse:
    """Executa export e devolve `FileResponse` pra download.

    `formato` é "csv" ou "xlsx" (validado pela action chamadora).
    `nome_arquivo` é o stem do arquivo (sem extensão) — geralmente o
    nome do modelo. A extensão e o content-type são adicionados aqui.
    """
    config = FORMATOS[formato]
    resource = resource_class(contexto=contexto)
    dataset: tablib.Dataset = resource.export()
    conteudo = dataset.export(formato)

    if isinstance(conteudo, str):
        conteudo = conteudo.encode("utf-8")

    resposta = HttpResponse(conteudo, content_type=config["content_type"])
    resposta["Content-Disposition"] = (
        f'attachment; filename="{nome_arquivo}.{config["ext"]}"'
    )
    return resposta


def executar_template(
    *,
    resource_class: type[BaseEscolaResource],
    formato: str,
    nome_arquivo: str,
) -> HttpResponse:
    """Devolve template vazio (só cabeçalhos) pro usuário preencher.

    Não precisa de contexto de escola — é só o esqueleto.
    """
    config = FORMATOS[formato]
    resource = resource_class()
    # `get_export_headers()` devolve os nomes das colunas conforme o
    # resource. Criamos um Dataset vazio com esses headers.
    dataset = tablib.Dataset(headers=resource.get_export_headers())
    conteudo = dataset.export(formato)

    if isinstance(conteudo, str):
        conteudo = conteudo.encode("utf-8")

    resposta = HttpResponse(conteudo, content_type=config["content_type"])
    resposta["Content-Disposition"] = (
        f'attachment; filename="{nome_arquivo}_modelo.{config["ext"]}"'
    )
    return resposta


def _carregar_dataset(arquivo, nome: str) -> tablib.Dataset:
    """Lê um upload (`UploadedFile`) e devolve `Dataset` parseado.

    Detecta formato pela extensão do nome do arquivo. Levanta `ValueError`
    quando a extensão não é suportada ou o conteúdo não pode ser parseado.
    """
    nome_lower = (nome or "").lower()
    if nome_lower.endswith(".xlsx"):
        formato = "xlsx"
    elif nome_lower.endswith(".csv"):
        formato = "csv"
    else:
        raise ValueError(
            "Formato não suportado. Envie um arquivo .csv ou .xlsx."
        )

    conteudo = arquivo.read()
    dataset = tablib.Dataset()
    # tablib usa `.load(stream, format=...)` — pra CSV precisa de string,
    # pra XLSX precisa de bytes.
    if formato == "csv":
        try:
            conteudo_texto = conteudo.decode("utf-8-sig")
        except UnicodeDecodeError:
            # Fallback pra planilhas exportadas do Excel em latin-1.
            conteudo_texto = conteudo.decode("latin-1")
        dataset.load(conteudo_texto, format="csv")
    else:
        dataset.load(conteudo, format="xlsx")
    return dataset


def executar_import(
    *,
    resource_class: type[BaseEscolaResource],
    contexto: ImportContext,
    arquivo,
    confirmar: bool,
) -> Response:
    """Executa import (dry-run e/ou confirmação) e devolve `Response` JSON.

    Sempre roda dry-run primeiro pra coletar erros por linha. Se
    `confirmar=False`, devolve o relatório do dry-run sem persistir.
    Se `confirmar=True` e o dry-run não tiver erros, repete com
    `dry_run=False` pra persistir.

    Resposta:
        {
            "criados": int,
            "pulados": [{"linha": "...", "motivo": "..."}, ...],
            "erros": [{"linha": int, "campo": str|None, "mensagem": str}, ...],
            "persistido": bool,
        }
    """
    try:
        dataset = _carregar_dataset(arquivo, getattr(arquivo, "name", ""))
    except ValueError as exc:
        return Response(
            {"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST
        )
    except Exception as exc:  # noqa: BLE001 — feedback claro
        return Response(
            {
                "detail": (
                    "Não foi possível ler o arquivo. Verifique o formato "
                    "e os cabeçalhos."
                ),
                "erro_tecnico": str(exc),
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Single-pass: rodar 2x (dry-run + persist) duplica side-effects.
    # No `AlunoResource.before_import_row` criamos a turma faltante
    # FORA da `transaction.atomic` do import_data (porque `Turma.objects.create`
    # foge da transação do save da linha). No primeiro pass (dry_run) ela
    # ficava criada, no segundo pass (persist) tentava criar de novo e
    # batia em UniqueViolation. Com 1 pass:
    # - `confirmar=False` → `dry_run=True`: a lib faz rollback do
    #   savepoint atômico no fim. Relatório de erros sem persistir.
    # - `confirmar=True` → `dry_run=False`: persiste. Em erro de linha,
    #   `raise_errors=False` registra no `result` em vez de levantar.
    resource = resource_class(contexto=contexto)
    result = resource.import_data(
        dataset,
        dry_run=not confirmar,
        raise_errors=False,
        # `collect_failed_rows` é incompatível com nossos resources que
        # mutam chaves no `before_import_row` — tablib rejeita rows com
        # número de colunas diferente do header inicial. Sem o flag,
        # `row_errors()` ainda dá tudo que precisamos pro relatório.
        collect_failed_rows=False,
    )
    erros = _coletar_erros(result)
    return Response(
        {
            "criados": result.totals.get("new", 0),
            "pulados": list(resource.duplicados),
            "erros": erros,
            "persistido": confirmar and not erros,
        },
        status=status.HTTP_200_OK,
    )


def _coletar_erros(result) -> list[dict[str, Any]]:
    """Achata os erros de um `Result` do django-import-export.

    O `Result` tem `row_errors()` (lista de tuplas `(linha, [Error, ...])`)
    e cada `Error` tem `error`, `traceback`, e `row`. Pegamos só o que
    importa pro usuário.
    """
    erros: list[dict[str, Any]] = []
    for numero_linha, errors_da_linha in result.row_errors():
        for erro in errors_da_linha:
            mensagem = str(erro.error)
            erros.append(
                {
                    "linha": numero_linha,
                    "mensagem": mensagem,
                }
            )
    # `invalid_rows` cobre erros de validação (ValidationError) — a
    # estrutura é diferente dos `row_errors` (exceptions cruas).
    for linha_invalida in getattr(result, "invalid_rows", []) or []:
        for campo, mensagens in (linha_invalida.error_dict or {}).items():
            for msg in mensagens:
                erros.append(
                    {
                        "linha": linha_invalida.number,
                        "campo": campo if campo != "__all__" else None,
                        "mensagem": str(msg),
                    }
                )
    return erros
