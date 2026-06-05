"""Rotas da app boletins."""
from django.urls import path

from .views import (
    BoletimAlunoAvaliacoesView,
    BoletimAlunoPDFView,
    BoletimAlunoView,
)

urlpatterns = [
    path(
        "boletins/aluno/<int:aluno_id>/",
        BoletimAlunoView.as_view(),
        name="boletim-aluno",
    ),
    path(
        "boletins/aluno/<int:aluno_id>/pdf/",
        BoletimAlunoPDFView.as_view(),
        name="boletim-aluno-pdf",
    ),
    path(
        "boletins/aluno/<int:aluno_id>/avaliacoes/",
        BoletimAlunoAvaliacoesView.as_view(),
        name="boletim-aluno-avaliacoes",
    ),
]
