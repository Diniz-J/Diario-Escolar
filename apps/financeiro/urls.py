"""Rotas do financeiro — incluídas no roteamento global em config/urls.py."""
from rest_framework.routers import DefaultRouter

from .views import (
    FaturaItemViewSet,
    FaturaViewSet,
    PagamentoViewSet,
    PlanoCobrancaViewSet,
)

router = DefaultRouter()
router.register(r"planos-cobranca", PlanoCobrancaViewSet, basename="planocobranca")
router.register(r"faturas", FaturaViewSet, basename="fatura")
router.register(r"fatura-itens", FaturaItemViewSet, basename="faturaitem")
router.register(r"pagamentos", PagamentoViewSet, basename="pagamento")

urlpatterns = router.urls
