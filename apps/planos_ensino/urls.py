"""Rotas da app planos_ensino — incluídas em config/urls.py."""
from rest_framework.routers import DefaultRouter

from .views import PlanoEnsinoViewSet

router = DefaultRouter()
router.register(r"planos-ensino", PlanoEnsinoViewSet, basename="plano-ensino")

urlpatterns = router.urls
