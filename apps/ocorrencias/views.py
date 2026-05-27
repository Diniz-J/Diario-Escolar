"""Views da app ocorrencias — CRUD escopado por escola.

Diferente do padrão das outras apps, **professor também escreve** aqui:
ocorrências são registradas no dia a dia pelos professores, não apenas
por admin/diretor.

Decisão consciente: a permissão é uniforme em todas as ações (list,
retrieve, create, update, partial_update, destroy). Qualquer
admin/diretor/professor da mesma escola pode editar status de ocorrência
aberta por outro professor — o caso de uso é colega ajudando colega
(especialmente professores mais novos auxiliando os mais experientes a
resolver/arquivar registros).
"""
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, viewsets

from apps.common.permissions import IsAdminOrDiretorOrProfessor
from apps.common.views import EscopoEscolaMixin

from .filters import OcorrenciaFilter
from .models import Ocorrencia
from .serializers import OcorrenciaSerializer
from .services import notificar_responsavel_ocorrencia


class OcorrenciaViewSet(EscopoEscolaMixin, viewsets.ModelViewSet):
    """CRUD de ocorrências.

    Leitura e escrita liberadas para admin/diretor/professor. Queryset
    escopado pela escola do usuário autenticado via `EscopoEscolaMixin`.
    Filtros declarativos por status, turma, aluno e professor; busca livre
    em `descricao`.

    Ao criar uma ocorrência, notifica o responsável do aluno por email
    (em background e protegido — falha de email não impede o registro nem
    pendura a resposta HTTP).
    """

    queryset = (
        Ocorrencia.objects.select_related("turma", "aluno", "professor", "escola")
        .order_by("-data_ocorrencia", "-criado_em")
    )
    serializer_class = OcorrenciaSerializer
    permission_classes = [IsAdminOrDiretorOrProfessor]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_class = OcorrenciaFilter
    search_fields = ["descricao"]

    def perform_create(self, serializer) -> None:
        ocorrencia = serializer.save()
        # Notificação por email — não levanta exceção (ver service).
        notificar_responsavel_ocorrencia(ocorrencia)
