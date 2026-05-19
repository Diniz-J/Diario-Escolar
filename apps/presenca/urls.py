"""Rotas da app presenca — incluídas no roteamento global em config/urls.py (etapa 6)."""
from rest_framework.routers import DefaultRouter

from .views import ItemPresencaViewSet, RegistroPresencaViewSet

router = DefaultRouter()
router.register(
    r"registros-presenca", RegistroPresencaViewSet, basename="registro-presenca"
)
router.register(
    r"itens-presenca", ItemPresencaViewSet, basename="item-presenca"
)

urlpatterns = router.urls
