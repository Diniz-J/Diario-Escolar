"""Modelos da app planos_ensino.

`PlanoEnsino` é o documento programático de uma disciplina pra uma
turma num ano letivo: ementa, conteúdo programático, objetivos,
habilidades BNCC, metodologia, recursos, avaliação. Único por
`(escola, turma, disciplina, ano_letivo)` — não faz sentido ter dois
planos pra a mesma turma+disciplina no mesmo ano.

Todos os campos textuais começam vazios; o preenchimento fica a cargo
do professor/coordenador (não há seed de conteúdo).
"""
from django.core.exceptions import ValidationError
from django.db import models
from simple_history.models import HistoricalRecords

from apps.common.models import BaseModelEscopado
from apps.escola.models import Disciplina, Escola, Professor, Turma


class PlanoEnsino(BaseModelEscopado):
    """Plano anual de ensino — meta programática de uma disciplina."""

    turma = models.ForeignKey(
        Turma, on_delete=models.PROTECT, related_name="planos_ensino"
    )
    disciplina = models.ForeignKey(
        Disciplina, on_delete=models.PROTECT, related_name="planos_ensino"
    )
    professor = models.ForeignKey(
        Professor,
        on_delete=models.PROTECT,
        related_name="planos_ensino",
        null=True,
        blank=True,
    )
    ano_letivo = models.PositiveIntegerField()

    ementa = models.TextField(blank=True)
    conteudo_programatico = models.TextField(blank=True)
    objetivos_gerais = models.TextField(blank=True)
    objetivos_especificos = models.TextField(blank=True)
    habilidades_bncc = models.TextField(
        blank=True,
        help_text="Códigos da BNCC, um por linha (ex.: EF06MA01).",
    )
    carga_horaria = models.PositiveIntegerField(null=True, blank=True)
    metodologia = models.TextField(blank=True)
    recursos = models.TextField(blank=True)
    avaliacao = models.TextField(blank=True)
    ativo = models.BooleanField(default=True)

    escola = models.ForeignKey(
        Escola, on_delete=models.PROTECT, related_name="planos_ensino"
    )

    history = HistoricalRecords()

    class Meta:
        verbose_name = "plano de ensino"
        verbose_name_plural = "planos de ensino"
        ordering = ["-ano_letivo", "turma__nome", "disciplina__nome"]
        constraints = [
            models.UniqueConstraint(
                fields=["escola", "turma", "disciplina", "ano_letivo"],
                name="plano_ensino_unique_escola_turma_disciplina_ano",
            ),
        ]

    def __str__(self) -> str:
        return (
            f"{self.disciplina} — {self.turma} ({self.ano_letivo})"
        )

    def clean(self) -> None:
        """Garante coerência entre escola, turma, disciplina e professor."""
        super().clean()
        errors: dict[str, str] = {}

        if (
            self.turma_id
            and self.escola_id
            and self.turma.escola_id != self.escola_id
        ):
            errors["turma"] = "A turma deve pertencer à mesma escola do plano."

        if (
            self.disciplina_id
            and self.escola_id
            and self.disciplina.escola_id != self.escola_id
        ):
            errors["disciplina"] = (
                "A disciplina deve pertencer à mesma escola do plano."
            )

        if (
            self.professor_id
            and self.escola_id
            and self.professor.escola_id != self.escola_id
        ):
            errors["professor"] = (
                "O professor deve pertencer à mesma escola do plano."
            )

        if (
            self.turma_id
            and self.ano_letivo
            and self.turma.ano_letivo != self.ano_letivo
        ):
            errors["ano_letivo"] = (
                "O ano letivo do plano deve coincidir com o da turma."
            )

        if errors:
            raise ValidationError(errors)
