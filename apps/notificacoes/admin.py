from django.contrib import admin

from .models import Mensagem


@admin.register(Mensagem)
class MensagemAdmin(admin.ModelAdmin):
    """Só leitura: o outbox é registro do que aconteceu, não formulário.

    Editar status à mão aqui faria a linha mentir sobre o envio, e é
    justamente essa linha que a escola consulta pra saber se o
    responsável foi avisado.
    """

    list_display = (
        "destinatario",
        "origem",
        "assunto",
        "status",
        "tentativas",
        "criado_em",
    )
    list_filter = ("status", "origem", "escola")
    search_fields = ("destinatario", "assunto")
    date_hierarchy = "criado_em"

    def has_add_permission(self, request) -> bool:
        return False

    def has_change_permission(self, request, obj=None) -> bool:
        return False
