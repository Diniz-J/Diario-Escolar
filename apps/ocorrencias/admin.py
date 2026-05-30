"""Registro da app ocorrencias no Django admin."""
from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

from .models import Ocorrencia


@admin.register(Ocorrencia)
class OcorrenciaAdmin(SimpleHistoryAdmin):
    list_display = (
        "aluno",
        "turma",
        "professor",
        "status",
        "data_ocorrencia",
        "escola",
    )
    list_filter = ("status", "data_ocorrencia", "escola", "turma")
    search_fields = (
        "aluno__nome_completo",
        "aluno__matricula",
        "descricao",
    )
    # Depende dos search_fields configurados em escola.admin.
    autocomplete_fields = ("escola", "turma", "aluno", "professor")
    date_hierarchy = "data_ocorrencia"
    ordering = ("-data_ocorrencia", "-criado_em")
