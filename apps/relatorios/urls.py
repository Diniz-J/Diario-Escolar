"""Rotas dos relatórios operacionais.

Sem router: são APIViews de leitura, não ViewSets de recurso.
"""
from django.urls import path

from .views import RelatorioDashboardView, RelatorioFrequenciaView

urlpatterns = [
    path(
        "relatorios/frequencia/",
        RelatorioFrequenciaView.as_view(),
        name="relatorio_frequencia",
    ),
    path(
        "relatorios/dashboard/",
        RelatorioDashboardView.as_view(),
        name="relatorio_dashboard",
    ),
]
