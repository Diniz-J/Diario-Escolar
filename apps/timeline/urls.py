"""Rotas da timeline do aluno.

Sem router: é uma APIView de leitura, não um ViewSet de recurso — mesma
escolha de `boletins` e `relatorios`.
"""
from django.urls import path

from .views import TimelineAlunoView

urlpatterns = [
    path(
        "timeline/aluno/<int:aluno_id>/",
        TimelineAlunoView.as_view(),
        name="timeline-aluno",
    ),
]
