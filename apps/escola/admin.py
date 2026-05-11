"""Registro dos modelos da app escola no Django admin.

Nota sobre `autocomplete_fields`: o Django exige que o admin do modelo
referenciado tenha `search_fields` configurado. Removendo `search_fields`
de `EscolaAdmin`, `TurmaAdmin` ou `AlunoAdmin` quebra os autocompletes
abaixo em runtime sem aviso prévio.
"""
from django.contrib import admin

from .models import Aluno, Disciplina, Escola, Professor, Turma


@admin.register(Escola)
class EscolaAdmin(admin.ModelAdmin):
    list_display = ("nome", "cnpj", "ativa", "criado_em")
    list_filter = ("ativa",)
    # search_fields é dependência dos autocomplete_fields nos outros admins.
    search_fields = ("nome", "cnpj")
    ordering = ("nome",)


@admin.register(Turma)
class TurmaAdmin(admin.ModelAdmin):
    list_display = ("nome", "turno", "ano_letivo", "escola", "ativa")
    list_filter = ("turno", "ano_letivo", "ativa", "escola")
    # search_fields é dependência do autocomplete em AlunoAdmin (turma).
    search_fields = ("nome",)
    autocomplete_fields = ("escola",)  # depende de EscolaAdmin.search_fields
    ordering = ("-ano_letivo", "nome")


@admin.register(Disciplina)
class DisciplinaAdmin(admin.ModelAdmin):
    list_display = ("nome", "escola", "ativa")
    list_filter = ("ativa", "escola")
    search_fields = ("nome",)
    autocomplete_fields = ("escola",)  # depende de EscolaAdmin.search_fields
    ordering = ("nome",)


@admin.register(Aluno)
class AlunoAdmin(admin.ModelAdmin):
    list_display = ("nome_completo", "matricula", "turma", "escola", "ativo")
    list_filter = ("ativo", "turma", "escola")
    search_fields = ("nome_completo", "matricula")
    # depende de TurmaAdmin.search_fields e EscolaAdmin.search_fields
    autocomplete_fields = ("turma", "escola")
    ordering = ("nome_completo",)


@admin.register(Professor)
class ProfessorAdmin(admin.ModelAdmin):
    list_display = ("usuario", "escola", "ativo")
    list_filter = ("ativo", "escola")
    # Busca pelos campos do Usuario relacionado — útil pra autocompletes
    # futuros em Ocorrencia/Presença.
    search_fields = (
        "usuario__first_name",
        "usuario__last_name",
        "usuario__username",
    )
    autocomplete_fields = ("escola",)
    filter_horizontal = ("disciplinas",)
    ordering = ("usuario__first_name", "usuario__last_name")
