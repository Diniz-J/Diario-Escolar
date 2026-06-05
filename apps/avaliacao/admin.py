"""Registro dos modelos da app avaliacao no Django admin."""
from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

from .models import PeriodoAvaliativo


@admin.register(PeriodoAvaliativo)
class PeriodoAvaliativoAdmin(SimpleHistoryAdmin):
    list_display = (
        "nome",
        "ordem",
        "ano_letivo",
        "data_inicio",
        "data_fim",
        "escola",
        "ativo",
    )
    list_filter = ("ano_letivo", "ativo", "escola")
    search_fields = ("nome",)
    # depende de EscolaAdmin.search_fields (configurado em apps/escola/admin.py)
    autocomplete_fields = ("escola",)
    ordering = ("-ano_letivo", "ordem")
