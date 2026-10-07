"""Views dos relatórios operacionais.

Um endpoint por relatório, cada um servindo quatro formatos no mesmo
recorte (`?formato=json|pdf|csv|xlsx`): a tela consome o JSON e os
outros três são download. Um endpoint por formato multiplicaria rota e
filtro sem necessidade.

Escopo: o recorte vem sempre de uma turma da escola do usuário. Turma de
outra escola responde 404 — igual ao período em
`boletins.services.resolver_janela_por_periodo`, pra resposta não
confirmar que o id existe.
"""
from __future__ import annotations

from datetime import date

from django.template.loader import render_to_string
from django.utils import timezone
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.boletins.services import resolver_janela_por_periodo
from apps.common.pdf import caminho_logo, render_pdf, slug_arquivo
from apps.common.permissions import (
    IsAdminOrDiretorOrProfessorOrInspetor,
    eh_admin_global,
)
from apps.escola.models import Turma

from .exportacao import (
    FORMATOS_PLANILHA,
    exportar_planilha,
    resolver_formato,
    resposta_download,
)
from .services import frequencia_por_turma, linhas_planas

# Alias module-level: o render mora em `apps/common/pdf.py`, mas o nome
# fica aqui porque os testes dão `mock.patch` em
# `apps.relatorios.views._render_pdf`.
_render_pdf = render_pdf

FORMATOS = ("json", "pdf", *FORMATOS_PLANILHA)


def _parse_date(valor: str | None, nome_param: str) -> date | None:
    """Converte `YYYY-MM-DD` em `date`. Vazio ou ausente → None."""
    if not valor:
        return None
    try:
        return date.fromisoformat(valor)
    except ValueError as exc:
        raise ValidationError(
            {nome_param: "Formato inválido. Use YYYY-MM-DD."}
        ) from exc


def _resolver_turma(request) -> Turma:
    """Turma do recorte, já validada contra a escola do usuário.

    Obrigatória: um relatório de frequência sem turma seria a escola
    inteira num PDF, e nenhuma tela pede isso — a mesma razão do
    `FiltroEscopoObrigatorioMixin` nos endpoints matriz.
    """
    turma_id = request.query_params.get("turma")
    if not turma_id:
        raise ValidationError(
            {"turma": "Informe a turma do relatório."}
        )
    qs = Turma.objects.select_related("escola")
    if not eh_admin_global(request.user):
        escola_id = getattr(request.user, "escola_id", None)
        qs = qs.filter(escola_id=escola_id) if escola_id else qs.none()
    turma = qs.filter(pk=turma_id).first()
    if turma is None:
        raise NotFound("Turma não encontrada.")
    return turma


def _resolver_janela(request, escola_id: int):
    """Janela de datas do recorte, com `?periodo=` tendo precedência.

    Mesmo contrato do boletim: `?periodo=<id>` é atalho de UI e ganha de
    `?data_inicio/?data_fim`; sem nenhum dos dois, a janela é aberta
    (todas as chamadas da turma). A resolução do período reusa o serviço
    do boletim, que já recusa período de outra escola.
    """
    periodo_id_raw = request.query_params.get("periodo")
    try:
        periodo_id = int(periodo_id_raw) if periodo_id_raw else None
    except ValueError:
        # Antes era ignorado em silêncio e virava janela aberta: o
        # relatório saía "de todo o período" sem a secretaria saber que o
        # filtro não pegou.
        raise ValidationError({"periodo": "Período inválido."})

    if periodo_id:
        return resolver_janela_por_periodo(periodo_id, escola_id)

    data_inicio = _parse_date(request.query_params.get("data_inicio"), "data_inicio")
    data_fim = _parse_date(request.query_params.get("data_fim"), "data_fim")
    if data_inicio and data_fim and data_inicio > data_fim:
        # Intervalo invertido devolvia um relatório válido com tudo zerado.
        raise ValidationError(
            {"data_fim": "A data final não pode ser anterior à inicial."}
        )
    return data_inicio, data_fim, None


def _descrever_janela(relatorio: dict, periodo) -> str:
    """Rótulo legível do recorte, pro cabeçalho do PDF."""
    if periodo is not None:
        return periodo.nome
    janela = relatorio["janela"]
    inicio, fim = janela["data_inicio"], janela["data_fim"]
    if inicio and fim:
        return f"{_br(inicio)} a {_br(fim)}"
    if inicio:
        return f"a partir de {_br(inicio)}"
    if fim:
        return f"até {_br(fim)}"
    return "Todo o período registrado"


def _br(iso: str) -> str:
    """`2026-03-01` → `01/03/2026`."""
    ano, mes, dia = iso.split("-")
    return f"{dia}/{mes}/{ano}"


class RelatorioFrequenciaView(APIView):
    """`GET /relatorios/frequencia/`.

    Params: `turma` (obrigatório), `periodo` ou
    `data_inicio`/`data_fim`, `formato` (json, pdf, csv, xlsx).

    Leitura aberta a professor e inspetor, igual ao boletim: quem lança
    a chamada precisa conseguir conferir o resultado dela.
    """

    permission_classes = [
        IsAuthenticated,
        IsAdminOrDiretorOrProfessorOrInspetor,
    ]

    def get(self, request):
        formato = resolver_formato(request, FORMATOS, default="json")
        turma = _resolver_turma(request)
        data_inicio, data_fim, periodo = _resolver_janela(
            request, turma.escola_id
        )
        relatorio = frequencia_por_turma(turma, data_inicio, data_fim)

        if formato == "json":
            return Response(relatorio)

        stem = f"frequencia_{slug_arquivo(turma.nome, fallback='turma')}"

        if formato in FORMATOS_PLANILHA:
            headers, linhas = linhas_planas(relatorio)
            return exportar_planilha(
                headers, linhas, formato=formato, stem=stem
            )

        contexto = {
            **relatorio,
            "escola_nome": turma.escola.nome,
            "recorte": _descrever_janela(relatorio, periodo),
            "gerado_em": timezone.localtime(),
            "logo_path": caminho_logo(),
        }
        html_str = render_to_string(
            "relatorio_frequencia_pdf.html", contexto
        )
        return resposta_download(
            _render_pdf(html_str),
            content_type="application/pdf",
            nome_arquivo=f"{stem}.pdf",
        )
