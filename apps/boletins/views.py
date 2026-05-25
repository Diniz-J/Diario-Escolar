"""Views da app boletins.

Endpoint único `GET /api/v1/boletins/aluno/{aluno_id}/` que agrega
frequência, notas por disciplina e ocorrências do aluno num único JSON.
Sem persistência: cada chamada recalcula.
"""
from datetime import date

from django.shortcuts import get_object_or_404
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.permissions import IsAdminOrDiretorOrProfessorOrInspetor
from apps.escola.models import Aluno

from .services import montar_boletim


def _parse_date(valor: str | None, nome_param: str) -> date | None:
    """Converte `YYYY-MM-DD` em `date`. Vazio ou None → None.

    Lança `ValidationError` (DRF) pra entrada malformada.
    """
    if not valor:
        return None
    try:
        return date.fromisoformat(valor)
    except ValueError as exc:
        raise ValidationError(
            {nome_param: "Formato inválido. Use YYYY-MM-DD."}
        ) from exc


class BoletimAlunoView(APIView):
    """Devolve o boletim agregado de um aluno específico.

    Filtros opcionais via query string:
    - `?data_inicio=YYYY-MM-DD`
    - `?data_fim=YYYY-MM-DD`
    """

    permission_classes = [
        IsAuthenticated,
        IsAdminOrDiretorOrProfessorOrInspetor,
    ]

    def get(self, request, aluno_id: int):
        aluno = get_object_or_404(
            Aluno.objects.select_related("turma"),
            pk=aluno_id,
        )

        # Reaproveita a defesa do EscopoEscolaMixin manualmente: usuário
        # não-admin só vê aluno da própria escola.
        user = request.user
        if not (
            user.is_superuser
            or getattr(user, "perfil", None) == "admin"
        ):
            user_escola_id = getattr(user, "escola_id", None)
            if user_escola_id and aluno.escola_id != user_escola_id:
                raise PermissionDenied(
                    "Aluno fora da sua escola."
                )

        data_inicio = _parse_date(
            request.query_params.get("data_inicio"), "data_inicio"
        )
        data_fim = _parse_date(
            request.query_params.get("data_fim"), "data_fim"
        )

        return Response(montar_boletim(aluno, data_inicio, data_fim))
