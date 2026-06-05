"""Rotas da app avaliacao — incluídas no roteamento global em config/urls.py."""
from rest_framework.routers import DefaultRouter

from .views import (
    AvaliacaoViewSet,
    NotaAvaliacaoViewSet,
    PeriodoAvaliativoViewSet,
)

router = DefaultRouter()
router.register(
    r"periodos-avaliativos",
    PeriodoAvaliativoViewSet,
    basename="periodo-avaliativo",
)
router.register(r"avaliacoes", AvaliacaoViewSet, basename="avaliacao")
router.register(
    r"notas-avaliacao", NotaAvaliacaoViewSet, basename="nota-avaliacao"
)

urlpatterns = router.urls
