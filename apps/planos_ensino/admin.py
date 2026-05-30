"""Registro da app planos_ensino no Django admin."""
from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

from .models import PlanoEnsino


@admin.register(PlanoEnsino)
class PlanoEnsinoAdmin(SimpleHistoryAdmin):
    list_display = (
        "turma",
        "disciplina",
        "ano_letivo",
        "professor",
        "ativo",
        "escola",
    )
    list_filter = ("ano_letivo", "ativo", "escola", "turma", "disciplina")
    search_fields = ("ementa", "conteudo_programatico", "habilidades_bncc")
    autocomplete_fields = ("escola", "turma", "disciplina", "professor")
    fieldsets = (
        ("Identificação", {
            "fields": (
                "escola", "turma", "disciplina", "professor", "ano_letivo",
                "ativo",
            ),
        }),
        ("Programação", {
            "fields": (
                "ementa", "conteudo_programatico",
                "objetivos_gerais", "objetivos_especificos",
                "habilidades_bncc", "carga_horaria",
            ),
        }),
        ("Execução", {
            "fields": ("metodologia", "recursos", "avaliacao"),
        }),
    )
    ordering = ("-ano_letivo", "turma__nome", "disciplina__nome")
