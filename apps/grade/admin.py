"""Admin da app grade."""
from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

from .models import AulaGrade, TempoAula


@admin.register(TempoAula)
class TempoAulaAdmin(admin.ModelAdmin):
    list_display = ("ordem", "turno", "hora_inicio", "hora_fim", "escola", "ativo")
    list_filter = ("turno", "ativo", "escola")
    autocomplete_fields = ("escola",)
    ordering = ("escola", "turno", "ordem")


@admin.register(AulaGrade)
class AulaGradeAdmin(SimpleHistoryAdmin):
    list_display = ("turma", "dia_semana", "tempo", "lecionamento", "ativo")
    list_filter = ("dia_semana", "ativo", "escola", "turma__ano_letivo")
    search_fields = (
        "turma__nome",
        "lecionamento__disciplina__nome",
        "lecionamento__professor__usuario__first_name",
        "lecionamento__professor__usuario__last_name",
    )
    autocomplete_fields = ("escola",)
    ordering = ("turma__nome", "dia_semana")
