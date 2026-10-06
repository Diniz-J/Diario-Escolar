"""Leituras do portal do responsável (fatia 4 do `PORTAL.md`).

Regra única de autorização (seção 4.2): **tudo parte dos vínculos do
responsável autenticado**. Id de aluno que chega na URL é palpite — se não
for filho dele, 404, nunca 403 (403 confirmaria que o aluno existe).

Separado de `views.py` (login, senha, convite) pra a camada de leitura não
se misturar com a de autenticação.
"""
from django.db.models import QuerySet
from django.shortcuts import get_object_or_404
from rest_framework import generics
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.avaliacao.models import PeriodoAvaliativo
from apps.boletins.services import montar_boletim
from apps.common.pagination import PaginacaoCompulsoria
from apps.comunicados.models import Comunicado, ComunicadoDestinatario
from apps.escola.models import Aluno
from apps.materiais.models import Material
from apps.ocorrencias.models import Ocorrencia

from .authentication import IsResponsavel, PortalJWTAuthentication
from .serializers import (
    ComunicadoPortalSerializer,
    FilhoSerializer,
    MaterialPortalSerializer,
    OcorrenciaPortalSerializer,
    PeriodoSerializer,
)


def filhos_do(responsavel) -> QuerySet:
    """Alunos vinculados ao responsável — a raiz de toda leitura do portal.

    Inclui aluno inativo de propósito: o vínculo sobrevive ao soft delete e
    o responsável segue vendo o histórico (`PORTAL.md`, seção 2).

    O filtro por escola é redundante com o `ResponsavelAluno.clean()` e
    fica de propósito: o `clean()` não roda em `objects.create()`, shell nem
    código futuro que crie vínculo pelo ORM. Um vínculo cruzado nascido por
    aí abriria os dados de um aluno de outra escola em toda leitura, já que
    todas partem daqui.
    """
    return Aluno.objects.filter(
        vinculos_responsavel__responsavel=responsavel,
        escola_id=responsavel.escola_id,
    ).select_related("turma", "escola")


def filho_ou_404(request, pk) -> Aluno:
    return get_object_or_404(filhos_do(request.user), pk=pk)


def comunicados_do(responsavel) -> QuerySet:
    """Comunicados enviados que alcançaram algum filho do responsável.

    Parte do log de entrega (`ComunicadoDestinatario`), não da turma atual
    do filho: o log guarda quem foi endereçado no momento do disparo. Filho
    que trocou de turma não herda os avisos antigos da turma nova nem perde
    os da antiga; filho desativado para de receber aviso novo e mantém os
    antigos; aluno sem email também tem linha, então o pai vê no portal o
    aviso que não chegou por email.

    Só `enviado`: rascunho é texto em revisão; `enviando` e `falhou` não
    são o registro final. O filtro por escola é redundante (o vínculo já
    garante) e fica como rede de segurança contra vazamento entre escolas.
    """
    return (
        Comunicado.objects.filter(
            status=Comunicado.Status.ENVIADO,
            escola_id=responsavel.escola_id,
            destinatarios__aluno__vinculos_responsavel__responsavel=responsavel,
        )
        .distinct()
        .order_by("-enviado_em", "-pk")
    )


def alunos_por_comunicado(responsavel, comunicado_ids) -> dict[int, list[dict]]:
    """Filhos do responsável alcançados por cada comunicado — uma query só."""
    linhas = (
        ComunicadoDestinatario.objects.filter(
            comunicado_id__in=comunicado_ids,
            aluno__vinculos_responsavel__responsavel=responsavel,
        )
        .order_by("aluno__nome_completo")
        .values("comunicado_id", "aluno_id", "aluno__nome_completo")
    )
    resultado: dict[int, list[dict]] = {}
    for linha in linhas:
        resultado.setdefault(linha["comunicado_id"], []).append(
            {"id": linha["aluno_id"], "nome_completo": linha["aluno__nome_completo"]}
        )
    return resultado


class _PortalMixin:
    authentication_classes = [PortalJWTAuthentication]
    permission_classes = [IsResponsavel]


class FilhosView(_PortalMixin, generics.ListAPIView):
    """`GET /portal/alunos/` — os filhos vinculados."""

    serializer_class = FilhoSerializer
    pagination_class = None

    def get_queryset(self):
        return filhos_do(self.request.user).order_by("nome_completo")


class FilhoDetalheView(_PortalMixin, generics.RetrieveAPIView):
    """`GET /portal/alunos/<id>/`."""

    serializer_class = FilhoSerializer

    def get_object(self):
        return filho_ou_404(self.request, self.kwargs["pk"])


class BoletimFilhoView(_PortalMixin, APIView):
    """`GET /portal/alunos/<id>/boletim/?periodo=<id>` — sem período, anual.

    O período tem que ser da escola do filho. O helper do staff
    (`resolver_janela_por_periodo`) busca por id sem escopo, então aqui a
    busca é própria: período de outra escola dá 404 em vez de vazar nome e
    datas.
    """

    def get(self, request, pk):
        aluno = filho_ou_404(request, pk)
        periodo = None
        periodo_id = request.query_params.get("periodo")
        if periodo_id:
            periodo = get_object_or_404(
                PeriodoAvaliativo,
                pk=periodo_id if periodo_id.isdigit() else None,
                escola_id=aluno.escola_id,
            )
        return Response(
            montar_boletim(
                aluno,
                periodo.data_inicio if periodo else None,
                periodo.data_fim if periodo else None,
                periodo=periodo,
            )
        )


class OcorrenciasFilhoView(_PortalMixin, generics.ListAPIView):
    """`GET /portal/alunos/<id>/ocorrencias/` — paginado, mais recente primeiro."""

    serializer_class = OcorrenciaPortalSerializer
    pagination_class = PaginacaoCompulsoria

    def get_queryset(self):
        aluno = filho_ou_404(self.request, self.kwargs["pk"])
        return (
            Ocorrencia.objects.filter(aluno=aluno)
            .select_related("professor__usuario")
            .order_by("-data_ocorrencia", "-criado_em")
        )


class MateriaisFilhoView(_PortalMixin, generics.ListAPIView):
    """`GET /portal/alunos/<id>/materiais/` — mural da turma atual do filho.

    Só da turma do filho (`PORTAL.md`, fatia 5) e só materiais ativos.

    Filho desativado recebe lista vazia, divergindo do resto do portal de
    propósito: boletim, ocorrências e comunicados são histórico *dele* e
    continuam visíveis; o mural é conteúdo corrente da turma, e o aluno
    transferido seguiria vendo o que a turma que ele deixou recebe depois.
    """

    serializer_class = MaterialPortalSerializer
    pagination_class = PaginacaoCompulsoria

    def get_queryset(self):
        aluno = filho_ou_404(self.request, self.kwargs["pk"])
        if not aluno.ativo:
            return Material.objects.none()
        return (
            Material.objects.filter(
                turma_id=aluno.turma_id, escola_id=aluno.escola_id, ativo=True
            )
            .select_related("disciplina", "professor__usuario")
            .order_by("-publicado_em", "-pk")
        )


class PeriodosView(_PortalMixin, generics.ListAPIView):
    """`GET /portal/periodos/` — períodos da escola, pro seletor do boletim."""

    serializer_class = PeriodoSerializer
    pagination_class = None

    def get_queryset(self):
        return PeriodoAvaliativo.objects.filter(
            escola_id=self.request.user.escola_id, ativo=True
        ).order_by("ano_letivo", "ordem")


class ComunicadosView(_PortalMixin, APIView):
    """`GET /portal/comunicados/` — paginado, mais recente primeiro."""

    def get(self, request):
        paginador = PaginacaoCompulsoria()
        qs = comunicados_do(request.user)
        pagina = paginador.paginate_queryset(qs, request, view=self)
        itens = list(qs) if pagina is None else pagina
        contexto = {
            "alunos_por_comunicado": alunos_por_comunicado(
                request.user, [c.pk for c in itens]
            )
        }
        dados = ComunicadoPortalSerializer(itens, many=True, context=contexto).data
        if pagina is None:
            return Response(dados)
        return paginador.get_paginated_response(dados)


class ComunicadoDetalheView(_PortalMixin, APIView):
    """`GET /portal/comunicados/<id>/` — 404 se não alcançou nenhum filho."""

    def get(self, request, pk):
        comunicado = get_object_or_404(comunicados_do(request.user), pk=pk)
        contexto = {
            "alunos_por_comunicado": alunos_por_comunicado(request.user, [comunicado.pk])
        }
        return Response(ComunicadoPortalSerializer(comunicado, context=contexto).data)
