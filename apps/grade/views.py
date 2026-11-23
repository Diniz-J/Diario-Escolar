"""Views da app grade — cadastro da grade horária (lado da direção).

Escrita é só direção (default do `ReadWritePermissionMixin`): montar a
grade é cadastro, como turma e disciplina. Leitura inclui professor e
inspetor porque a tela de chamada (fatia 4 do `PRESENCA.md`) lê a grade
pra pré-marcar os tempos do dia, e a agenda do diário (fatia 5) passa a
projetar a partir dela.

`DELETE` desativa em vez de apagar: o unique da grade é parcial
(`ativo=True`), então o slot desativado fica como histórico da grade
antiga sem impedir remontar o mesmo horário.
"""
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets
from rest_framework.exceptions import ValidationError

from apps.common.permissions import IsAdminOrDiretorOrProfessorOrInspetor
from apps.common.views import EscopoEscolaMixin, ReadWritePermissionMixin

from .models import AulaGrade, TempoAula
from .serializers import AulaGradeSerializer, TempoAulaSerializer


class _GradeReadWriteMixin(ReadWritePermissionMixin):
    """Leitura ampla (professor/inspetor consomem a grade); escrita direção."""

    READ_PERMISSION = IsAdminOrDiretorOrProfessorOrInspetor


class TempoAulaViewSet(
    EscopoEscolaMixin, _GradeReadWriteMixin, viewsets.ModelViewSet
):
    """CRUD do catálogo de horários da escola."""

    queryset = TempoAula.objects.select_related("escola").order_by(
        "turno", "ordem"
    )
    serializer_class = TempoAulaSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["turno", "ativo"]

    def get_queryset(self):
        # Soft delete: sem ?ativo=... explícito, lista só ativos pros seletores
        # não oferecerem tempos desativados.
        qs = super().get_queryset()
        if "ativo" not in self.request.query_params:
            qs = qs.filter(ativo=True)
        return qs

    def perform_destroy(self, instance) -> None:
        """Soft delete — bloqueia se houver slot ativo apontando pro tempo.

        O `on_delete=PROTECT` do FK só dispara em delete hard; aqui fazemos
        soft delete, então a checagem tem que ser explícita, senão a grade
        fica com slots ativos referenciando tempo desativado e a tela de
        chamada renderiza horário morto.
        """
        if instance.slots_grade.filter(ativo=True).exists():
            raise ValidationError(
                "Tempo em uso por slot(s) ativo(s) na grade; "
                "remova ou desative os slots antes."
            )
        instance.ativo = False
        instance.save(update_fields=["ativo", "atualizado_em"])


class AulaGradeViewSet(
    EscopoEscolaMixin, _GradeReadWriteMixin, viewsets.ModelViewSet
):
    """CRUD dos slots da grade (lecionamento × dia × tempo)."""

    queryset = AulaGrade.objects.select_related(
        "turma",
        "tempo",
        "escola",
        "lecionamento__disciplina",
        "lecionamento__professor__usuario",
    ).order_by("turma__nome", "dia_semana", "tempo__ordem")
    serializer_class = AulaGradeSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = [
        "turma",
        "dia_semana",
        "tempo",
        "lecionamento",
        "lecionamento__professor",
        "turma__ano_letivo",
        "ativo",
    ]

    def perform_destroy(self, instance) -> None:
        """Soft delete — ver docstring do módulo."""
        instance.ativo = False
        instance.save(update_fields=["ativo", "atualizado_em"])
