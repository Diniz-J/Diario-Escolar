"""Modelos da app accounts."""
import hashlib
import secrets
from datetime import timedelta

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone
from simple_history.models import HistoricalRecords


class Usuario(AbstractUser):
    """Usuário do sistema com perfil de acesso e vínculo com Escola.

    O campo `escola` é opcional hoje porque o superusuário do Django (e
    eventuais contas globais de manutenção) não pertencem a nenhuma escola.
    Quando o sistema migrar para SaaS multi-tenant, a obrigatoriedade vai
    ser imposta via `clean()`/serializer para todos os perfis exceto
    superuser — sem precisar de migration de dados.

    `email` é obrigatório (sobrescreve o AbstractUser que tem `blank=True`)
    porque é a chave do fluxo de redefinição de senha — sem email, não há
    como entregar o token de reset. Usuários legados sem email são
    preenchidos pela data migration 0004 com placeholder
    `{username}@diariodiniz.local`.
    """

    class Perfil(models.TextChoices):
        ADMIN = "admin", "Admin"
        DIRETOR = "diretor", "Diretor"
        PROFESSOR = "professor", "Professor"
        SECRETARIA = "secretaria", "Secretaria"
        COORDENADOR = "coordenador", "Coordenador"
        INSPETOR = "inspetor", "Inspetor"

    email = models.EmailField("email address", blank=False)

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


# Janela de validade do token de redefinição. 1h é o suficiente pra o
# usuário abrir o email e clicar no link sem deixar a janela aberta tempo
# demais caso o email seja interceptado depois.
RESET_TOKEN_LIFETIME = timedelta(hours=1)


class PasswordResetToken(models.Model):
    """Token de uso único pra redefinição de senha.

    Só o hash SHA-256 do token é guardado — vazamento do banco não revela
    tokens utilizáveis. O token cru circula apenas no link enviado por
    email; o backend verifica recalculando o hash.
    """

    usuario = models.ForeignKey(
        Usuario, on_delete=models.CASCADE, related_name="reset_tokens"
    )
    token_hash = models.CharField(max_length=64, unique=True, db_index=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    expira_em = models.DateTimeField()
    usado_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "token de redefinição de senha"
        verbose_name_plural = "tokens de redefinição de senha"
        indexes = [models.Index(fields=["usuario", "usado_em"])]

    def __str__(self) -> str:
        return f"reset(user={self.usuario_id}, expira={self.expira_em.isoformat()})"

    @classmethod
    def gerar(cls, usuario: Usuario) -> tuple["PasswordResetToken", str]:
        """Cria um token novo. Retorna (instance, token_cru).

        O `token_cru` só é retornado aqui — é o que vai no email. A partir
        desse momento, só fica o hash no banco.
        """
        token_cru = secrets.token_urlsafe(48)
        token_hash = cls._hash(token_cru)
        instance = cls.objects.create(
            usuario=usuario,
            token_hash=token_hash,
            expira_em=timezone.now() + RESET_TOKEN_LIFETIME,
        )
        return instance, token_cru

    @classmethod
    def buscar_valido(cls, token_cru: str) -> "PasswordResetToken | None":
        """Devolve o token correspondente se ainda for válido; senão None."""
        try:
            obj = cls.objects.select_related("usuario").get(
                token_hash=cls._hash(token_cru)
            )
        except cls.DoesNotExist:
            return None
        if obj.usado_em is not None:
            return None
        if obj.expira_em <= timezone.now():
            return None
        return obj

    def marcar_usado(self) -> None:
        self.usado_em = timezone.now()
        self.save(update_fields=["usado_em"])

    @staticmethod
    def _hash(token_cru: str) -> str:
        return hashlib.sha256(token_cru.encode("utf-8")).hexdigest()
