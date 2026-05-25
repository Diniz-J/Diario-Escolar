"""Rotas da app tarefas — incluídas no roteamento global em config/urls.py."""
from rest_framework.routers import DefaultRouter

from .views import EntregaTarefaViewSet, TarefaViewSet

router = DefaultRouter()
router.register(r"tarefas", TarefaViewSet, basename="tarefa")
router.register(
    r"entregas-tarefa", EntregaTarefaViewSet, basename="entrega-tarefa"
)

urlpatterns = router.urls
