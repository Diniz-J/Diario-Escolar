"""Rotas da app escola — incluídas no roteamento global em config/urls.py (etapa 6)."""
from rest_framework.routers import DefaultRouter

from .views import (
    AlunoViewSet,
    DisciplinaViewSet,
    EscolaViewSet,
    LecionamentoViewSet,
    ProfessorViewSet,
    TurmaViewSet,
)

router = DefaultRouter()
router.register(r"escolas", EscolaViewSet, basename="escola")
router.register(r"turmas", TurmaViewSet, basename="turma")
router.register(r"disciplinas", DisciplinaViewSet, basename="disciplina")
router.register(r"alunos", AlunoViewSet, basename="aluno")
router.register(r"professores", ProfessorViewSet, basename="professor")
router.register(r"lecionamentos", LecionamentoViewSet, basename="lecionamento")

urlpatterns = router.urls
