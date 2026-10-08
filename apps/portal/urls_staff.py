"""Rotas do STAFF sobre responsáveis — fora do prefixo `portal/`.

O prefixo `portal/` é do responsável, com autenticação própria. Estas
rotas são da área administrativa e usam a autenticação padrão, então
moram na raiz da API (`/api/v1/responsaveis/...`).

O `convidar` já existia (fatia 3) e veio pra cá junto: o nome da rota
(`responsavel_convidar`) é o mesmo, então nada que usa `reverse` muda.
"""
from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import ConvidarResponsavelView
from .views_staff import ResponsavelStaffViewSet

router = DefaultRouter()
router.register(r"responsaveis", ResponsavelStaffViewSet, basename="responsavel")

# O path explícito vem ANTES do router: o detail do router casa
# `responsaveis/<pk>/` e não pegaria `responsaveis/<pk>/convidar/`, mas a
# ordem deixa a intenção clara.
urlpatterns = [
    path(
        "responsaveis/<int:pk>/convidar/",
        ConvidarResponsavelView.as_view(),
        name="responsavel_convidar",
    ),
    *router.urls,
]
