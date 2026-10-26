"""View da timeline do aluno.

Um endpoint de leitura, JSON só: `GET /timeline/aluno/<id>/`. Sem PDF
nem planilha — é tela de consulta, e o que a escola arquiva sai pelos
relatórios da app `relatorios`.
"""
from __future__ import annotations

from datetime import date

from django.shortcuts import get_object_or_404
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.permissions import IsAdminOrDiretorOrProfessorOrInspetor
from apps.escola.models import Aluno

from .services import montar_timeline


def _parse_date(valor: str | None, nome_param: str) -> date | None:
    """Converte `YYYY-MM-DD` em `date`. Vazio ou ausente → None."""
    if not valor:
        return None
    try:
        return date.fromisoformat(valor)
    except ValueError as exc:
        raise ValidationError(
            {nome_param: "Formato inválido. Use YYYY-MM-DD."}
        ) from exc


def _checar_acesso_aluno(request, aluno: Aluno) -> None:
    """Defesa de IDOR — não-admin só vê aluno da própria escola.

    Gêmeo do guard de `apps/boletins/views.py`, que é a outra view de
    leitura por aluno. São duas cópias de seis linhas; se aparecer uma
    terceira, o lugar dela é `apps/common` (foi o que aconteceu com
    `validate_escola_do_usuario` nos serializers).
    """
    user = request.user
    if user.is_superuser or getattr(user, "perfil", None) == "admin":
        return
    user_escola_id = getattr(user, "escola_id", None)
    if user_escola_id and aluno.escola_id != user_escola_id:
        raise PermissionDenied("Aluno fora da sua escola.")


class TimelineAlunoView(APIView):
    """`GET /timeline/aluno/<aluno_id>/`.

    Params: `data_inicio`/`data_fim` (opcionais, `YYYY-MM-DD`). Sem
    nenhum dos dois, devolve o histórico inteiro do aluno até o teto de
    `LIMITE_EVENTOS`.

    Leitura aberta a professor e inspetor, igual ao boletim: quem lança
    ocorrência e chamada precisa ver o que já foi lançado. O que é
    nível-direção (contato do responsável) não entra na timeline — ver
    `CAMPOS_CADASTRAIS` no serviço.
    """

    permission_classes = [
        IsAuthenticated,
        IsAdminOrDiretorOrProfessorOrInspetor,
    ]

    def get(self, request, aluno_id: int):
        aluno = get_object_or_404(
            Aluno.objects.select_related("turma", "escola"), pk=aluno_id
        )
        _checar_acesso_aluno(request, aluno)

        data_inicio = _parse_date(
            request.query_params.get("data_inicio"), "data_inicio"
        )
        data_fim = _parse_date(request.query_params.get("data_fim"), "data_fim")
        if data_inicio and data_fim and data_inicio > data_fim:
            # Intervalo invertido devolveria timeline vazia e válida, e a
            # tela diria "nenhum evento" pra um aluno cheio deles.
            raise ValidationError(
                {"data_fim": "A data final não pode ser anterior à inicial."}
            )

        return Response(montar_timeline(aluno, data_inicio, data_fim))
