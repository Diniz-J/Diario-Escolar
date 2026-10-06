"""Rotas do portal do responsável — incluídas sob `/api/v1/portal/`."""
from django.urls import path

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
]
