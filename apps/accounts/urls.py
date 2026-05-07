"""Rotas da app accounts — incluídas no roteamento global em config/urls.py (etapa 6)."""
from rest_framework.routers import DefaultRouter

from .views import UsuarioViewSet

router = DefaultRouter()
router.register(r"usuarios", UsuarioViewSet, basename="usuario")

urlpatterns = router.urls
