"""Registro dos modelos da app escola no Django admin."""
from django.contrib import admin

from .models import Aluno, Disciplina, Escola, Turma


@admin.register(Escola)
class EscolaAdmin(admin.ModelAdmin):
    list_display = ("nome", "cnpj", "ativa", "criado_em")
    list_filter = ("ativa",)
    search_fields = ("nome", "cnpj")
    ordering = ("nome",)


@admin.register(Turma)
class TurmaAdmin(admin.ModelAdmin):
    list_display = ("nome", "turno", "ano_letivo", "escola", "ativa")
    list_filter = ("turno", "ano_letivo", "ativa", "escola")
    search_fields = ("nome",)
    autocomplete_fields = ("escola",)
    ordering = ("-ano_letivo", "nome")


@admin.register(Disciplina)
class DisciplinaAdmin(admin.ModelAdmin):
    list_display = ("nome", "escola", "ativa")
    list_filter = ("ativa", "escola")
    search_fields = ("nome",)
    autocomplete_fields = ("escola",)
    ordering = ("nome",)


@admin.register(Aluno)
class AlunoAdmin(admin.ModelAdmin):
    list_display = ("nome_completo", "matricula", "turma", "escola", "ativo")
    list_filter = ("ativo", "turma", "escola")
    search_fields = ("nome_completo", "matricula")
    autocomplete_fields = ("turma", "escola")
    ordering = ("nome_completo",)
