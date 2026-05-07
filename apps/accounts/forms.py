"""Formulários do admin para o modelo Usuario."""
from django.contrib.auth.forms import AdminUserCreationForm, UserChangeForm

from .models import Usuario


class UsuarioCreationForm(AdminUserCreationForm):
    """Form de criação no admin, incluindo o campo `perfil`.

    Herda de `AdminUserCreationForm` (Django 5.2+) — que inclui o campo
    `usable_password` referenciado pelo `UserAdmin.add_fieldsets`. Herdar
    de `UserCreationForm` direto causa FieldError ao renderizar o admin.
    """

    class Meta(AdminUserCreationForm.Meta):
        model = Usuario
        fields = AdminUserCreationForm.Meta.fields + ("perfil",)


class UsuarioChangeForm(UserChangeForm):
    """Form de edição no admin para o modelo Usuario customizado."""

    class Meta(UserChangeForm.Meta):
        model = Usuario
