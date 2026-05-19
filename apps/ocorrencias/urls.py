"""Rotas da app ocorrencias — incluídas no roteamento global em config/urls.py (etapa 6)."""
from rest_framework.routers import DefaultRouter

from .views import OcorrenciaViewSet

router = DefaultRouter()
router.register(r"ocorrencias", OcorrenciaViewSet, basename="ocorrencia")

urlpatterns = router.urls
