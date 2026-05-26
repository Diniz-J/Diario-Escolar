"""Modelos da app escola — domínio principal do sistema."""
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from apps.common.models import BaseModelEscopado, TimeStampedModel
from apps.common.validators import validar_cnpj


class Escola(TimeStampedModel):
    """Instituição de ensino — raiz do escopo de domínio (tenant root)."""

    nome = models.CharField(max_length=200)
    cnpj = models.CharField(
        max_length=18,
        blank=True,
        null=True,
        unique=True,
        validators=[validar_cnpj],
    )
    ativa = models.BooleanField(default=True)

    class Meta:
        verbose_name = "escola"
        verbose_name_plural = "escolas"
        ordering = ["nome"]

    def __str__(self) -> str:
        return self.nome


class Turma(BaseModelEscopado):
    """Turma escolar dentro de um ano letivo (ex.: '1º Ano A' em 2026)."""

    class Turno(models.TextChoices):
        MATUTINO = "matutino", "Matutino"
        VESPERTINO = "vespertino", "Vespertino"
        NOTURNO = "noturno", "Noturno"
        INTEGRAL = "integral", "Integral"

    nome = models.CharField(max_length=50)
    turno = models.CharField(max_length=20, choices=Turno.choices)
    ano_letivo = models.PositiveIntegerField()
    ativa = models.BooleanField(default=True)

    # Sobrescreve o campo herdado para expor `escola.turmas` no reverse.
    escola = models.ForeignKey(
        Escola, on_delete=models.PROTECT, related_name="turmas"
    )

    class Meta:
        verbose_name = "turma"
        verbose_name_plural = "turmas"
        ordering = ["-ano_letivo", "nome"]
        constraints = [
            models.UniqueConstraint(
                fields=["escola", "nome", "ano_letivo"],
                name="turma_unique_escola_nome_ano",
            ),
        ]

    def __str__(self) -> str:
        # Inclui escola para diferenciar turmas homônimas no admin/dropdowns.
        return f"{self.nome} ({self.get_turno_display()}, {self.ano_letivo}) — {self.escola}"


class Disciplina(BaseModelEscopado):
    """Matéria oferecida pela escola (Matemática, Português etc.)."""

    nome = models.CharField(max_length=100)
    ativa = models.BooleanField(default=True)

    escola = models.ForeignKey(
        Escola, on_delete=models.PROTECT, related_name="disciplinas"
    )

    class Meta:
        verbose_name = "disciplina"
        verbose_name_plural = "disciplinas"
        ordering = ["nome"]
        constraints = [
            models.UniqueConstraint(
                fields=["escola", "nome"],
                name="disciplina_unique_escola_nome",
            ),
        ]

    def __str__(self) -> str:
        return self.nome


class Aluno(BaseModelEscopado):
    """Aluno matriculado na escola.

    Não loga no sistema — é referenciado pelos professores ao registrar
    presença e ocorrências. A `matricula` é única por escola (não global)
    para acomodar o futuro modelo SaaS sem colisões entre instituições.

    `escola` e `turma.escola` precisam coincidir; a invariante é validada
    em `clean()` para erros consistentes via Admin/`full_clean`/serializer.
    """

    matricula = models.CharField(max_length=30)
    nome_completo = models.CharField(max_length=200)
    data_nascimento = models.DateField(null=True, blank=True)
    turma = models.ForeignKey(
        Turma, on_delete=models.PROTECT, related_name="alunos"
    )
    ativo = models.BooleanField(default=True)

    escola = models.ForeignKey(
        Escola, on_delete=models.PROTECT, related_name="alunos"
    )

    class Meta:
        verbose_name = "aluno"
        verbose_name_plural = "alunos"
        ordering = ["nome_completo"]
        constraints = [
            models.UniqueConstraint(
                fields=["escola", "matricula"],
                name="aluno_unique_escola_matricula",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.nome_completo} ({self.matricula})"

    def clean(self) -> None:
        """Garante que turma e aluno pertencem à mesma escola."""
        super().clean()
        if self.turma_id and self.escola_id and self.turma.escola_id != self.escola_id:
            raise ValidationError(
                {"turma": "A turma deve pertencer à mesma escola do aluno."}
            )


class Professor(BaseModelEscopado):
    """Professor da escola — perfil docente vinculado a um `Usuario`.

    O `usuario` é a fonte de identidade (login, nome, email). Este modelo
    apenas materializa o professor dentro da escola — a granularidade de
    "qual disciplina ele leciona em qual turma" mora no modelo
    `Lecionamento`, que cruza professor × turma × disciplina.

    A invariante `usuario.escola == self.escola` é validada em `clean()`
    para impedir vincular um docente de outra escola por engano.
    """

    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="professor",
        limit_choices_to={"perfil": "professor"},
    )
    ativo = models.BooleanField(default=True)

    escola = models.ForeignKey(
        Escola, on_delete=models.PROTECT, related_name="professores"
    )

    class Meta:
        verbose_name = "professor"
        verbose_name_plural = "professores"
        ordering = ["usuario__first_name", "usuario__last_name"]

    def __str__(self) -> str:
        return self.usuario.get_full_name() or self.usuario.username

    def clean(self) -> None:
        """Garante que `usuario.escola` coincide com a escola do professor."""
        super().clean()
        if self.usuario_id and self.escola_id:
            usuario_escola_id = getattr(self.usuario, "escola_id", None)
            if usuario_escola_id and usuario_escola_id != self.escola_id:
                raise ValidationError(
                    {"usuario": "O usuário deve pertencer à mesma escola do professor."}
                )


class Lecionamento(BaseModelEscopado):
    """Vínculo granular: este professor leciona esta disciplina nesta turma.

    Modelo intermediário que substitui a M2M antiga `Professor.disciplinas`.
    Permite responder perguntas mais ricas do diário escolar:

    - Quais turmas o professor X dá aula este ano?
    - Quem leciona Matemática no 1º Ano A?
    - Qual professor lança ocorrências/tarefas para o 2º Ano B?

    `ano_letivo` é derivado da turma (não duplicamos no modelo). `escola`
    vem de `BaseModelEscopado` e precisa coincidir com a escola de
    professor, turma e disciplina — validado em `clean()`.

    Unique por (professor, turma, disciplina): o mesmo trio não se repete.
    Se o professor passar a lecionar a mesma matéria no ano seguinte para
    a mesma turma (raro, pois turmas têm ano_letivo no nome), basta criar
    um lecionamento novo para a turma do novo ano.
    """

    professor = models.ForeignKey(
        Professor, on_delete=models.CASCADE, related_name="lecionamentos"
    )
    turma = models.ForeignKey(
        Turma, on_delete=models.PROTECT, related_name="lecionamentos"
    )
    disciplina = models.ForeignKey(
        Disciplina, on_delete=models.PROTECT, related_name="lecionamentos"
    )
    ativo = models.BooleanField(default=True)

    escola = models.ForeignKey(
        Escola, on_delete=models.PROTECT, related_name="lecionamentos"
    )

    class Meta:
        verbose_name = "lecionamento"
        verbose_name_plural = "lecionamentos"
        ordering = ["turma__ano_letivo", "turma__nome", "disciplina__nome"]
        constraints = [
            models.UniqueConstraint(
                fields=["professor", "turma", "disciplina"],
                name="lecionamento_unique_prof_turma_disc",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.professor} — {self.disciplina} ({self.turma})"

    def clean(self) -> None:
        """Garante alinhamento de escola entre professor, turma e disciplina."""
        super().clean()
        ids = {
            "professor": getattr(self.professor, "escola_id", None),
            "turma": getattr(self.turma, "escola_id", None),
            "disciplina": getattr(self.disciplina, "escola_id", None),
        }
        if self.escola_id:
            for campo, valor in ids.items():
                if valor and valor != self.escola_id:
                    raise ValidationError(
                        {campo: f"O {campo} deve pertencer à mesma escola do lecionamento."}
                    )
