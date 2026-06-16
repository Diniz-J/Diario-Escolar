"""Views da app aulas — diário de classe do professor + visto da direção.

Padrão de permissão:
- Leitura/escrita: admin/diretor/secretaria/professor/inspetor.
- Conferência (`conferir`): só admin/diretor/secretaria.

Escopo de visibilidade:
- Direção (admin/diretor/secretaria) vê os registros de toda a escola.
- Professor/inspetor vê e edita apenas os próprios registros.

A transição pra `conferido` é exclusiva da action `conferir` — o serializer
recusa `status=conferido`, então não há como o professor se autoconferir.
"""
from datetime import date

from django.core.exceptions import ObjectDoesNotExist
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from apps.common.permissions import (
    IsAdminOrDiretor,
    IsAdminOrDiretorOrProfessor,
)
from apps.common.views import EscopoEscolaMixin, ReadWritePermissionMixin
from apps.escola.models import Turma

from .filters import RegistroAulaFilter
from .models import RegistroAula
from .serializers import RegistroAulaSerializer
from .services import projetar_agenda

# Perfis que enxergam o diário da escola inteira (não só o próprio).
_PERFIS_DIRECAO = frozenset({"diretor", "secretaria"})


def _eh_direcao(user) -> bool:
    """True para admin/superuser e perfis de direção (diretor/secretaria)."""
    if getattr(user, "is_superuser", False):
        return True
    perfil = getattr(user, "perfil", None)
    return perfil == "admin" or perfil in _PERFIS_DIRECAO


def _professor_do_usuario(user):
    """Retorna o `Professor` vinculado ao usuário, ou None se não houver."""
    try:
        return user.professor
    except (AttributeError, ObjectDoesNotExist):
        return None


class _AulaReadWriteMixin(ReadWritePermissionMixin):
    """Leitura e escrita liberadas pra direção + professor/inspetor."""

    READ_PERMISSION = IsAdminOrDiretorOrProfessor
    WRITE_PERMISSION = IsAdminOrDiretorOrProfessor


class RegistroAulaViewSet(
    EscopoEscolaMixin, _AulaReadWriteMixin, viewsets.ModelViewSet
):
    """CRUD do diário de aula + conferência da direção + agenda projetada."""

    queryset = (
        RegistroAula.objects.select_related(
            "turma",
            "disciplina",
            "professor",
            "professor__usuario",
            "conferido_por",
            "escola",
        ).order_by("-data")
    )
    serializer_class = RegistroAulaSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_class = RegistroAulaFilter

    def get_queryset(self):
        """Direção vê toda a escola; professor/inspetor só os próprios."""
        qs = super().get_queryset()
        user = self.request.user
        if not user.is_authenticated:
            return qs.none()
        if _eh_direcao(user):
            return qs
        professor = _professor_do_usuario(user)
        if professor is None:
            return qs.none()
        return qs.filter(professor_id=professor.id)

    def get_permissions(self):
        if self.action == "conferir":
            return [IsAdminOrDiretor()]
        return super().get_permissions()

    def perform_create(self, serializer) -> None:
        """Professor só cria registro pra si mesmo; direção pode escolher.

        Bloqueia (em vez de sobrescrever) quando o docente tenta lançar em
        nome de outro: a validação de lecionamento já rodou pro `professor`
        do payload, então sobrescrever desalinharia a invariante.
        """
        user = self.request.user
        if not _eh_direcao(user):
            proprio = _professor_do_usuario(user)
            if proprio is None or serializer.validated_data.get("professor") != proprio:
                raise PermissionDenied(
                    "Você só pode lançar aulas em seu próprio nome."
                )
        serializer.save()

    @action(detail=True, methods=["post"])
    def conferir(self, request, pk=None):
        """Direção dá o visto: `lancado` → `conferido` (grava quem/quando)."""
        registro = self.get_object()
        if registro.status != RegistroAula.Status.LANCADO:
            return Response(
                {
                    "detail": "Só é possível conferir uma aula com status "
                    "'lançado'."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        registro.status = RegistroAula.Status.CONFERIDO
        registro.conferido_por = request.user
        registro.conferido_em = timezone.now()
        registro.save(
            update_fields=[
                "status",
                "conferido_por",
                "conferido_em",
                "atualizado_em",
            ]
        )
        return Response(self.get_serializer(registro).data)

    @action(detail=False, methods=["get"])
    def agenda(self, request):
        """Projeta os slots de aula de um lecionamento num mês.

        Query params: `turma`, `disciplina`, `mes` (YYYY-MM) obrigatórios;
        `professor` opcional (default: o professor logado).
        """
        turma_id = request.query_params.get("turma")
        disciplina_id = request.query_params.get("disciplina")
        mes_param = request.query_params.get("mes")
        professor_param = request.query_params.get("professor")

        if not (turma_id and disciplina_id and mes_param):
            return Response(
                {
                    "detail": "Parâmetros obrigatórios: turma, disciplina, "
                    "mes (YYYY-MM)."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            ano_str, mes_str = mes_param.split("-")
            ano, mes = int(ano_str), int(mes_str)
            date(ano, mes, 1)
        except (ValueError, TypeError):
            return Response(
                {"detail": "mes inválido — use o formato YYYY-MM."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if professor_param:
            professor_id = professor_param
        else:
            professor = _professor_do_usuario(request.user)
            if professor is None:
                return Response(
                    {"detail": "Informe o parâmetro professor."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            professor_id = professor.id

        turma = Turma.objects.filter(id=turma_id).first()
        if turma is None:
            return Response(
                {"detail": "Turma não encontrada."},
                status=status.HTTP_404_NOT_FOUND,
            )
        # Guard de escopo: não-direção só projeta agenda da própria escola.
        if not _eh_direcao(request.user) and turma.escola_id != getattr(
            request.user, "escola_id", None
        ):
            return Response(
                {"detail": "Turma fora do seu escopo."},
                status=status.HTTP_404_NOT_FOUND,
            )

        slots = projetar_agenda(
            escola_id=turma.escola_id,
            professor_id=professor_id,
            turma_id=turma_id,
            disciplina_id=disciplina_id,
            ano=ano,
            mes=mes,
        )
        return Response(slots)
