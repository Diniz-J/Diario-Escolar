"""Segurança de conteúdo em planilha (CSV/XLSX).

Mora em `common` porque os três caminhos que exportam planilha neste
projeto estão em camadas diferentes — `relatorios`, `boletins` e o
próprio `common.import_export` — e a camada base não pode importar app
de domínio.
"""
from __future__ import annotations

from typing import Any

# Caracteres que fazem Excel e LibreOffice tratarem a célula como
# fórmula ao abrir o arquivo. Tab e CR entram porque as duas suítes os
# descartam antes de olhar o primeiro caractere de verdade.
INICIO_DE_FORMULA = ("=", "+", "-", "@", "\t", "\r")

# Marcador que neutraliza a célula. O Excel lê o apóstrofo como "isto é
# texto" e não o exibe.
MARCADOR = "'"


def neutralizar_formula(valor: Any) -> Any:
    """Impede que uma célula de texto seja executada como fórmula.

    O conteúdo exportado é escrito por gente: descrição de ocorrência e
    título de avaliação são texto livre de qualquer professor, e nome de
    aluno e de responsável podem ter vindo de uma importação de
    terceiro. Quem abre o arquivo é a secretaria, na própria máquina.
    Uma célula que começa com `=HYPERLINK(...)` vira um link clicável
    montado com dados da planilha — e `=HYPERLINK` não dispara nem o
    aviso de DDE.

    A defesa padrão (OWASP) é prefixar com apóstrofo. Vale pro XLSX
    também: o openpyxl converte string iniciada em `=` em fórmula.

    Número e data não são afetados: só `str` passa por aqui.
    """
    if isinstance(valor, str) and valor.startswith(INICIO_DE_FORMULA):
        return f"{MARCADOR}{valor}"
    return valor


def desneutralizar_formula(valor: Any) -> Any:
    """Desfaz `neutralizar_formula` na leitura de uma planilha.

    Existe por causa do import/export de migração, que é round-trip: a
    escola exporta a base, edita e reimporta. Sem isto, o apóstrofo que
    protegeu a célula na saída seria gravado no banco na volta, e cada
    ciclo acumularia mais um.

    Desfaz **só o que esta casa escreveu**: apóstrofo seguido de
    caractere de fórmula. Um valor que legitimamente comece com
    apóstrofo (seguido de letra, por exemplo) passa intacto.
    """
    if (
        isinstance(valor, str)
        and valor.startswith(MARCADOR)
        and valor[1:].startswith(INICIO_DE_FORMULA)
    ):
        return valor[1:]
    return valor


def neutralizar_dataset(dataset):
    """Aplica `neutralizar_formula` em todas as células de um `Dataset`.

    O `tablib.Dataset` não deixa reescrever célula a célula, então o
    jeito é recriar as linhas. Usado onde a planilha é montada por
    terceiros (os `Resource` do django-import-export) e não há uma lista
    de linhas pra tratar antes.
    """
    linhas = [
        [neutralizar_formula(celula) for celula in linha]
        for linha in dataset
    ]
    del dataset[0 : len(dataset)]
    for linha in linhas:
        dataset.append(linha)
    return dataset


def desneutralizar_dataset(dataset):
    """Contraparte de `neutralizar_dataset`, na entrada do import."""
    linhas = [
        [desneutralizar_formula(celula) for celula in linha]
        for linha in dataset
    ]
    del dataset[0 : len(dataset)]
    for linha in linhas:
        dataset.append(linha)
    return dataset
