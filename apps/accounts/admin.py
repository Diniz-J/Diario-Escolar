"""Registro da app accounts no Django admin."""
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .forms import UsuarioChangeForm, UsuarioCreationForm
from .models import Usuario


@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    """Admin do Usuario com o campo `perfil` adicional."""

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
