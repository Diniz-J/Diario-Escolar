"""Views da app boletins.

3 endpoints:
- `GET /boletins/aluno/{aluno_id}/` — JSON do boletim.
- `GET /boletins/aluno/{aluno_id}/pdf/` — boletim em PDF via WeasyPrint.
- `GET /boletins/aluno/{aluno_id}/avaliacoes/` — CSV ou XLSX plano com
  todas as avaliações do aluno na janela.

Todos aceitam `?periodo=<id>` como atalho pra um `PeriodoAvaliativo`
específico (resolve `data_inicio`/`data_fim` automaticamente) ou
`?data_inicio=YYYY-MM-DD&data_fim=YYYY-MM-DD` pra janela manual. Sem
nada significa "tudo" (boletim anual).
"""
from datetime import date

from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.permissions import IsAdminOrDiretorOrProfessorOrInspetor
from apps.escola.models import Aluno

from .services import (
    listar_avaliacoes_do_aluno,
    montar_boletim,
    resolver_janela_por_periodo,
)


def _parse_date(valor: str | None, nome_param: str) -> date | None:
    """Converte `YYYY-MM-DD` em `date`. Vazio ou None → None."""
    if not valor:
        return None
    try:
        return date.fromisoformat(valor)
    except ValueError as exc:
        raise ValidationError(
            {nome_param: "Formato inválido. Use YYYY-MM-DD."}
        ) from exc


def _checar_acesso_aluno(request, aluno: Aluno) -> None:
    """Defesa de IDOR — não-admin só vê aluno da própria escola."""
    user = request.user
    if user.is_superuser or getattr(user, "perfil", None) == "admin":
        return
    user_escola_id = getattr(user, "escola_id", None)
    if user_escola_id and aluno.escola_id != user_escola_id:
        raise PermissionDenied("Aluno fora da sua escola.")


def _render_pdf(html_str: str) -> bytes:
    """Helper module-level: chama WeasyPrint pra render HTML→PDF.

    Extraído pra um nível de função pra ficar mockável nos testes
    (não dá pra patch numa importação `from X import Y` que mora
    dentro de outra função). O import do WeasyPrint é mantido lazy
    aqui mesmo — `manage.py check` no Windows continua funcionando
    porque a lib só é carregada quando esta função é chamada.
    """
    from weasyprint import HTML  # noqa: WPS433

    return HTML(string=html_str).write_pdf()


def _resolver_filtros(request) -> tuple[date | None, date | None, object]:
    """Resolve janela de datas + período opcional a partir da query string.

    Precedência: `?periodo=<id>` ganha sobre `?data_inicio/data_fim`
    (atalho de UI). Sem nenhum dos dois → janela vazia (boletim anual).
    """
    periodo_id_raw = request.query_params.get("periodo")
    try:
        periodo_id = int(periodo_id_raw) if periodo_id_raw else None
    except ValueError:
        periodo_id = None

    if periodo_id:
        data_inicio, data_fim, periodo = resolver_janela_por_periodo(
            periodo_id
        )
        return data_inicio, data_fim, periodo

    data_inicio = _parse_date(
        request.query_params.get("data_inicio"), "data_inicio"
    )
    data_fim = _parse_date(
        request.query_params.get("data_fim"), "data_fim"
    )
    return data_inicio, data_fim, None


class BoletimAlunoView(APIView):
    """`GET /boletins/aluno/{aluno_id}/` — JSON do boletim."""

    permission_classes = [
        IsAuthenticated,
        IsAdminOrDiretorOrProfessorOrInspetor,
    ]

    def get(self, request, aluno_id: int):
        aluno = get_object_or_404(
            Aluno.objects.select_related("turma", "escola"),
            pk=aluno_id,
        )
        _checar_acesso_aluno(request, aluno)
        data_inicio, data_fim, periodo = _resolver_filtros(request)
        return Response(
            montar_boletim(aluno, data_inicio, data_fim, periodo=periodo)
        )


class BoletimAlunoPDFView(APIView):
    """`GET /boletins/aluno/{aluno_id}/pdf/?periodo=X` — PDF via WeasyPrint.

    Sem `?periodo` e sem datas, gera anual com tudo. O template HTML
    fica em `apps/boletins/templates/boletim_pdf.html` — agnostico do
    backend de renderização (qualquer ferramenta HTML→PDF serve).
    """

    permission_classes = [
        IsAuthenticated,
        IsAdminOrDiretorOrProfessorOrInspetor,
    ]

    def get(self, request, aluno_id: int):
        aluno = get_object_or_404(
            Aluno.objects.select_related("turma", "escola"),
            pk=aluno_id,
        )
        _checar_acesso_aluno(request, aluno)
        data_inicio, data_fim, periodo = _resolver_filtros(request)

        contexto = montar_boletim(
            aluno, data_inicio, data_fim, periodo=periodo
        )
        html_str = render_to_string("boletim_pdf.html", contexto)
        pdf_bytes = _render_pdf(html_str)

        # Nome do arquivo: `boletim_<matricula>_<periodo>.pdf`
        sufixo = (
            f"_{periodo.nome.replace(' ', '_').lower()}"
            if periodo
            else "_anual"
        )
        nome_arquivo = f"boletim_{aluno.matricula}{sufixo}.pdf"

        resposta = HttpResponse(pdf_bytes, content_type="application/pdf")
        resposta["Content-Disposition"] = (
            f'attachment; filename="{nome_arquivo}"'
        )
        return resposta


class BoletimAlunoAvaliacoesView(APIView):
    """`GET /boletins/aluno/{aluno_id}/avaliacoes/?formato=csv|xlsx`.

    Lista plana de TODAS as avaliações do aluno na janela — uma linha
    por NotaAvaliacao, mesmo se ainda não foi lançada (`nota_obtida`
    fica vazia). Pra escola fechar média no Excel se quiser.
    """

    permission_classes = [
        IsAuthenticated,
        IsAdminOrDiretorOrProfessorOrInspetor,
    ]

    def get(self, request, aluno_id: int):
        aluno = get_object_or_404(
            Aluno.objects.select_related("turma", "escola"),
            pk=aluno_id,
        )
        _checar_acesso_aluno(request, aluno)
        data_inicio, data_fim, periodo = _resolver_filtros(request)

        formato = (request.query_params.get("formato") or "csv").lower()
        if formato not in {"csv", "xlsx"}:
            raise ValidationError(
                {"formato": "Use 'csv' ou 'xlsx'."}
            )

        linhas = listar_avaliacoes_do_aluno(aluno, data_inicio, data_fim)

        # Import lazy — tablib é dep mais leve, mas mantemos o padrão.
        import tablib  # noqa: WPS433

        headers = [
            "disciplina",
            "periodo",
            "data",
            "tipo",
            "titulo",
            "nota_maxima",
            "nota_obtida",
            "peso",
        ]
        dataset = tablib.Dataset(headers=headers)
        for linha in linhas:
            dataset.append([linha[h] for h in headers])

        conteudo = dataset.export(formato)
        if isinstance(conteudo, str):
            conteudo = conteudo.encode("utf-8")

        content_type = (
            "text/csv"
            if formato == "csv"
            else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        sufixo = f"_{periodo.nome.replace(' ', '_').lower()}" if periodo else ""
        nome_arquivo = (
            f"avaliacoes_{aluno.matricula}{sufixo}.{formato}"
        )
        resposta = HttpResponse(conteudo, content_type=content_type)
        resposta["Content-Disposition"] = (
            f'attachment; filename="{nome_arquivo}"'
        )
        return resposta
