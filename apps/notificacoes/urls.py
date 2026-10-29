"""Rotas da app de notificações — incluídas sob `/api/v1/`."""
from django.urls import path

from .tarefas import ExecutarTarefasView

urlpatterns = [
    path(
        "tarefas/executar/",
        ExecutarTarefasView.as_view(),
        name="tarefas-executar",
    ),
]
