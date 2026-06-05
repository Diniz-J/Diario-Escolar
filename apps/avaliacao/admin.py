"""Registro dos modelos da app avaliacao no Django admin."""
from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

from .models import Avaliacao, NotaAvaliacao, NotaPeriodo, PeriodoAvaliativo


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


@admin.register(Avaliacao)
class AvaliacaoAdmin(SimpleHistoryAdmin):
    list_display = (
        "titulo",
        "tipo",
        "turma",
        "disciplina",
        "data",
        "periodo",
        "nota_maxima",
        "peso",
        "ativo",
    )
    list_filter = ("tipo", "ativo", "turma__ano_letivo", "escola")
    search_fields = ("titulo", "descricao")
    # autocompletes dependem dos search_fields configurados nos respectivos
    # admins de escola/turma/disciplina/professor.
    autocomplete_fields = ("turma", "disciplina", "professor", "escola")
    ordering = ("-data",)


@admin.register(NotaAvaliacao)
class NotaAvaliacaoAdmin(SimpleHistoryAdmin):
    list_display = ("aluno", "avaliacao", "nota", "atualizado_em")
    list_filter = ("avaliacao__tipo", "escola")
    search_fields = (
        "aluno__nome_completo",
        "aluno__matricula",
        "avaliacao__titulo",
    )
    autocomplete_fields = ("aluno", "avaliacao", "escola")
    ordering = ("-atualizado_em",)


@admin.register(NotaPeriodo)
class NotaPeriodoAdmin(SimpleHistoryAdmin):
    list_display = (
        "aluno",
        "disciplina",
        "periodo",
        "nota_final",
        "atualizado_em",
    )
    list_filter = ("periodo__ano_letivo", "disciplina", "escola")
    search_fields = (
        "aluno__nome_completo",
        "aluno__matricula",
        "disciplina__nome",
    )
    autocomplete_fields = ("aluno", "disciplina", "escola")
    ordering = ("-atualizado_em",)
