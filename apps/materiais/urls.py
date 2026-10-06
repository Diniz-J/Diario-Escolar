"""Rotas da app materiais — incluídas no roteamento global em config/urls.py."""
from rest_framework.routers import DefaultRouter

from .views import MaterialViewSet

router = DefaultRouter()
router.register(r"materiais", MaterialViewSet, basename="material")

urlpatterns = router.urls
