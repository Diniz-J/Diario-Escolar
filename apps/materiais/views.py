"""Views da app materiais — mural publicado pelo professor (lado do staff).

Mesmo padrão do diário de aula (`apps/aulas/views.py`):

- Direção (admin/diretor/secretaria/coordenador) vê e edita o mural da
  escola inteira, e pode publicar escolhendo o professor.
- Professor/inspetor vê e edita só os próprios materiais; publicar em nome
  de outro dá 403.

A leitura pelo responsável fica no portal (`apps/portal/leituras.py`).
"""
from django.core.exceptions import ObjectDoesNotExist
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets
from rest_framework.exceptions import PermissionDenied

from apps.common.permissions import (
    PERFIS_PRIVILEGIADOS,
    IsAdminOrDiretorOrProfessor,
    eh_admin_global,
)
from apps.common.views import EscopoEscolaMixin, ReadWritePermissionMixin

from .models import Material
from .serializers import MaterialSerializer


def _eh_direcao(user) -> bool:
    return eh_admin_global(user) or getattr(user, "perfil", None) in PERFIS_PRIVILEGIADOS


def _professor_do_usuario(user):
    try:
        return user.professor
    except (AttributeError, ObjectDoesNotExist):
        return None


class MaterialViewSet(EscopoEscolaMixin, ReadWritePermissionMixin, viewsets.ModelViewSet):
    """CRUD do mural. `DELETE` desativa (soft delete) — some do portal."""

    READ_PERMISSION = IsAdminOrDiretorOrProfessor
    WRITE_PERMISSION = IsAdminOrDiretorOrProfessor

    queryset = Material.objects.select_related(
        "turma", "disciplina", "professor__usuario", "escola"
    ).order_by("-publicado_em")
    serializer_class = MaterialSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["turma", "disciplina", "professor", "ativo"]

    def get_queryset(self):
        """Direção vê a escola toda; professor/inspetor só os próprios."""
        qs = super().get_queryset()
        user = self.request.user
        if _eh_direcao(user):
            return qs
        professor = _professor_do_usuario(user)
        if professor is None:
            return qs.none()
        return qs.filter(professor_id=professor.id)

    def _barrar_outro_professor(self, serializer) -> None:
        """Professor só publica (ou move o material) pra si mesmo.

        Bloqueia em vez de sobrescrever: a validação de lecionamento já
        rodou pro `professor` do payload, e trocar depois desalinharia.
        """
        user = self.request.user
        if _eh_direcao(user):
            return
        professor = serializer.validated_data.get("professor")
        if professor is None:
            return  # PATCH sem professor: o queryset já garante que é dele.
        if professor != _professor_do_usuario(user):
            raise PermissionDenied("Você só pode publicar material em seu próprio nome.")

    def perform_create(self, serializer) -> None:
        self._barrar_outro_professor(serializer)
        serializer.save()

    def perform_update(self, serializer) -> None:
        self._barrar_outro_professor(serializer)
        serializer.save()

    def perform_destroy(self, instance) -> None:
        instance.ativo = False
        instance.save(update_fields=["ativo", "atualizado_em"])
