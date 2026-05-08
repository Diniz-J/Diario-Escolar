"""Modelos da app accounts."""
from django.contrib.auth.models import AbstractUser
from django.db import models


class Usuario(AbstractUser):
    """Usuário do sistema com perfil de acesso e vínculo com Escola.

    O campo `escola` é opcional hoje porque o superusuário do Django (e
    eventuais contas globais de manutenção) não pertencem a nenhuma escola.
    Quando o sistema migrar para SaaS multi-tenant, a obrigatoriedade vai
    ser imposta via `clean()`/serializer para todos os perfis exceto
    superuser — sem precisar de migration de dados.
    """

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
    escola = models.ForeignKey(
        "escola.Escola",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="usuarios",
    )

    class Meta:
        verbose_name = "usuário"
        verbose_name_plural = "usuários"

    def __str__(self) -> str:
        return f"{self.get_full_name() or self.username} ({self.get_perfil_display()})"
