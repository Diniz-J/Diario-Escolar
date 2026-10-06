"""Registro do portal no Django admin.

Enquanto não existe tela de gestão de responsáveis (fatia 6), o admin é
como a secretaria confere a semeadura e corrige um email errado.
"""
from django.contrib import admin
from django.db.models import Count
from simple_history.admin import SimpleHistoryAdmin

from .models import ConviteResponsavel, Responsavel, ResponsavelAluno


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

    def get_queryset(self, request):
        """Anota a contagem de vínculos.

        Sem isto, `total_alunos` dispararia um `COUNT(*)` por linha da
        listagem.
        """
        return (
            super()
            .get_queryset(request)
            .select_related("escola")
            .annotate(_total_alunos=Count("vinculos"))
        )

    @admin.display(description="alunos", ordering="_total_alunos")
    def total_alunos(self, obj) -> int:
        return obj._total_alunos


@admin.register(ResponsavelAluno)
class ResponsavelAlunoAdmin(SimpleHistoryAdmin):
    list_display = ("responsavel", "aluno", "criado_em")
    search_fields = ("responsavel__nome", "responsavel__email", "aluno__nome_completo")
    autocomplete_fields = ("responsavel", "aluno")


@admin.register(ConviteResponsavel)
class ConviteResponsavelAdmin(admin.ModelAdmin):
    """Só leitura: é como a secretaria confere se o convite saiu e se foi usado.

    Criar ou editar por aqui furaria o fluxo — o token cru só existe no
    email, e o hash sozinho não serve pra nada.
    """

    list_display = ("responsavel", "finalidade", "criado_em", "expira_em", "usado_em", "enviado_por")
    list_filter = ("finalidade",)
    search_fields = ("responsavel__nome", "responsavel__email")
    list_select_related = ("responsavel", "enviado_por")

    def has_add_permission(self, request) -> bool:
        return False

    def has_change_permission(self, request, obj=None) -> bool:
        return False
