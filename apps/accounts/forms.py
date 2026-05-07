"""Formulários do admin para o modelo Usuario."""
from django.contrib.auth.forms import UserChangeForm, UserCreationForm

from .models import Usuario


class UsuarioCreationForm(UserCreationForm):
    """Form de criação no admin, incluindo o campo `perfil`."""

    class Meta(UserCreationForm.Meta):
        model = Usuario
        fields = UserCreationForm.Meta.fields + ("perfil",)


class UsuarioChangeForm(UserChangeForm):
    """Form de edição no admin para o modelo Usuario customizado."""

    class Meta(UserChangeForm.Meta):
        model = Usuario
