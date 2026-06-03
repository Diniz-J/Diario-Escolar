"""Views da app planos_ensino — CRUD do plano anual.

Leitura: admin/diretor/professor/inspetor (inspetor acompanha).
Escrita: admin/diretor/professor (professores preenchem seu plano).
"""
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, viewsets

from apps.common.import_export_views import ImportExportViewSetMixin
from apps.common.permissions import (
    IsAdminOrDiretorOrProfessor,
    IsAdminOrDiretorOrProfessorOrInspetor,
)
from apps.common.views import EscopoEscolaMixin, ReadWritePermissionMixin

from .models import PlanoEnsino
from .resources import PlanoEnsinoResource
from .serializers import PlanoEnsinoSerializer


class _PlanoEnsinoReadWriteMixin(ReadWritePermissionMixin):
    READ_PERMISSION = IsAdminOrDiretorOrProfessorOrInspetor
    WRITE_PERMISSION = IsAdminOrDiretorOrProfessor


class PlanoEnsinoViewSet(
    ImportExportViewSetMixin,
    EscopoEscolaMixin,
    _PlanoEnsinoReadWriteMixin,
    viewsets.ModelViewSet,
):
    queryset = (
        PlanoEnsino.objects.select_related(
            "turma", "disciplina", "professor", "escola"
        )
        .order_by("-ano_letivo", "turma__nome", "disciplina__nome")
    )
    serializer_class = PlanoEnsinoSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ["turma", "disciplina", "professor", "ano_letivo", "ativo"]
    # Pesquisa nos campos mais consultados; conteúdo programático pode
    # ser longo mas costuma ser onde se busca por palavra-chave.
    search_fields = ["ementa", "conteudo_programatico", "habilidades_bncc"]
    import_export_resource = PlanoEnsinoResource
    import_export_nome_arquivo = "planos_ensino"
