"""Helpers compartilhados pelos PDFs gerados com WeasyPrint.

Três views geram PDF hoje (boletim, diário de aula e relatório de
frequência) e as três precisavam das mesmas duas coisas: chamar o
WeasyPrint e achar o caminho absoluto da logo. Até o segundo consumidor
a duplicação era tolerável; no terceiro passou a ser o lugar errado pra
descobrir que uma das cópias ficou atrás.
"""
from __future__ import annotations

import unicodedata


def render_pdf(html_str: str) -> bytes:
    """Renderiza HTML em PDF.

    O import do WeasyPrint fica lazy de propósito: a lib não carrega no
    Windows (falta GTK) e o `manage.py check` do ambiente de
    desenvolvimento precisa passar mesmo assim. Só quebra quando alguém
    de fato pede um PDF.

    As views mantêm um alias module-level (`_render_pdf = render_pdf`)
    porque os testes dão `mock.patch` nele — não dá pra interceptar uma
    chamada feita direto de dentro de outra função.
    """
    from weasyprint import HTML  # noqa: WPS433

    return HTML(string=html_str).write_pdf()


def caminho_logo() -> str:
    """Caminho absoluto da logo, pro `src="file://..."` do template.

    O WeasyPrint não tem servidor HTTP por trás: uma URL relativa de
    static não resolve. Devolve string vazia quando o arquivo não é
    encontrado (os templates já tratam com `{% if logo_path %}`), porque
    um PDF sem logo é melhor que um 500 no download.
    """
    from django.contrib.staticfiles import finders  # noqa: WPS433

    return finders.find("branding/diario-diniz-badge-128.png") or ""


def slug_arquivo(nome: str | None, *, fallback: str) -> str:
    """Transforma um nome em stem ASCII pro `Content-Disposition`.

    Acento no nome do arquivo engasga em browser antigo e em proxy que
    não fala RFC 5987, então "Ensino Médio A" sai como `ensino_medio_a`.
    Nome vazio (ou que virou vazio ao tirar os não-ASCII) cai no
    `fallback`.
    """
    if not nome:
        return fallback
    ascii_puro = (
        unicodedata.normalize("NFKD", nome)
        .encode("ascii", "ignore")
        .decode("ascii")
    )
    slug = "_".join(ascii_puro.lower().split())
    return slug or fallback
