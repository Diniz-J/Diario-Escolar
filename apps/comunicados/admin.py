"""Registro da app comunicados no Django admin."""
from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

from .models import Comunicado, ComunicadoDestinatario


class ComunicadoDestinatarioInline(admin.TabularInline):
    """Log de entrega embutido no comunicado — somente leitura.

    `extra=0` e tudo readonly: as linhas são criadas pelo serviço de
    disparo. Editá-las pelo admin corromperia a auditoria de entrega.
    """

    model = ComunicadoDestinatario
    extra = 0
    can_delete = False
    fields = ("aluno", "email", "nome_responsavel", "status", "erro", "enviado_em")
    readonly_fields = fields

    def has_add_permission(self, request, obj=None) -> bool:
        return False


@admin.register(Comunicado)
class ComunicadoAdmin(SimpleHistoryAdmin):
    list_display = (
        "titulo",
        "destino",
        "status",
        "total_enviados",
        "total_falhas",
        "total_sem_email",
        "enviado_em",
        "escola",
    )
    list_filter = ("status", "destino", "escola")
    search_fields = ("titulo", "mensagem")
    filter_horizontal = ("turmas",)
    # Resultado do disparo é escrito pelo serviço, não pelo operador.
    readonly_fields = (
        "status",
        "enviado_em",
        "enviado_por",
        "total_destinatarios",
        "total_enviados",
        "total_falhas",
        "total_sem_email",
        "criado_em",
        "atualizado_em",
    )
    inlines = (ComunicadoDestinatarioInline,)
