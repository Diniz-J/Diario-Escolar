"""Modelos da app presenca.

Dois modelos relacionados:

- `RegistroPresenca` — chamada de uma turma num dia específico, única por
  `(escola, turma, data)`. Quem registra (`professor`) é opcional, porque
  admin/diretor também podem abrir a chamada.
- `ItemPresenca` — status individual de cada aluno dentro de um registro.
  Único por `(registro, aluno)`. Status: P (presente, default), A (ausente),
  J (justificado), R (retardatário).

Quando um `RegistroPresenca` é criado pela API, a view dispara a criação
automática de um `ItemPresenca` (status=P) para cada aluno ativo da turma.

Invariantes em `clean()` (espelhadas no serializer):

- `RegistroPresenca`: `turma.escola == escola`, `data <= hoje`,
  `professor.escola == escola` (se fornecido).
- `ItemPresenca`: `aluno.turma == registro.turma`,
  `aluno.escola == registro.escola`. O campo `escola` do item é
  sincronizado com `registro.escola` no `save()` — nunca aceita payload
  manipulado.
"""
from datetime import date

from django.core.exceptions import ValidationError
from django.db import models
from simple_history.models import HistoricalRecords

from apps.common.models import BaseModelEscopado
from apps.escola.models import Aluno, Escola, Professor, Turma


class RegistroPresenca(BaseModelEscopado):
    """Chamada de uma turma num dia."""

    turma = models.ForeignKey(
        Turma, on_delete=models.PROTECT, related_name="registros_presenca"
    )
    data = models.DateField(default=date.today)
    professor = models.ForeignKey(
        Professor,
        on_delete=models.PROTECT,
        related_name="registros_presenca",
        null=True,
        blank=True,
    )
    observacao = models.TextField(blank=True)

    # Sobrescreve o campo herdado para expor `escola.registros_presenca`.
    escola = models.ForeignKey(
        Escola, on_delete=models.PROTECT, related_name="registros_presenca"
    )

    history = HistoricalRecords()

    class Meta:
        verbose_name = "registro de presença"
        verbose_name_plural = "registros de presença"
        ordering = ["-data"]
        constraints = [
            models.UniqueConstraint(
                fields=["escola", "turma", "data"],
                name="registro_presenca_unique_escola_turma_data",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.turma} — {self.data}"

    def clean(self) -> None:
        """Coerência entre escola, turma, professor e data."""
        super().clean()
        errors: dict[str, str] = {}

        if self.turma_id and self.escola_id and self.turma.escola_id != self.escola_id:
            errors["turma"] = "A turma deve pertencer à mesma escola do registro."

        if self.data and self.data > date.today():
            errors["data"] = "Data do registro não pode estar no futuro."

        if (
            self.professor_id
            and self.escola_id
            and self.professor.escola_id != self.escola_id
        ):
            errors["professor"] = (
                "O professor deve pertencer à mesma escola do registro."
            )

        if errors:
            raise ValidationError(errors)


class ItemPresenca(BaseModelEscopado):
    """Status individual de presença de um aluno em um registro."""

    class Status(models.TextChoices):
        PRESENTE = "P", "Presente"
        AUSENTE = "A", "Ausente"
        JUSTIFICADO = "J", "Justificado"
        RETARDATARIO = "R", "Retardatário"

    registro = models.ForeignKey(
        RegistroPresenca, on_delete=models.CASCADE, related_name="itens"
    )
    aluno = models.ForeignKey(
        Aluno, on_delete=models.PROTECT, related_name="presencas"
    )
    status = models.CharField(
        max_length=1,
        choices=Status.choices,
        default=Status.PRESENTE,
    )
    observacao = models.CharField(max_length=200, blank=True)

    # `escola` é derivada do registro pai — ver `save()` abaixo.
    escola = models.ForeignKey(
        Escola, on_delete=models.PROTECT, related_name="itens_presenca"
    )

    history = HistoricalRecords()

    class Meta:
        verbose_name = "item de presença"
        verbose_name_plural = "itens de presença"
        ordering = ["aluno__nome_completo"]
        constraints = [
            models.UniqueConstraint(
                fields=["registro", "aluno"],
                name="item_presenca_unique_registro_aluno",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.aluno} — {self.get_status_display()}"

    def save(self, *args, **kwargs) -> None:
        """Sincroniza `escola` com `registro.escola` antes de gravar.

        O `EscopoEscolaMixin` filtra leituras por `escola_id` — para que
        funcione consistentemente, `item.escola` precisa refletir
        exatamente a escola do registro pai. Forçar aqui evita qualquer
        possibilidade de divergência por payload manipulado ou erro
        humano.
        """
        if self.registro_id:
            self.escola_id = self.registro.escola_id
        super().save(*args, **kwargs)

    def clean(self) -> None:
        """Coerência entre aluno, registro e suas turmas/escolas."""
        super().clean()
        errors: dict[str, str] = {}

        if self.registro_id and self.aluno_id:
            if self.aluno.turma_id != self.registro.turma_id:
                errors["aluno"] = (
                    "O aluno deve pertencer à turma do registro de presença."
                )
            if self.aluno.escola_id != self.registro.escola_id:
                errors["aluno"] = (
                    "O aluno deve pertencer à mesma escola do registro."
                )

        if errors:
            raise ValidationError(errors)
