"""Filtros declarativos do financeiro.

`FilterSet` explícito em vez de `filterset_fields` porque as três
listagens são consultadas por período — "o que vence este mês", "o que
entrou em março", "as faturas do primeiro semestre" — e range de data
precisa de filtro declarado. Mesmo molde de `apps/ocorrencias/filters.py`.
"""
import django_filters
from django.db.models import Q

from .models import Fatura, Pagamento, PlanoCobranca


class PlanoCobrancaFilter(django_filters.FilterSet):
    # Contratos que cobrem uma data (ex.: quem tem plano valendo hoje).
    vigente_em = django_filters.DateFilter(
        method="filtrar_vigente_em",
        label="Vigente na data",
    )

    class Meta:
        model = PlanoCobranca
        fields = ["aluno", "ativo", "desconto_tipo"]

    def filtrar_vigente_em(self, queryset, name, value):
        """Vigência é intervalo fechado, com fim nulo valendo infinito."""
        return queryset.filter(vigencia_inicio__lte=value).filter(
            Q(vigencia_fim__isnull=True) | Q(vigencia_fim__gte=value)
        )


class FaturaFilter(django_filters.FilterSet):
    # Range de competência: `?competencia_de=2026-01-01&competencia_ate=2026-06-01`
    # pega o primeiro semestre. Ambos inclusivos.
    competencia_de = django_filters.DateFilter(
        field_name="competencia", lookup_expr="gte"
    )
    competencia_ate = django_filters.DateFilter(
        field_name="competencia", lookup_expr="lte"
    )
    # Range de vencimento: a pergunta da secretaria ("o que vence nesta
    # semana") é por vencimento, não por competência.
    vencimento_de = django_filters.DateFilter(
        field_name="vencimento", lookup_expr="gte"
    )
    vencimento_ate = django_filters.DateFilter(
        field_name="vencimento", lookup_expr="lte"
    )
    # Atalho pra turma: a fatura não tem o campo, mas a cobrança é
    # organizada por turma no dia a dia da escola.
    turma = django_filters.NumberFilter(field_name="aluno__turma")

    class Meta:
        model = Fatura
        fields = ["aluno", "plano", "status", "competencia"]


class PagamentoFilter(django_filters.FilterSet):
    data_de = django_filters.DateFilter(field_name="data", lookup_expr="gte")
    data_ate = django_filters.DateFilter(field_name="data", lookup_expr="lte")
    aluno = django_filters.NumberFilter(field_name="fatura__aluno")

    class Meta:
        model = Pagamento
        fields = ["fatura", "metodo"]
