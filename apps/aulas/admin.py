"""Registro da app aulas no Django admin."""
from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

from .models import RegistroAula


@admin.register(RegistroAula)
class RegistroAulaAdmin(SimpleHistoryAdmin):
    list_display = (
        "data",
        "turma",
        "disciplina",
        "professor",
        "status",
        "escola",
    )
    list_filter = ("status", "escola", "data")
    search_fields = (
        "turma__nome",
        "disciplina__nome",
        "professor__usuario__first_name",
        "professor__usuario__last_name",
        "conteudo",
    )
    autocomplete_fields = (
        "escola",
        "turma",
        "disciplina",
        "professor",
        "conferido_por",
    )
    date_hierarchy = "data"
    ordering = ("-data",)
    readonly_fields = ("conferido_por", "conferido_em")
