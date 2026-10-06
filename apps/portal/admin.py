"""Registro do portal no Django admin.

Enquanto não existe tela de gestão de responsáveis (fatia 6), o admin é
como a secretaria confere a semeadura e corrige um email errado.
"""
from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

from .models import Responsavel, ResponsavelAluno


class ResponsavelAlunoInline(admin.TabularInline):
    """Vínculos do responsável, editáveis — é como se corrige um vínculo errado."""

    model = ResponsavelAluno
    extra = 0
    autocomplete_fields = ("aluno",)


@admin.register(Responsavel)
class ResponsavelAdmin(SimpleHistoryAdmin):
    list_display = ("nome", "email", "escola", "ativo", "total_alunos")
    list_filter = ("ativo", "escola")
    search_fields = ("nome", "email", "alunos__nome_completo")
    # `password` e `last_login` vêm do AbstractBaseUser. A senha não é
    # editável aqui: quem define é o responsável, pelo convite.
    readonly_fields = ("password", "last_login", "criado_em", "atualizado_em")
    inlines = (ResponsavelAlunoInline,)

    @admin.display(description="alunos")
    def total_alunos(self, obj) -> int:
        return obj.vinculos.count()


@admin.register(ResponsavelAluno)
class ResponsavelAlunoAdmin(SimpleHistoryAdmin):
    list_display = ("responsavel", "aluno", "criado_em")
    search_fields = ("responsavel__nome", "responsavel__email", "aluno__nome_completo")
    autocomplete_fields = ("responsavel", "aluno")
