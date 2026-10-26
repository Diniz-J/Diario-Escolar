"""Rotas do financeiro — incluídas no roteamento global em config/urls.py."""
from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    FaturaItemViewSet,
    FaturaViewSet,
    FichaFinanceiraAlunoView,
    PagamentoViewSet,
    PlanoCobrancaViewSet,
)
from .webhooks import WebhookAsaasView

router = DefaultRouter()
router.register(r"planos-cobranca", PlanoCobrancaViewSet, basename="planocobranca")
router.register(r"faturas", FaturaViewSet, basename="fatura")
router.register(r"fatura-itens", FaturaItemViewSet, basename="faturaitem")
router.register(r"pagamentos", PagamentoViewSet, basename="pagamento")

urlpatterns = [
    # Fora do router: é agregação de um aluno, não CRUD de recurso.
    path(
        "financeiro/alunos/<int:aluno_id>/",
        FichaFinanceiraAlunoView.as_view(),
        name="ficha-financeira-aluno",
    ),
    # Entrada do provedor, não recurso nosso: rota por gateway, pra que um
    # segundo provedor ganhe a sua em vez de disputar esta.
    path(
        "financeiro/webhooks/asaas/",
        WebhookAsaasView.as_view(),
        name="webhook-asaas",
    ),
    *router.urls,
]
