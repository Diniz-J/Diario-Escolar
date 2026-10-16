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
`data_pagamento` da fatura são escritos pelo `services.py`, e
`id_externo`/`link_pagamento` pelo gateway (fatia 4). As views nunca
reescrevem esses campos — o registro e o estorno de pagamento delegam em
`registrar_pagamento`/`estornar_pagamento`, que reconciliam a fatura na
mesma transação. Ver `serializers.py` e `FINANCEIRO.md` §2.4.
"""
from django.core.exceptions import ValidationError as DjangoValidationError
from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, mixins, viewsets
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.pagination import PaginacaoCompulsoria, PaginacaoPadrao
from apps.common.permissions import IsAdminOrDiretor, eh_admin_global
from apps.common.views import EscopoEscolaMixin
from apps.escola.models import Aluno

from .filters import FaturaFilter, PagamentoFilter, PlanoCobrancaFilter
from .models import Fatura, FaturaItem, Pagamento, PlanoCobranca
from .serializers import (
    FaturaItemSerializer,
    FaturaSerializer,
    PagamentoCreateSerializer,
    PagamentoSerializer,
    PlanoCobrancaSerializer,
    erro_drf,
)
from .services import estornar_pagamento, ficha_financeira, registrar_pagamento


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


class PagamentoViewSet(
    EscopoEscolaMixin,
    mixins.CreateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.ReadOnlyModelViewSet,
):
    """Registro manual (secretaria recebeu), leitura e estorno.

    **Sem `update`**: corrigir valor ou data de um pagamento registrado
    deixaria a fatura reconciliada com um número que não existe mais. O
    caminho é estornar e registrar de novo, que passa pelos dois lados da
    conciliação.

    `POST` e `DELETE` delegam no `services.py` em vez de salvar pelo
    serializer: é lá que `valor_pago` e `status` da fatura são
    reescritos, na mesma transação (`FINANCEIRO.md` §2.4).
    """

    queryset = Pagamento.objects.select_related("fatura__aluno", "escola")
    permission_classes = [IsAdminOrDiretor]
    pagination_class = PaginacaoCompulsoria
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_class = PagamentoFilter
    search_fields = [
        "referencia_externa",
        "fatura__aluno__nome_completo",
        "fatura__aluno__matricula",
    ]

    def get_serializer_class(self):
        if self.action == "create":
            return PagamentoCreateSerializer
        return PagamentoSerializer

    def perform_create(self, serializer) -> None:
        """Entrega ao service e devolve o que ele criou.

        `serializer.instance` é setado à mão porque o service é que
        persiste — sem isso o DRF renderizaria a resposta a partir de um
        serializer sem instância.

        O service é idempotente por `referencia_externa`: reenviar a
        mesma referência devolve o pagamento que já existe, com 201 e o
        recurso existente, em vez de criar o segundo.
        """
        dados = serializer.validated_data
        try:
            serializer.instance = registrar_pagamento(
                fatura=dados["fatura"],
                valor=dados["valor"],
                data=dados["data"],
                metodo=dados["metodo"],
                referencia_externa=dados.get("referencia_externa", ""),
            )
        except DjangoValidationError as exc:
            # O service valida com `full_clean()` pra que as invariantes
            # valham também pro command e pro webhook. O DRF não traduz o
            # `ValidationError` do Django, então sem isto "fatura
            # cancelada não recebe pagamento" sairia como 500.
            raise erro_drf(exc) from exc

    def perform_destroy(self, instance) -> None:
        """`DELETE` é estorno: apaga o pagamento e reconcilia a fatura.

        É o que torna acionável a recusa de cancelar fatura com pagamento
        registrado — estorna aqui, cancela a fatura depois. O audit log
        guarda a linha apagada e quem apagou.
        """
        estornar_pagamento(instance)


class FichaFinanceiraAlunoView(APIView):
    """`GET /financeiro/alunos/<id>/` — situação financeira consolidada.

    Sem modelo próprio: agrega on-the-fly, como `boletins` e `relatorios`.
    Devolve os totais (em aberto, vencido, encargos de hoje, pago no ano)
    mais os três históricos — contratos, faturas e pagamentos — numa
    requisição só, porque a tela mostra tudo junto e quatro chamadas
    paralelas renderizariam a ficha em pedaços.

    Os totais são somados no `services.py`, sobre os métodos do modelo, e
    não em SQL: `saldo()` trava em zero no pagamento a mais, e uma soma
    reescrita em SQL faria o excesso de uma fatura abater a dívida de
    outra. Ver `ficha_financeira`.

    Escopo: aluno de outra escola responde **404**, não 403 — existência
    de aluno alheio não é informação que este endpoint deva confirmar.
    (`boletins` responde 403 no mesmo caso; a divergência é consciente, e
    o caminho aqui é o mesmo dos viewsets deste módulo, onde o escopo do
    queryset já produz 404.)
    """

    permission_classes = [IsAdminOrDiretor]

    def get(self, request, aluno_id: int):
        alunos = Aluno.objects.select_related("turma")
        if not eh_admin_global(request.user):
            # Sem escola no token, não há recorte possível: nega tudo.
            alunos = alunos.filter(
                escola_id=getattr(request.user, "escola_id", None) or 0
            )
        aluno = get_object_or_404(alunos, pk=aluno_id)

        ficha = ficha_financeira(aluno)
        contexto = {"request": request}
        totais = ficha.totais
        return Response(
            {
                "aluno": {
                    "id": aluno.id,
                    "nome_completo": aluno.nome_completo,
                    "matricula": aluno.matricula,
                    "turma": aluno.turma.nome,
                    "ativo": aluno.ativo,
                },
                # Strings, como todo dinheiro da API: o front formata, não
                # calcula.
                "totais": {
                    "em_aberto": str(totais.em_aberto),
                    "vencido": str(totais.vencido),
                    "encargos_hoje": str(totais.encargos_hoje),
                    "a_cobrar_hoje": str(totais.a_cobrar_hoje),
                    "pago_no_ano": str(totais.pago_no_ano),
                    "faturas_abertas": totais.faturas_abertas,
                },
                "planos": PlanoCobrancaSerializer(
                    ficha.planos, many=True, context=contexto
                ).data,
                "faturas": FaturaSerializer(
                    ficha.faturas, many=True, context=contexto
                ).data,
                "pagamentos": PagamentoSerializer(
                    ficha.pagamentos, many=True, context=contexto
                ).data,
            }
        )
