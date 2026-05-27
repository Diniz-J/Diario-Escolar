"""Filtros declarativos da app presenca.

Suporta range de datas (`data_inicio` / `data_fim`) sobre o campo `data`
do registro de chamada, além dos filtros exatos por turma/professor.
"""
import django_filters

from .models import RegistroPresenca


class RegistroPresencaFilter(django_filters.FilterSet):
    data_inicio = django_filters.DateFilter(field_name="data", lookup_expr="gte")
    data_fim = django_filters.DateFilter(field_name="data", lookup_expr="lte")

    class Meta:
        model = RegistroPresenca
        fields = ["turma", "professor"]
