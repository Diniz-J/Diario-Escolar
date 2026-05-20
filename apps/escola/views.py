"""Views da app escola — API REST com permissões granulares por ação.

Todos os ViewSets escopam o queryset à escola do `request.user` (via
`EscopoEscolaMixin` ou override manual em `EscolaViewSet`). Admin e superuser
bypassam o filtro.
"""
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, viewsets

from apps.common.permissions import IsAdmin, IsAdminOrDiretor
from apps.common.views import EscopoEscolaMixin, ReadWritePermissionMixin

from .models import Aluno, Disciplina, Escola, Professor, Turma
from .serializers import (
    AlunoSerializer,
    DisciplinaSerializer,
    EscolaSerializer,
    ProfessorSerializer,
    TurmaSerializer,
)


class EscolaViewSet(ReadWritePermissionMixin, viewsets.ModelViewSet):
    """CRUD de escolas. Apenas admins criam/editam/removem.

    Filtro de queryset é feito manualmente porque Escola é o tenant root —
    não tem FK `escola`, então não pode usar `EscopoEscolaMixin`.
    """

    queryset = Escola.objects.all().order_by("nome")
    serializer_class = EscolaSerializer
    READ_PERMISSION = IsAdminOrDiretor
    WRITE_PERMISSION = IsAdmin

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if not user.is_authenticated:
            return qs.none()
        if user.is_superuser or getattr(user, "perfil", None) == "admin":
            return qs
        if not getattr(user, "escola_id", None):
            return qs.none()
        return qs.filter(id=user.escola_id)


class TurmaViewSet(EscopoEscolaMixin, ReadWritePermissionMixin, viewsets.ModelViewSet):
    queryset = Turma.objects.select_related("escola").order_by("-ano_letivo", "nome")
    serializer_class = TurmaSerializer
    filter_backends = [DjangoFilterBackend]
    # `escola` removido: o queryset já é escopado por `EscopoEscolaMixin`.
    filterset_fields = ["ano_letivo", "turno", "ativa"]


class DisciplinaViewSet(EscopoEscolaMixin, ReadWritePermissionMixin, viewsets.ModelViewSet):
    queryset = Disciplina.objects.select_related("escola").order_by("nome")
    serializer_class = DisciplinaSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["ativa"]


class AlunoViewSet(EscopoEscolaMixin, ReadWritePermissionMixin, viewsets.ModelViewSet):
    """CRUD de alunos. Suporta busca por nome/matrícula e filtro por turma."""

    queryset = Aluno.objects.select_related("turma", "escola").order_by("nome_completo")
    serializer_class = AlunoSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ["turma", "ativo"]
    search_fields = ["nome_completo", "matricula"]


class ProfessorViewSet(EscopoEscolaMixin, ReadWritePermissionMixin, viewsets.ModelViewSet):
    """CRUD de professores. Busca pelo nome do usuário vinculado."""

    queryset = (
        Professor.objects.select_related("usuario", "escola")
        .prefetch_related("disciplinas")
        .order_by("usuario__first_name", "usuario__last_name")
    )
    serializer_class = ProfessorSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ["ativo", "disciplinas"]
    search_fields = [
        "usuario__first_name",
        "usuario__last_name",
        "usuario__username",
    ]
