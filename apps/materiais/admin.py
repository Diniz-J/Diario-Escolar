"""Registro da app materiais no Django admin."""
from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

from .models import Material


@admin.register(Material)
class MaterialAdmin(SimpleHistoryAdmin):
    list_display = ("titulo", "turma", "disciplina", "professor", "publicado_em", "ativo", "escola")
    list_filter = ("ativo", "escola")
    search_fields = ("titulo", "descricao", "turma__nome", "disciplina__nome")
    list_select_related = ("turma", "disciplina", "professor__usuario", "escola")
    autocomplete_fields = ("escola", "turma", "disciplina", "professor")
