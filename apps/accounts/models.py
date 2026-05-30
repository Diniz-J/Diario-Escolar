"""Modelos da app accounts."""
from django.contrib.auth.models import AbstractUser
from django.db import models
from simple_history.models import HistoricalRecords


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

    # Audit log. `last_login` é excluído por ser barulho (atualiza a cada
    # login bem-sucedido); `password` é incluído porque o hash mudar já é
    # informação auditável (não expõe a senha, é PBKDF2 one-way).
    history = HistoricalRecords(excluded_fields=["last_login"])

    class Meta:
        verbose_name = "usuário"
        verbose_name_plural = "usuários"

    def __str__(self) -> str:
        return f"{self.get_full_name() or self.username} ({self.get_perfil_display()})"
