"""Modelos da app accounts."""
from django.contrib.auth.models import AbstractUser
from django.db import models


class Usuario(AbstractUser):
    """Usuário do sistema com perfil de acesso."""

    class Perfil(models.TextChoices):
        ADMIN = "admin", "Admin"
        DIRETOR = "diretor", "Diretor"
        PROFESSOR = "professor", "Professor"
        SECRETARIA = "secretaria", "Secretaria"
        INSPETOR = "inspetor", "Inspetor"

    perfil = models.CharField(
        max_length=20,
        choices=Perfil.choices,
        default=Perfil.PROFESSOR,
    )

    class Meta:
        verbose_name = "usuário"
        verbose_name_plural = "usuários"

    def __str__(self) -> str:
        return f"{self.get_full_name() or self.username} ({self.get_perfil_display()})"
