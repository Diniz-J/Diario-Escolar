"""Rotas da app boletins."""
from django.urls import path

from .views import BoletimAlunoView

urlpatterns = [
    path(
        "boletins/aluno/<int:aluno_id>/",
        BoletimAlunoView.as_view(),
        name="boletim-aluno",
    ),
]
