"""Views da app ocorrencias — CRUD escopado por escola.

Diferente do padrão das outras apps, **professor também escreve** aqui:
ocorrências são registradas no dia a dia pelos professores, não apenas
por admin/diretor.

Decisão consciente: a permissão é uniforme em todas as ações (list,
retrieve, create, update, partial_update, destroy). Qualquer
admin/diretor/professor da mesma escola pode editar status de ocorrência
aberta por outro professor — o caso de uso é colega ajudando colega
(especialmente professores mais novos auxiliando os mais experientes a
resolver/arquivar registros).
"""
from django.template.loader import render_to_string
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError

from apps.common.pagination import PaginacaoCompulsoria
from apps.common.pdf import caminho_logo, render_pdf
from apps.common.permissions import IsAdminOrDiretorOrProfessor
from apps.common.views import EscopoEscolaMixin
from apps.relatorios.exportacao import (
    FORMATOS_PLANILHA,
    exportar_planilha,
    resolver_formato,
    resposta_download,
)
from apps.relatorios.services import (
    LIMITE_PDF_OCORRENCIAS,
    agrupar_ocorrencias_por_aluno,
    contar_ocorrencias_por_status,
    linhas_ocorrencias,
)

from .filters import OcorrenciaFilter
from .models import Ocorrencia
from .serializers import OcorrenciaSerializer
from .services import notificar_responsavel_ocorrencia

# Alias module-level: o render mora em `apps/common/pdf.py`, mas o nome
# fica aqui porque os testes dão `mock.patch` em
# `apps.ocorrencias.views._render_pdf`.
_render_pdf = render_pdf

FORMATOS_EXPORT = ("pdf", *FORMATOS_PLANILHA)


class OcorrenciaViewSet(EscopoEscolaMixin, viewsets.ModelViewSet):
    """CRUD de ocorrências.

    Leitura e escrita liberadas para admin/diretor/professor. Queryset
    escopado pela escola do usuário autenticado via `EscopoEscolaMixin`.
    Filtros declarativos por status, turma, aluno e professor; busca livre
    em `descricao`.

    Ao criar uma ocorrência, notifica o responsável do aluno por email
    (em background e protegido — falha de email não impede o registro nem
    pendura a resposta HTTP).
    """

    queryset = (
        Ocorrencia.objects.select_related("turma", "aluno", "professor", "escola")
        .order_by("-data_ocorrencia", "-criado_em")
    )
    serializer_class = OcorrenciaSerializer
    permission_classes = [IsAdminOrDiretorOrProfessor]
    # Listagem volumosa (cresce sem teto em escola operando ano a ano):
    # pagina por default, dashboard/boletim pedem `?page_size=all`.
    pagination_class = PaginacaoCompulsoria
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_class = OcorrenciaFilter
    search_fields = ["descricao"]

    def perform_create(self, serializer) -> None:
        ocorrencia = serializer.save()
        # Notificação por email — não levanta exceção (ver service).
        notificar_responsavel_ocorrencia(ocorrencia)

    @action(detail=False, methods=["get"])
    def exportar(self, request):
        """`GET /ocorrencias/exportar/?formato=pdf|csv|xlsx`.

        Exporta o MESMO recorte da listagem: a action reaproveita
        `get_queryset` (escopo de escola) e `filter_queryset`
        (`OcorrenciaFilter` + busca em `descricao`), então status, turma,
        aluno, professor e período valem aqui exatamente como na tela.
        Reimplementar os filtros seria a maneira mais fácil de o arquivo
        divergir do que a pessoa estava vendo.

        Sem paginação de propósito — exportar a primeira página não é
        exportar o relatório.
        """
        formato = resolver_formato(
            request, FORMATOS_EXPORT, default="pdf"
        )
        ocorrencias = list(
            self.filter_queryset(self.get_queryset()).select_related(
                "professor__usuario"
            )
        )

        stem = "ocorrencias"
        if formato in FORMATOS_PLANILHA:
            headers, linhas = linhas_ocorrencias(ocorrencias)
            return exportar_planilha(
                headers, linhas, formato=formato, stem=stem
            )

        if len(ocorrencias) > LIMITE_PDF_OCORRENCIAS:
            raise ValidationError(
                {
                    "detail": (
                        f"O recorte tem {len(ocorrencias)} ocorrências e o "
                        f"PDF comporta {LIMITE_PDF_OCORRENCIAS}. Estreite o "
                        "filtro (turma, período ou status) ou baixe em "
                        "CSV/XLSX, que não têm esse limite."
                    )
                }
            )

        escola_nome = ""
        if ocorrencias:
            escola_nome = ocorrencias[0].escola.nome
        else:
            escola_usuario = getattr(request.user, "escola", None)
            escola_nome = escola_usuario.nome if escola_usuario else ""

        contexto = {
            "grupos": agrupar_ocorrencias_por_aluno(ocorrencias),
            "contagem": contar_ocorrencias_por_status(ocorrencias),
            "total": len(ocorrencias),
            "escola_nome": escola_nome,
            "recorte": self._descrever_recorte(request, ocorrencias),
            "gerado_em": timezone.localtime(),
            "logo_path": caminho_logo(),
        }
        html_str = render_to_string(
            "relatorio_ocorrencias_pdf.html", contexto
        )
        return resposta_download(
            _render_pdf(html_str),
            content_type="application/pdf",
            nome_arquivo=f"{stem}.pdf",
        )

    def _descrever_recorte(self, request, ocorrencias) -> str:
        """Rótulo legível dos filtros, pro cabeçalho do PDF.

        Sem isto, duas folhas impressas do mesmo mês com status
        diferentes ficariam indistinguíveis em cima da mesa.

        O nome da turma sai das ocorrências encontradas, não do
        `?turma=` recebido: um id de outra escola devolve recorte vazio
        (o queryset é escopado), mas resolver o nome pelo parâmetro
        imprimiria no cabeçalho a turma de quem não é da casa.
        """
        partes = []
        inicio = request.query_params.get("data_inicio")
        fim = request.query_params.get("data_fim")
        if inicio and fim:
            partes.append(f"{_br(inicio)} a {_br(fim)}")
        elif inicio:
            partes.append(f"a partir de {_br(inicio)}")
        elif fim:
            partes.append(f"até {_br(fim)}")

        status_filtro = request.query_params.get("status")
        if status_filtro:
            rotulos = dict(Ocorrencia.Status.choices)
            partes.append(rotulos.get(status_filtro, status_filtro))

        if request.query_params.get("turma"):
            nomes = {ocorrencia.turma.nome for ocorrencia in ocorrencias}
            if len(nomes) == 1:
                partes.append(f"turma {nomes.pop()}")

        busca = request.query_params.get("search")
        if busca:
            partes.append(f'busca "{busca}"')

        return " · ".join(partes) if partes else "Todas as ocorrências"


def _br(iso: str) -> str:
    """`2026-03-01` → `01/03/2026`. Entrada inválida volta como veio."""
    partes = iso.split("-")
    if len(partes) != 3:
        return iso
    ano, mes, dia = partes
    return f"{dia}/{mes}/{ano}"
