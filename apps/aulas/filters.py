"""Filtros declarativos da app aulas.

Suporta range de datas (`data_inicio` / `data_fim`) sobre o campo `data`
do registro, além dos filtros exatos por turma/disciplina/professor/status —
usados na ficha do professor (lista cronológica) e na exportação por recorte.
"""
import django_filters

from .models import RegistroAula


class RegistroAulaFilter(django_filters.FilterSet):
    data_inicio = django_filters.DateFilter(field_name="data", lookup_expr="gte")
    data_fim = django_filters.DateFilter(field_name="data", lookup_expr="lte")

    class Meta:
        model = RegistroAula
        fields = ["turma", "disciplina", "professor", "status"]
