"""Filtros declarativos da app ocorrencias.

Substitui o `filterset_fields` simples por um `FilterSet` explícito para
suportar range de datas (`data_inicio` / `data_fim`) sobre o campo
`data_ocorrencia`, mantendo os filtros exatos por status/turma/aluno/professor.
"""
import django_filters

from .models import Ocorrencia


class OcorrenciaFilter(django_filters.FilterSet):
    # Range de período: ambos opcionais e inclusivos.
    # `?data_inicio=2026-05-01&data_fim=2026-05-31` → ocorrências do mês.
    data_inicio = django_filters.DateFilter(
        field_name="data_ocorrencia", lookup_expr="gte"
    )
    data_fim = django_filters.DateFilter(
        field_name="data_ocorrencia", lookup_expr="lte"
    )

    class Meta:
        model = Ocorrencia
        fields = ["status", "turma", "aluno", "professor"]
