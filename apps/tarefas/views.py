"""Views da app tarefas.

Mesmo padrão de `presenca`: ao criar uma `Tarefa`, o backend gera
automaticamente uma `EntregaTarefa(entregue=False)` para cada aluno
ativo da turma. `EntregaTarefaViewSet` não expõe POST/DELETE — o ciclo
de vida das entregas pertence à tarefa pai.

Permissões:
- Leitura: admin/diretor/professor/inspetor (inspetor monitora).
- Escrita: admin/diretor/professor.
"""
from django.db import transaction
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, mixins, viewsets

from apps.common.permissions import (
    IsAdminOrDiretorOrProfessor,
    IsAdminOrDiretorOrProfessorOrInspetor,
)
from apps.common.views import EscopoEscolaMixin, ReadWritePermissionMixin

from .models import EntregaTarefa, Tarefa
from .serializers import EntregaTarefaSerializer, TarefaSerializer


class _TarefasReadWriteMixin(ReadWritePermissionMixin):
    """Leitura inclui inspetor; escrita só admin/diretor/professor."""

    READ_PERMISSION = IsAdminOrDiretorOrProfessorOrInspetor
    WRITE_PERMISSION = IsAdminOrDiretorOrProfessor


class TarefaViewSet(
    EscopoEscolaMixin, _TarefasReadWriteMixin, viewsets.ModelViewSet
):
    """CRUD de tarefas. Cria entregas automaticamente para alunos ativos."""

    queryset = (
        Tarefa.objects.select_related(
            "turma", "disciplina", "professor", "escola"
        )
        .order_by("-data_lancamento", "-criado_em")
    )
    serializer_class = TarefaSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ["turma", "disciplina", "professor", "vale_nota"]
    search_fields = ["titulo", "descricao"]

    def perform_create(self, serializer) -> None:
        """Cria a tarefa e gera uma `EntregaTarefa` por aluno ativo.

        Tudo em transação atômica: falha na geração das entregas reverte
        a criação da tarefa. Aluno inativo não recebe entrega (snapshot
        histórico).
        """
        with transaction.atomic():
            tarefa = serializer.save()
            alunos_ativos = list(tarefa.turma.alunos.filter(ativo=True))
            for aluno in alunos_ativos:
                if aluno.turma_id != tarefa.turma_id:
                    raise ValueError(
                        f"Aluno {aluno.id} tem turma_id={aluno.turma_id} "
                        f"divergente de tarefa.turma_id={tarefa.turma_id}."
                    )
            EntregaTarefa.objects.bulk_create(
                [
                    EntregaTarefa(
                        tarefa=tarefa,
                        aluno=aluno,
                        escola=tarefa.escola,
                    )
                    for aluno in alunos_ativos
                ]
            )


class EntregaTarefaViewSet(
    EscopoEscolaMixin,
    _TarefasReadWriteMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    """Listagem e edição (PATCH/PUT) de entregas individuais.

    Sem POST/DELETE: entregas são criadas pela tarefa pai e removidas
    via cascade quando a tarefa é apagada.
    """

    queryset = (
        EntregaTarefa.objects.select_related("tarefa", "aluno", "escola")
        .order_by("aluno__nome_completo")
    )
    serializer_class = EntregaTarefaSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["tarefa", "aluno", "entregue"]
