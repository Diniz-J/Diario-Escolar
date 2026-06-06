"""Roteamento principal.

API REST versionada sob `/api/v1/`. Autenticação JWT (Bearer) é o padrão
para todos os endpoints da API — exceto os de obtenção/renovação de token,
que ficam públicos.

Endpoints de autenticação:
- `POST /api/v1/auth/token/` — obtem par (access + refresh) a partir de
  username/password.
- `POST /api/v1/auth/token/refresh/` — troca um refresh válido por um
  novo access.

Endpoints de domínio: ver os `urls.py` de cada app (`accounts`, `escola`,
`ocorrencias`, `presenca`) — todos incluídos no prefixo `/api/v1/`.
"""
from django.contrib import admin
from django.urls import include, path
from rest_framework_simplejwt.views import TokenRefreshView

from apps.accounts.views import (
    LogoutView,
    PasswordChangeRequestView,
    PasswordResetConfirmView,
    PasswordResetRequestView,
    UsuarioTokenObtainPairView,
)

api_v1_patterns = [
    path(
        "auth/token/",
        UsuarioTokenObtainPairView.as_view(),
        name="token_obtain_pair",
    ),
    path(
        "auth/token/refresh/",
        TokenRefreshView.as_view(),
        name="token_refresh",
    ),
    path(
        "auth/logout/",
        LogoutView.as_view(),
        name="logout",
    ),
    path(
        "auth/password/reset/request/",
        PasswordResetRequestView.as_view(),
        name="password_reset_request",
    ),
    path(
        "auth/password/reset/confirm/",
        PasswordResetConfirmView.as_view(),
        name="password_reset_confirm",
    ),
    path(
        "auth/password/change/",
        PasswordChangeRequestView.as_view(),
        name="password_change_request",
    ),
    path("", include("apps.accounts.urls")),
    path("", include("apps.escola.urls")),
    path("", include("apps.ocorrencias.urls")),
    path("", include("apps.presenca.urls")),
    path("", include("apps.boletins.urls")),
    path("", include("apps.planos_ensino.urls")),
    path("", include("apps.avaliacao.urls")),
]

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", include((api_v1_patterns, "api_v1"))),
]
