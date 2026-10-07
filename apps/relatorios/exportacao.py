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


# Caracteres que fazem Excel e LibreOffice tratarem a célula como
# fórmula ao abrir o arquivo. Tab e CR entram porque as duas suítes os
# descartam antes de olhar o primeiro caractere de verdade.
_INICIO_DE_FORMULA = ("=", "+", "-", "@", "\t", "\r")


def neutralizar_formula(valor: Any) -> Any:
    """Impede que uma célula de texto seja executada como fórmula.

    O conteúdo destes relatórios é escrito por gente: descrição de
    ocorrência é texto livre de qualquer professor, e nome de aluno e de
    responsável podem ter vindo de uma importação de terceiro. Quem abre
    o arquivo é a secretaria, na própria máquina. Uma descrição que
    começa com `=HYPERLINK(...)` vira um link clicável montado com dados
    da planilha — e `=HYPERLINK` não dispara nem o aviso de DDE.

    A defesa padrão (OWASP) é prefixar com apóstrofo: o Excel passa a
    tratar a célula como texto e não mostra o apóstrofo. Vale pro XLSX
    também — o openpyxl converte string iniciada em `=` em fórmula.

    Número e data não são afetados: só `str` passa por aqui, e as
    colunas numéricas destes relatórios são `int`.
    """
    if isinstance(valor, str) and valor.startswith(_INICIO_DE_FORMULA):
        return f"'{valor}"
    return valor


def exportar_planilha(
    headers: list[str],
    linhas: list[list[Any]],
    *,
    formato: str,
    stem: str,
) -> HttpResponse:
    """CSV ou XLSX a partir de cabeçalho + linhas, via tablib.

    Toda célula passa por `neutralizar_formula` — é o ponto único por
    onde os três relatórios saem, então a defesa mora aqui e não em cada
    `linhas_*` de `services.py`.
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
