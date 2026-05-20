"""Registro da app presenca no Django admin."""
from django.contrib import admin

from .models import ItemPresenca, RegistroPresenca


class ItemPresencaInline(admin.TabularInline):
    """Edita itens diretamente na página do registro pai."""

    model = ItemPresenca
    fields = ("aluno", "status", "observacao")
    autocomplete_fields = ("aluno",)
    extra = 0
    # Itens só fazem sentido juntos com seu registro; não permitir adicionar
    # manualmente no admin evita estado inconsistente (item sem `escola` setada,
    # aluno fora da turma do registro, etc.). Edição inline ainda funciona.
    can_delete = False
    show_change_link = True


@admin.register(RegistroPresenca)
class RegistroPresencaAdmin(admin.ModelAdmin):
    list_display = ("turma", "data", "professor", "escola")
    list_filter = ("data", "escola", "turma")
    search_fields = ("turma__nome", "observacao")
    autocomplete_fields = ("escola", "turma", "professor")
    date_hierarchy = "data"
    inlines = [ItemPresencaInline]
    ordering = ("-data",)


@admin.register(ItemPresenca)
class ItemPresencaAdmin(admin.ModelAdmin):
    list_display = ("registro", "aluno", "status", "escola")
    list_filter = ("status", "escola")
    search_fields = ("aluno__nome_completo", "aluno__matricula", "observacao")
    autocomplete_fields = ("aluno",)
    ordering = ("registro", "aluno__nome_completo")
