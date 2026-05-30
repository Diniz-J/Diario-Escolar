"""Registro da app accounts no Django admin."""
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from simple_history.admin import SimpleHistoryAdmin

from .forms import UsuarioChangeForm, UsuarioCreationForm
from .models import Usuario


@admin.register(Usuario)
class UsuarioAdmin(SimpleHistoryAdmin, UserAdmin):
    """Admin do Usuario com o campo `perfil` adicional + aba de histórico.

    A ordem do MRO importa: `SimpleHistoryAdmin` precisa vir ANTES de
    `UserAdmin` para que o template do botão "History" seja resolvido
    pelo simple-history; ambos são subclasses de `ModelAdmin`.
    """

    add_form = UsuarioCreationForm
    form = UsuarioChangeForm

    fieldsets = UserAdmin.fieldsets + (
        ("Perfil de acesso", {"fields": ("perfil",)}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ("Perfil de acesso", {"fields": ("perfil",)}),
    )
    list_display = ("username", "email", "first_name", "last_name", "perfil", "is_staff")
    list_filter = ("perfil", "is_staff", "is_superuser", "is_active")
    search_fields = ("username", "first_name", "last_name", "email")
