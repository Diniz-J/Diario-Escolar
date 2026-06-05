"""Views da app avaliacao."""
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets

from apps.common.permissions import (
    IsAdminOrDiretor,
    IsAdminOrDiretorOrProfessorOrInspetor,
)
from apps.common.views import EscopoEscolaMixin, ReadWritePermissionMixin

from .models import PeriodoAvaliativo
from .serializers import PeriodoAvaliativoSerializer


class _PeriodoAvaliativoReadWriteMixin(ReadWritePermissionMixin):
    """Leitura ampla (qualquer perfil que opera o sistema vê os períodos
    pra contextualizar avaliações/boletim). Escrita restrita a quem
    configura escola: admin/diretor/secretaria (`IsAdminOrDiretor`)."""

    READ_PERMISSION = IsAdminOrDiretorOrProfessorOrInspetor
    WRITE_PERMISSION = IsAdminOrDiretor


class PeriodoAvaliativoViewSet(
    EscopoEscolaMixin,
    _PeriodoAvaliativoReadWriteMixin,
    viewsets.ModelViewSet,
):
    """CRUD dos períodos avaliativos da escola.

    Escopo: queryset filtrado pela escola do JWT (admin global vê tudo).
    Soft delete via `ativo=False` no DELETE — preserva histórico de
    avaliações apontando pro período.
    """

    queryset = PeriodoAvaliativo.objects.select_related("escola").order_by(
        "-ano_letivo", "ordem"
    )
    serializer_class = PeriodoAvaliativoSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["ano_letivo", "ativo"]

    def perform_destroy(self, instance: PeriodoAvaliativo) -> None:
        """Soft delete: marca `ativo=False`. Mantém o registro no banco
        pra preservar histórico de avaliações futuras que apontem pra ele."""
        instance.ativo = False
        instance.save(update_fields=["ativo", "atualizado_em"])
