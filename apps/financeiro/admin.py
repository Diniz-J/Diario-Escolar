"""Registro da app financeiro no Django admin.

O admin é hoje o único caminho de cadastro do módulo (a API é a fatia
seguinte), então vale a pena ter os inlines: a secretaria abre a fatura e
vê o detalhamento e os pagamentos dela na mesma página.
"""
from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

from .models import Fatura, FaturaItem, Pagamento, PlanoCobranca


class FaturaItemInline(admin.TabularInline):
    """Detalhamento da fatura, editado na página dela.

    Sem `can_delete=False` (ao contrário do `ItemPresencaInline`): aqui a
    linha é informativa, e corrigir uma taxa lançada errado é operação
    legítima da secretaria.
    """

    model = FaturaItem
    fields = ("descricao", "valor", "escola")
    autocomplete_fields = ("escola",)
    extra = 0
    show_change_link = True


class PagamentoInline(admin.TabularInline):
    """Pagamentos conciliados contra a fatura.

    Só leitura: `valor_pago`/`status` da fatura são escritos pelo
    `services.py`, e registrar pagamento por aqui deixaria a fatura com
    dinheiro recebido e status intocado. O registro manual entra pela API
    (fatia 2), que passa pelo service.
    """

    model = Pagamento
    fields = ("valor", "data", "metodo", "referencia_externa")
    readonly_fields = fields
    extra = 0
    can_delete = False
    show_change_link = True

    def has_add_permission(self, request, obj) -> bool:
        return False


@admin.register(PlanoCobranca)
class PlanoCobrancaAdmin(SimpleHistoryAdmin):
    list_display = (
        "aluno",
        "valor_mensalidade",
        "dia_vencimento",
        "desconto_tipo",
        "desconto_valor",
        "vigencia_inicio",
        "vigencia_fim",
        "ativo",
        "escola",
    )
    list_filter = ("ativo", "desconto_tipo", "escola")
    search_fields = ("aluno__nome_completo", "aluno__matricula")
    list_select_related = ("aluno", "escola")
    autocomplete_fields = ("escola", "aluno")
    ordering = ("-vigencia_inicio",)


@admin.register(Fatura)
class FaturaAdmin(SimpleHistoryAdmin):
    list_display = (
        "aluno",
        "competencia",
        "valor",
        "vencimento",
        "status",
        "valor_pago",
        "data_pagamento",
        "escola",
    )
    list_filter = ("status", "escola", "competencia")
    search_fields = (
        "aluno__nome_completo",
        "aluno__matricula",
        "id_externo",
    )
    list_select_related = ("aluno", "plano", "escola")
    autocomplete_fields = ("escola", "plano", "aluno")
    # `valor_pago` e `data_pagamento` são escritos pelo `services.py` na
    # conciliação, nunca à mão — mesma razão de o `PagamentoInline` ser
    # somente leitura. Editá-los no change form deixaria a fatura com
    # dinheiro recebido sem o `Pagamento` que o explica.
    readonly_fields = ("valor_pago", "data_pagamento")
    date_hierarchy = "vencimento"
    inlines = [FaturaItemInline, PagamentoInline]
    ordering = ("-competencia",)


@admin.register(FaturaItem)
class FaturaItemAdmin(SimpleHistoryAdmin):
    list_display = ("fatura", "descricao", "valor", "escola")
    list_filter = ("escola",)
    search_fields = ("descricao", "fatura__aluno__nome_completo")
    list_select_related = ("fatura__aluno", "escola")
    autocomplete_fields = ("escola", "fatura")


@admin.register(Pagamento)
class PagamentoAdmin(SimpleHistoryAdmin):
    list_display = ("fatura", "valor", "data", "metodo", "referencia_externa", "escola")
    list_filter = ("metodo", "escola", "data")
    search_fields = (
        "referencia_externa",
        "fatura__aluno__nome_completo",
        "fatura__aluno__matricula",
    )
    list_select_related = ("fatura__aluno", "escola")
    autocomplete_fields = ("escola", "fatura")
    date_hierarchy = "data"
    ordering = ("-data",)
