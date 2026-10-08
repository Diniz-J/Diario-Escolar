"""Modelos do portal do responsável — identidade externa e vínculo com aluno.

Ver `PORTAL.md` na raiz do repo pro desenho completo. O essencial aqui:

`Responsavel` é a identidade de um usuário **externo** à escola. Não é um
perfil novo em `Usuario`: usuário externo não encosta na superfície do
staff, onde todas as permission classes têm bypass de admin. Um furo de
permissão lá não pode passar a vazar pra fora da escola.

Herda `AbstractBaseUser` só pelo que ele dá de graça — `password`,
`set_password`/`check_password` e `last_login` — mas **não** é o
`AUTH_USER_MODEL` do projeto, que continua sendo `accounts.Usuario`
(Django admite um só). Como consequência, o `is_active` que vem da base
(atributo fixo `True`, não campo) é irrelevante: nada aqui passa pelos
backends de autenticação do Django. Quem diz se a conta vale é o campo
`ativo`, seguindo a convenção do projeto (`Aluno.ativo`,
`Professor.ativo`).

`ResponsavelAluno` é o vínculo. Sendo M2M, resolve de quebra o "múltiplos
responsáveis por aluno" que já estava listado como pendência. É o modelo
que decide quem pode ver os dados de qual aluno, então é **auditado**.

Esta fatia não expõe endpoint nenhum — é só schema, admin e semeadura. O
login externo entra na fatia 2.
"""
import hashlib
import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.base_user import AbstractBaseUser
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from simple_history.models import HistoricalRecords

from apps.common.models import BaseModelEscopado, TimeStampedModel
from apps.common.texto import normalizar_email
from apps.escola.models import Aluno, Escola


class Responsavel(AbstractBaseUser, BaseModelEscopado):
    """Responsável por um ou mais alunos. Identidade de acesso ao portal."""

    # `AbstractBaseUser` exige saber qual campo identifica a conta.
    USERNAME_FIELD = "email"
    EMAIL_FIELD = "email"

    # Email é a âncora da identidade: é por ele que o convite é enviado e
    # é com ele que o responsável loga. Obrigatório por isso — ver a regra
    # de semeadura em `portal_semear_responsaveis`.
    email = models.EmailField()
    nome = models.CharField(max_length=200)
    # Indexado: a listagem do portal e os envios filtram por conta ativa.
    ativo = models.BooleanField(default=True, db_index=True)
    # Opt-out de email, separado de `ativo` de propósito: o pai que pede
    # pra não receber aviso continua querendo consultar o boletim. Juntar
    # os dois tiraria o acesso de quem só pediu silêncio.
    #
    # Mora aqui, e não no vínculo, porque "não quero receber email" é da
    # pessoa, não da relação com cada filho — ninguém pediu granularidade
    # por filho, e ela multiplicaria a UI sem caso de uso.
    recebe_notificacao = models.BooleanField(default=True)

    # Sobrescreve o campo herdado para expor `escola.responsaveis` no reverse.
    escola = models.ForeignKey(
        Escola, on_delete=models.PROTECT, related_name="responsaveis"
    )
    alunos = models.ManyToManyField(
        Aluno, through="ResponsavelAluno", related_name="responsaveis"
    )

    # `last_login` fica fora pelo mesmo motivo do `Usuario`: geraria uma
    # entrada por login, afogando as mudanças que importam.
    #
    # `password` também fica fora, e aqui **divergindo** do `Usuario` de
    # propósito. No staff o hash no histórico tem valor de auditoria; aqui
    # é usuário externo, e guardar todo hash já usado numa tabela que
    # ninguém expira deixa um rastro permanente de credencial de terceiro
    # — sem contrapartida, porque hash antigo não serve pra investigar
    # nada (não loga mais). Se um dia for preciso saber *quando* a senha
    # mudou, o lugar é um campo de data, não o histórico do hash.
    history = HistoricalRecords(excluded_fields=["last_login", "password"])

    class Meta:
        verbose_name = "responsável"
        verbose_name_plural = "responsáveis"
        ordering = ["nome"]
        constraints = [
            models.UniqueConstraint(
                fields=["escola", "email"],
                name="responsavel_unique_escola_email",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.nome} <{self.email}>"

    def save(self, *args, **kwargs):
        """Normaliza o email antes de gravar.

        Feito aqui, e não só no serializer, porque o unique constraint não
        tem como normalizar: admin, shell e management command também
        precisam cair na mesma regra. Mesmo princípio do
        `ItemPresenca.save()`, que força a escola do registro pai.
        """
        self.email = normalizar_email(self.email)
        # Conta criada sem senha (ex.: pelo admin, onde o campo é só
        # leitura) ficaria com `""` — que o Django considera senha
        # *utilizável*. O convite recusaria ("já ativou"), o lote pularia e
        # o login nunca passaria: conta presa. Marca como sem senha.
        if not self.password:
            self.set_unusable_password()
        super().save(*args, **kwargs)


class ResponsavelAluno(TimeStampedModel):
    """Vínculo responsável × aluno — quem pode ver os dados de quem.

    `PROTECT` nos dois lados: é dado de tenant e o projeto prefere soft
    delete onde há histórico. Desvincular é ação explícita (apagar a
    linha), não efeito colateral de desativar uma conta.

    Não herda `BaseModelEscopado`: a escola vem por `responsavel.escola` e
    `aluno.escola`, que `clean()` obriga a coincidir. Uma terceira cópia
    da FK abriria espaço pra divergência.
    """

    responsavel = models.ForeignKey(
        Responsavel, on_delete=models.PROTECT, related_name="vinculos"
    )
    aluno = models.ForeignKey(
        Aluno, on_delete=models.PROTECT, related_name="vinculos_responsavel"
    )

    history = HistoricalRecords()

    class Meta:
        verbose_name = "vínculo responsável/aluno"
        verbose_name_plural = "vínculos responsável/aluno"
        ordering = ["aluno__nome_completo"]
        constraints = [
            models.UniqueConstraint(
                fields=["responsavel", "aluno"],
                name="responsavelaluno_unique_responsavel_aluno",
            ),
        ]
        # Sem `indexes` de propósito: toda leitura do portal parte do
        # responsável autenticado, e o índice do `UniqueConstraint` acima
        # — btree em (responsavel, aluno) — já atende filtro só por
        # `responsavel`, que é seu prefixo mais à esquerda. Um índice
        # dedicado seria custo de escrita e espaço sem ganho de leitura.

    def __str__(self) -> str:
        return f"{self.responsavel.nome} → {self.aluno.nome_completo}"

    def clean(self) -> None:
        """Responsável e aluno têm que ser da mesma escola.

        Sem isto, um vínculo cruzado daria a um responsável acesso a dados
        de outra escola — o escopo por queryset do portal parte justamente
        deste vínculo, então aqui é a última linha de defesa.
        """
        super().clean()
        if self.responsavel_id and self.aluno_id:
            if self.responsavel.escola_id != self.aluno.escola_id:
                raise ValidationError(
                    {
                        "aluno": (
                            "O aluno deve pertencer à mesma escola do "
                            "responsável."
                        )
                    }
                )


class ConviteResponsavel(TimeStampedModel):
    """Link de uso único pra o responsável definir a senha.

    Duas finalidades com o mesmo fluxo (link com token → definir senha):

    - **convite**: primeira ativação, disparado pela escola. Vale 7 dias —
      o pai pode só abrir o email no fim de semana.
    - **redefinição**: "esqueci a senha", pedido pelo próprio responsável.
      Vale 1 hora, igual ao `PasswordResetToken` do staff.

    Mesmo molde do `PasswordResetToken`: só o hash SHA-256 fica no banco;
    o token cru circula apenas no link do email.

    Emitir um link novo invalida os pendentes do mesmo responsável (expira
    na hora, sem marcar como usado — `usado_em` continua significando "a
    senha foi definida por este link"). Só o último link enviado funciona.
    """

    class Finalidade(models.TextChoices):
        CONVITE = "convite", "Convite"
        REDEFINICAO = "redefinicao", "Redefinição de senha"

    VALIDADE = {
        Finalidade.CONVITE: timedelta(days=7),
        Finalidade.REDEFINICAO: timedelta(hours=1),
    }

    responsavel = models.ForeignKey(
        Responsavel, on_delete=models.PROTECT, related_name="convites"
    )
    finalidade = models.CharField(max_length=20, choices=Finalidade.choices)
    token_hash = models.CharField(max_length=64, unique=True)
    expira_em = models.DateTimeField()
    usado_em = models.DateTimeField(null=True, blank=True)
    # Quem da escola disparou o convite. Nulo na redefinição (pedida pelo
    # próprio responsável) e no comando de lote.
    #
    # `SET_NULL`, não `PROTECT`: é campo de auditoria, não FK de tenant.
    # Com `PROTECT`, apagar a secretaria que mandou um convite levantaria
    # `ProtectedError` no `DELETE /usuarios/<id>/` — que vira 500.
    enviado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="convites_responsavel",
        null=True,
        blank=True,
    )

    class Meta:
        verbose_name = "convite de responsável"
        verbose_name_plural = "convites de responsável"
        ordering = ["-criado_em"]
        # O comando de lote e a invalidação filtram os pendentes por
        # responsável.
        indexes = [models.Index(fields=["responsavel", "usado_em"])]

    def __str__(self) -> str:
        return f"{self.get_finalidade_display()} → {self.responsavel.email}"

    @classmethod
    def gerar(cls, responsavel, finalidade, enviado_por=None):
        """Cria o link e invalida os pendentes. Retorna (instance, token_cru)."""
        agora = timezone.now()
        cls.pendentes(responsavel).update(expira_em=agora)
        token_cru = secrets.token_urlsafe(48)
        instance = cls.objects.create(
            responsavel=responsavel,
            finalidade=finalidade,
            token_hash=cls._hash(token_cru),
            expira_em=agora + cls.VALIDADE[finalidade],
            enviado_por=enviado_por,
        )
        return instance, token_cru

    @classmethod
    def pendentes(cls, responsavel):
        """Links ainda utilizáveis do responsável."""
        return cls.objects.filter(
            responsavel=responsavel,
            usado_em__isnull=True,
            expira_em__gt=timezone.now(),
        )

    @classmethod
    def buscar_valido(cls, token_cru: str):
        """Devolve o link se ainda for utilizável; senão None."""
        try:
            obj = cls.objects.select_related("responsavel").get(
                token_hash=cls._hash(token_cru)
            )
        except cls.DoesNotExist:
            return None
        if obj.usado_em is not None or obj.expira_em <= timezone.now():
            return None
        if not obj.responsavel.ativo:
            return None
        return obj

    def invalidar(self) -> None:
        """Expira o link sem marcar como usado (ex.: o email não saiu)."""
        self.expira_em = timezone.now()
        self.save(update_fields=["expira_em", "atualizado_em"])

    @staticmethod
    def _hash(token_cru: str) -> str:
        return hashlib.sha256(token_cru.encode("utf-8")).hexdigest()
