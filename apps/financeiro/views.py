"""Views do financeiro — CRUD escopado por escola.

**Permissão uniforme `IsAdminOrDiretor` em todas as ações**, leitura
inclusive. Pelos aliases do projeto isso cobre admin, diretor, secretaria
e coordenador; professor e inspetor levam 403 em tudo. Mensalidade,
bolsa e inadimplência não são assunto de quem dá aula — é o mesmo
raciocínio que já barra o professor no relatório cadastral de alunos
(aquela planilha traz nome e email de responsável).

A classe é declarada direto em `permission_classes`, sem o
`ReadWritePermissionMixin`: aqui leitura e escrita têm a mesma regra, e o
mixin só existe pra quando divergem. Como ele sobrescreve
`get_permissions`, tê-lo no caminho faria qualquer `permission_classes`
de `@action` futura ser ignorada em silêncio.

Escrita do que é dinheiro mora fora daqui: `status`/`valor_pago`/
`data_pagamento` da fatura são do `services.py` (fatia 3), `id_externo`/
`link_pagamento` são do gateway (fatia 4). Ver `serializers.py`.
"""
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, viewsets
from rest_framework.exceptions import ValidationError

from apps.common.pagination import PaginacaoCompulsoria, PaginacaoPadrao
from apps.common.permissions import IsAdminOrDiretor
from apps.common.views import EscopoEscolaMixin

from .filters import FaturaFilter, PagamentoFilter, PlanoCobrancaFilter
from .models import Fatura, FaturaItem, Pagamento, PlanoCobranca
from .serializers import (
    FaturaItemSerializer,
    FaturaSerializer,
    PagamentoSerializer,
    PlanoCobrancaSerializer,
)


class PlanoCobrancaViewSet(EscopoEscolaMixin, viewsets.ModelViewSet):
    """CRUD do contrato financeiro. `DELETE` desativa (soft delete).

    Soft delete porque o plano é a origem das faturas já emitidas: apagar
    a linha derrubaria o `PROTECT` da fatura, e desativar é o que a escola
    quer dizer quando encerra um contrato. Desativar também libera a
    vigência pra um plano novo do mesmo aluno.

    `PaginacaoPadrao` (opt-in) porque a lista é por aluno e curta — um
    contrato corrente mais os encerrados.
    """

    queryset = PlanoCobranca.objects.select_related("aluno", "escola")
    serializer_class = PlanoCobrancaSerializer
    permission_classes = [IsAdminOrDiretor]
    pagination_class = PaginacaoPadrao
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_class = PlanoCobrancaFilter
    search_fields = ["aluno__nome_completo", "aluno__matricula"]
    ordering = ["-vigencia_inicio"]

    def perform_destroy(self, instance) -> None:
        instance.ativo = False
        instance.save(update_fields=["ativo", "atualizado_em"])


class FaturaViewSet(EscopoEscolaMixin, viewsets.ModelViewSet):
    """CRUD do contas a receber. `DELETE` cancela a fatura.

    `select_related("plano")` não é otimização opcional: os campos
    derivados do serializer (`encargos`, `valor_atualizado`) leem os
    percentuais do plano, então sem isso a listagem faz uma query por
    linha.

    `PaginacaoCompulsoria` porque a listagem cresce sem teto — 300 alunos
    por 12 meses são 3.600 faturas por ano letivo. Quem precisa do
    recorte inteiro pede `?page_size=all`.
    """

    queryset = Fatura.objects.select_related("plano", "aluno", "escola")
    serializer_class = FaturaSerializer
    permission_classes = [IsAdminOrDiretor]
    pagination_class = PaginacaoCompulsoria
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_class = FaturaFilter
    search_fields = ["aluno__nome_completo", "aluno__matricula", "id_externo"]

    def perform_destroy(self, instance) -> None:
        """Cancela em vez de apagar — fatura é documento financeiro.

        Com pagamento registrado, recusa: a invariante do modelo não
        aceita fatura cancelada com dinheiro recebido, e o caminho certo
        é estornar o pagamento primeiro. Sem este guard, o `save()`
        gravaria um estado que o `full_clean()` recusaria — o banco
        aceitaria, e a fatura ficaria cancelada com valor pago.
        """
        if instance.status == Fatura.Status.CANCELADO:
            return
        if instance.valor_pago:
            raise ValidationError(
                {
                    "detail": (
                        "Esta fatura tem pagamento registrado e não pode ser "
                        "cancelada. Estorne o pagamento primeiro."
                    )
                }
            )
        instance.status = Fatura.Status.CANCELADO
        instance.save(update_fields=["status", "atualizado_em"])


class FaturaItemViewSet(EscopoEscolaMixin, viewsets.ModelViewSet):
    """CRUD do detalhamento da fatura.

    `DELETE` apaga de verdade, ao contrário do resto do módulo: a linha é
    detalhamento, não documento, e corrigir uma taxa lançada errado é
    operação legítima da secretaria. O audit log guarda o que foi apagado.
    """

    queryset = FaturaItem.objects.select_related("fatura__aluno", "escola")
    serializer_class = FaturaItemSerializer
    permission_classes = [IsAdminOrDiretor]
    pagination_class = PaginacaoPadrao
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["fatura"]


class PagamentoViewSet(EscopoEscolaMixin, viewsets.ReadOnlyModelViewSet):
    """Somente leitura nesta fatia.

    Registrar pagamento chega na fatia 3 junto de
    `services.registrar_pagamento()`, que atualiza `valor_pago` e
    `status` da fatura na mesma transação. Expor `POST` antes disso
    permitiria pagamento registrado com fatura intocada — o estado
    inconsistente que a decisão de não conciliar no `save()` existe pra
    evitar (`FINANCEIRO.md` §2.4).
    """

    queryset = Pagamento.objects.select_related("fatura__aluno", "escola")
    serializer_class = PagamentoSerializer
    permission_classes = [IsAdminOrDiretor]
    pagination_class = PaginacaoCompulsoria
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_class = PagamentoFilter
    search_fields = [
        "referencia_externa",
        "fatura__aluno__nome_completo",
        "fatura__aluno__matricula",
    ]
