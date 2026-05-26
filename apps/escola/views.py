"""Views da app escola — API REST com permissões granulares por ação.

Todos os ViewSets escopam o queryset à escola do `request.user` (via
`EscopoEscolaMixin` ou override manual em `EscolaViewSet`). Admin e superuser
bypassam o filtro.
"""
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, viewsets

from apps.common.permissions import IsAdmin, IsAdminOrDiretor
from apps.common.views import EscopoEscolaMixin, ReadWritePermissionMixin

from .models import Aluno, Disciplina, Escola, Lecionamento, Professor, Turma
from .serializers import (
    AlunoSerializer,
    DisciplinaSerializer,
    EscolaSerializer,
    LecionamentoSerializer,
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
    """CRUD de alunos. Suporta busca por nome/matrícula e filtro por turma.

    DELETE faz soft delete (marca `ativo=False`). Decisão consciente para
    preservar histórico de ocorrências e registros de presença vinculados
    ao aluno — alunos com dados históricos não podem ser apagados de fato
    pela FK PROTECT, e o registro escolar tem valor de auditoria.

    Frontend que quiser esconder inativos da listagem usa `?ativo=true`
    via DjangoFilterBackend (filterset_fields já inclui `ativo`).
    """

    queryset = Aluno.objects.select_related("turma", "escola").order_by("nome_completo")
    serializer_class = AlunoSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ["turma", "ativo"]
    search_fields = ["nome_completo", "matricula"]

    def perform_destroy(self, instance: Aluno) -> None:
        """Soft delete: só marca `ativo=False`, mantém a linha no banco."""
        instance.ativo = False
        instance.save(update_fields=["ativo", "atualizado_em"])


class ProfessorViewSet(EscopoEscolaMixin, ReadWritePermissionMixin, viewsets.ModelViewSet):
    """CRUD de professores. Busca pelo nome do usuário vinculado."""

    queryset = (
        Professor.objects.select_related("usuario", "escola")
        .order_by("usuario__first_name", "usuario__last_name")
    )
    serializer_class = ProfessorSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ["ativo"]
    search_fields = [
        "usuario__first_name",
        "usuario__last_name",
        "usuario__username",
    ]


class LecionamentoViewSet(EscopoEscolaMixin, ReadWritePermissionMixin, viewsets.ModelViewSet):
    """CRUD de lecionamentos (vínculo professor × turma × disciplina)."""

    queryset = (
        Lecionamento.objects.select_related(
            "professor__usuario", "turma", "disciplina", "escola"
        ).order_by("turma__ano_letivo", "turma__nome", "disciplina__nome")
    )
    serializer_class = LecionamentoSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["professor", "turma", "disciplina", "ativo"]
