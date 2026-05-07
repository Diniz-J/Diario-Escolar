"""Views da app escola — API REST com permissões granulares por ação."""
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, viewsets

from apps.common.permissions import (
    IsAdmin,
    IsAdminOrDiretor,
    IsAdminOrDiretorOrProfessor,
)

from .models import Aluno, Disciplina, Escola, Turma
from .serializers import (
    AlunoSerializer,
    DisciplinaSerializer,
    EscolaSerializer,
    TurmaSerializer,
)


class _BasePermissionMixin:
    """Padrão de permissões: leitura mais ampla que escrita.

    Subclasses definem `READ_PERMISSION` e `WRITE_PERMISSION`. As ações
    `list`/`retrieve` usam READ; o restante usa WRITE.
    """

    READ_PERMISSION = IsAdminOrDiretorOrProfessor
    WRITE_PERMISSION = IsAdminOrDiretor

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [self.READ_PERMISSION()]
        return [self.WRITE_PERMISSION()]


class EscolaViewSet(_BasePermissionMixin, viewsets.ModelViewSet):
    """CRUD de escolas. Apenas admins criam/editam/removem."""

    queryset = Escola.objects.all().order_by("nome")
    serializer_class = EscolaSerializer
    READ_PERMISSION = IsAdminOrDiretor
    WRITE_PERMISSION = IsAdmin


class TurmaViewSet(_BasePermissionMixin, viewsets.ModelViewSet):
    queryset = Turma.objects.select_related("escola").order_by("-ano_letivo", "nome")
    serializer_class = TurmaSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["escola", "ano_letivo", "turno", "ativa"]


class DisciplinaViewSet(_BasePermissionMixin, viewsets.ModelViewSet):
    queryset = Disciplina.objects.select_related("escola").order_by("nome")
    serializer_class = DisciplinaSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["escola", "ativa"]


class AlunoViewSet(_BasePermissionMixin, viewsets.ModelViewSet):
    """CRUD de alunos. Suporta busca por nome/matrícula e filtro por turma."""

    queryset = Aluno.objects.select_related("turma", "escola").order_by("nome_completo")
    serializer_class = AlunoSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ["turma", "escola", "ativo"]
    search_fields = ["nome_completo", "matricula"]
