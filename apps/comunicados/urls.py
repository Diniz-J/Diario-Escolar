"""Rotas da app comunicados — incluídas no roteamento global em config/urls.py."""
from rest_framework.routers import DefaultRouter

from .views import ComunicadoViewSet

router = DefaultRouter()
router.register(r"comunicados", ComunicadoViewSet, basename="comunicado")

urlpatterns = router.urls
