"""Rotas da app avaliacao — incluídas no roteamento global em config/urls.py."""
from rest_framework.routers import DefaultRouter

from .views import PeriodoAvaliativoViewSet

router = DefaultRouter()
router.register(
    r"periodos-avaliativos",
    PeriodoAvaliativoViewSet,
    basename="periodo-avaliativo",
)

urlpatterns = router.urls
