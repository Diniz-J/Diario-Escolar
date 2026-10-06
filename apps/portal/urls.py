"""Rotas do portal do responsável — incluídas sob `/api/v1/portal/`."""
from django.urls import path

from .leituras import (
    BoletimFilhoView,
    ComunicadoDetalheView,
    ComunicadosView,
    FilhoDetalheView,
    FilhosView,
    OcorrenciasFilhoView,
    PeriodosView,
)
from .views import (
    PortalDefinirSenhaView,
    PortalEsqueciSenhaView,
    PortalLoginView,
    PortalLogoutView,
    PortalMeView,
    PortalTokenRefreshView,
)

urlpatterns = [
    path("auth/login/", PortalLoginView.as_view(), name="portal_login"),
    path("auth/refresh/", PortalTokenRefreshView.as_view(), name="portal_refresh"),
    path("auth/logout/", PortalLogoutView.as_view(), name="portal_logout"),
    path(
        "auth/senha/esqueci/",
        PortalEsqueciSenhaView.as_view(),
        name="portal_senha_esqueci",
    ),
    path(
        "auth/senha/definir/",
        PortalDefinirSenhaView.as_view(),
        name="portal_senha_definir",
    ),
    path("me/", PortalMeView.as_view(), name="portal_me"),
    # Leituras (fatia 4) — tudo parte dos vínculos do responsável.
    path("alunos/", FilhosView.as_view(), name="portal_alunos"),
    path("alunos/<int:pk>/", FilhoDetalheView.as_view(), name="portal_aluno"),
    path(
        "alunos/<int:pk>/boletim/",
        BoletimFilhoView.as_view(),
        name="portal_aluno_boletim",
    ),
    path(
        "alunos/<int:pk>/ocorrencias/",
        OcorrenciasFilhoView.as_view(),
        name="portal_aluno_ocorrencias",
    ),
    path("periodos/", PeriodosView.as_view(), name="portal_periodos"),
    path("comunicados/", ComunicadosView.as_view(), name="portal_comunicados"),
    path(
        "comunicados/<int:pk>/",
        ComunicadoDetalheView.as_view(),
        name="portal_comunicado",
    ),
]
