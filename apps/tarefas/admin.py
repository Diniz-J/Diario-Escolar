"""Registro da app tarefas no Django admin."""
from django.contrib import admin

from .models import EntregaTarefa, Tarefa


class EntregaTarefaInline(admin.TabularInline):
    """Edita entregas inline dentro da página da tarefa."""

    model = EntregaTarefa
    fields = ("aluno", "entregue", "data_entrega", "nota", "observacao")
    autocomplete_fields = ("aluno",)
    extra = 0
    can_delete = False
    show_change_link = True


@admin.register(Tarefa)
class TarefaAdmin(admin.ModelAdmin):
    list_display = (
        "titulo",
        "turma",
        "disciplina",
        "data_lancamento",
        "prazo",
        "vale_nota",
        "escola",
    )
    list_filter = ("vale_nota", "data_lancamento", "escola", "turma", "disciplina")
    search_fields = ("titulo", "descricao")
    autocomplete_fields = ("escola", "turma", "disciplina", "professor")
    date_hierarchy = "data_lancamento"
    inlines = [EntregaTarefaInline]
    ordering = ("-data_lancamento", "-criado_em")


@admin.register(EntregaTarefa)
class EntregaTarefaAdmin(admin.ModelAdmin):
    list_display = ("tarefa", "aluno", "entregue", "data_entrega", "nota")
    list_filter = ("entregue", "escola")
    search_fields = ("aluno__nome_completo", "aluno__matricula", "tarefa__titulo")
    autocomplete_fields = ("aluno",)
    ordering = ("tarefa", "aluno__nome_completo")
