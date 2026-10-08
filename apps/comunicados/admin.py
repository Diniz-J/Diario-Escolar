"""Registro da app comunicados no Django admin."""
from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

from .models import Comunicado, ComunicadoDestinatario


class ComunicadoDestinatarioInline(admin.TabularInline):
    """Log de entrega embutido no comunicado — somente leitura.

    `extra=0` e tudo readonly: as linhas são criadas pelo serviço de
    disparo. Editá-las pelo admin corromperia a auditoria de entrega.

    A FK `responsavel` fica **fora** dos campos de propósito. Agora que há
    uma linha por responsável, a coluna seria redundante — o snapshot de
    `email`/`nome_responsavel` já identifica quem recebeu, e é justamente
    pra isso que ele existe. Renderizar mais uma FK readonly dobraria o
    `str()` por linha num inline que já faz um por `aluno`: num comunicado
    de escola inteira isso é centenas de queries pra repetir informação
    que a linha já mostra.
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
