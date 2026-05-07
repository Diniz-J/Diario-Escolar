"""Roteamento principal — rotas da API serão versionadas em /api/v1/ na etapa 6."""
from django.contrib import admin
from django.urls import path

urlpatterns = [
    path("admin/", admin.site.urls),
]
