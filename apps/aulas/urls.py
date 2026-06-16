"""Rotas da app aulas — incluídas no roteamento global em config/urls.py."""
from rest_framework.routers import DefaultRouter

from .views import RegistroAulaViewSet

router = DefaultRouter()
router.register(r"registros-aula", RegistroAulaViewSet, basename="registro-aula")

urlpatterns = router.urls
