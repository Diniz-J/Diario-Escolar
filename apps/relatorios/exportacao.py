"""Mecânica comum de export: formato, planilha e resposta de download.

Separado de `views.py` porque o relatório de ocorrências não mora aqui:
ele é uma action do `OcorrenciaViewSet` (é lá que o filtro e o escopo da
listagem já existem). Se estes helpers ficassem na view da frequência, a
app `ocorrencias` importaria uma view pra usar três funções.
"""
from __future__ import annotations

from typing import Any, Sequence

from django.http import HttpResponse
from rest_framework.exceptions import ValidationError

from apps.common.planilha import neutralizar_formula

FORMATOS_PLANILHA = {
    "csv": "text/csv",
    "xlsx": (
        "application/vnd.openxmlformats-officedocument"
        ".spreadsheetml.sheet"
    ),
}


def resolver_formato(request, permitidos: Sequence[str], *, default: str) -> str:
    """Lê `?formato=` e recusa o que não está na lista do relatório.

    Cada relatório declara os seus: a frequência serve `json` (a tela
    pode consumir), a exportação de ocorrências não — ali o JSON é a
    própria listagem paginada.
    """
    formato = (request.query_params.get("formato") or default).lower()
    if formato not in permitidos:
        raise ValidationError(
            {"formato": f"Use um de: {', '.join(permitidos)}."}
        )
    return formato


def resposta_download(
    conteudo: bytes, *, content_type: str, nome_arquivo: str
) -> HttpResponse:
    resposta = HttpResponse(conteudo, content_type=content_type)
    resposta["Content-Disposition"] = (
        f'attachment; filename="{nome_arquivo}"'
    )
    return resposta


def exportar_planilha(
    headers: list[str],
    linhas: list[list[Any]],
    *,
    formato: str,
    stem: str,
) -> HttpResponse:
    """CSV ou XLSX a partir de cabeçalho + linhas, via tablib.

    Toda célula passa por `neutralizar_formula` (`apps/common/planilha.py`)
    — é o ponto único por onde os três relatórios saem, então a defesa
    fica aqui e não em cada `linhas_*` de `services.py`.
    """
    # Import lazy: mesmo padrão do boletim.
    import tablib  # noqa: WPS433

    dataset = tablib.Dataset(headers=headers)
    for linha in linhas:
        dataset.append([neutralizar_formula(celula) for celula in linha])

    conteudo = dataset.export(formato)
    if isinstance(conteudo, str):
        conteudo = conteudo.encode("utf-8")
    return resposta_download(
        conteudo,
        content_type=FORMATOS_PLANILHA[formato],
        nome_arquivo=f"{stem}.{formato}",
    )
