"""Rotas da app grade — incluídas sob `/api/v1/` em `config/urls.py`."""
from rest_framework.routers import DefaultRouter

from .views import AulaGradeViewSet, TempoAulaViewSet

router = DefaultRouter()
router.register(r"tempos-aula", TempoAulaViewSet, basename="tempo-aula")
router.register(r"grade-aulas", AulaGradeViewSet, basename="aula-grade")

urlpatterns = router.urls
