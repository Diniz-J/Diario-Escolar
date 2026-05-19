"""Views da app presenca — CRUD de chamadas e itens individuais.

Padrão de permissão:
- Leitura (`list`, `retrieve`): admin/diretor/professor/inspetor.
- Escrita (`create`, `update`, `partial_update`, `destroy`): admin/diretor/professor.

Inspetor é incluído na leitura para que possa monitorar chamadas (ex.: cruzar
com ocorrências do dia) sem alterar os registros.

`RegistroPresencaViewSet.perform_create` gera automaticamente um `ItemPresenca`
com status=Presente para cada aluno ativo da turma, dentro de transação. Isso
materializa o caso de uso padrão: professor abre a chamada e só marca exceções.

`ItemPresencaViewSet` não expõe POST/DELETE — o ciclo de vida dos itens é
gerenciado pelo registro pai. Apenas GET e PATCH (mudar status/observação).
"""
from django.db import transaction
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import mixins, viewsets

from apps.common.permissions import (
    IsAdminOrDiretorOrProfessor,
    IsAdminOrDiretorOrProfessorOrInspetor,
)
from apps.common.views import EscopoEscolaMixin

from .models import ItemPresenca, RegistroPresenca
from .serializers import ItemPresencaSerializer, RegistroPresencaSerializer


class _PresencaPermissionMixin:
    """Leitura inclui inspetor; escrita só admin/diretor/professor."""

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [IsAdminOrDiretorOrProfessorOrInspetor()]
        return [IsAdminOrDiretorOrProfessor()]


class RegistroPresencaViewSet(
    EscopoEscolaMixin, _PresencaPermissionMixin, viewsets.ModelViewSet
):
    """CRUD de registros de presença. Cria itens automaticamente."""

    queryset = (
        RegistroPresenca.objects.select_related("turma", "professor", "escola")
        .order_by("-data")
    )
    serializer_class = RegistroPresencaSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["turma", "data", "professor"]

    def perform_create(self, serializer) -> None:
        """Cria o registro e popula `ItemPresenca` para cada aluno ativo.

        Tudo dentro de uma transação atômica: se a criação dos itens
        falhar, o próprio registro é revertido — evita ficar com registro
        sem itens em produção.

        Aluno inativo não recebe item: o padrão de diário escolar é que
        inativos saíram da turma e não devem aparecer na chamada. Se o
        aluno for reativado depois, novos registros já vão incluí-lo;
        registros antigos seguem sem ele (snapshot histórico).
        """
        with transaction.atomic():
            registro = serializer.save()
            alunos_ativos = registro.turma.alunos.filter(ativo=True)
            ItemPresenca.objects.bulk_create(
                [
                    ItemPresenca(
                        registro=registro,
                        aluno=aluno,
                        status=ItemPresenca.Status.PRESENTE,
                        escola=registro.escola,
                    )
                    for aluno in alunos_ativos
                ]
            )


class ItemPresencaViewSet(
    EscopoEscolaMixin,
    _PresencaPermissionMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    """Listagem e edição (PATCH/PUT) de itens individuais.

    Sem POST/DELETE de propósito: itens são criados pelo registro pai e
    removidos via cascade quando o registro é apagado.
    """

    queryset = (
        ItemPresenca.objects.select_related("registro", "aluno", "escola")
        .order_by("aluno__nome_completo")
    )
    serializer_class = ItemPresencaSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["registro", "aluno", "status"]
