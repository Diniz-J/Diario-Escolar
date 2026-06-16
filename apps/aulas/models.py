"""Modelos da app aulas — diário de classe (conteúdo ministrado por aula).

`RegistroAula` é o registro do conteúdo programático efetivamente dado
numa aula de uma turma+disciplina num dia, lançado pelo professor. É o
quarto conceito ao lado de `PlanoEnsino` (o planejado no ano), `Tarefa`
(atividade do aluno) e `RegistroPresenca` (quem veio) — nenhum deles
cobre "o que foi dado na aula do dia X".

Fluxo de status (3 estados):
- `rascunho` — professor está escrevendo, ainda não entregou.
- `lancado` — professor entregou o conteúdo; aguarda visto da direção.
- `conferido` — direção conferiu (grava `conferido_por`/`conferido_em`).

A transição pra `conferido` é exclusiva da direção, feita pela action
`conferir` da view — nunca pelo serializer.

Invariantes em `clean()` (espelhadas no serializer):
- `turma`/`disciplina`/`professor` na mesma escola do registro;
- existe `Lecionamento` ativo do trio professor×turma×disciplina;
- `data` não pode estar no futuro;
- `conteudo` obrigatório quando o status sai de `rascunho`.
"""
from datetime import date

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from simple_history.models import HistoricalRecords

from apps.common.models import BaseModelEscopado
from apps.escola.models import Disciplina, Escola, Lecionamento, Professor, Turma


class RegistroAula(BaseModelEscopado):
    """Conteúdo programático ministrado numa aula (turma×disciplina×dia)."""

    class Status(models.TextChoices):
        RASCUNHO = "rascunho", "Rascunho"
        LANCADO = "lancado", "Lançado"
        CONFERIDO = "conferido", "Conferido"

    turma = models.ForeignKey(
        Turma, on_delete=models.PROTECT, related_name="registros_aula"
    )
    disciplina = models.ForeignKey(
        Disciplina, on_delete=models.PROTECT, related_name="registros_aula"
    )
    professor = models.ForeignKey(
        Professor, on_delete=models.PROTECT, related_name="registros_aula"
    )
    # Indexado: filtro de período (`?data_inicio=&data_fim=`) e ordering
    # default (-data) na ficha do professor.
    data = models.DateField(db_index=True)
    # Texto livre — pode ficar vazio em rascunho; obrigatório ao lançar.
    conteudo = models.TextField(blank=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.RASCUNHO,
    )
    # Quem da direção deu o visto + quando. Preenchidos pela action
    # `conferir`; PROTECT pra não perder a autoria do visto no histórico.
    conferido_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="aulas_conferidas",
        null=True,
        blank=True,
    )
    conferido_em = models.DateTimeField(null=True, blank=True)

    escola = models.ForeignKey(
        Escola, on_delete=models.PROTECT, related_name="registros_aula"
    )

    history = HistoricalRecords()

    class Meta:
        verbose_name = "registro de aula"
        verbose_name_plural = "registros de aula"
        ordering = ["-data"]
        constraints = [
            models.UniqueConstraint(
                fields=["escola", "turma", "disciplina", "data"],
                name="registro_aula_unique_escola_turma_disc_data",
            ),
        ]
        indexes = [
            # Ficha do professor: lista cronológica (professor, -data).
            models.Index(
                fields=["professor", "data"],
                name="aula_idx_prof_data",
            ),
            # Dashboard: "X aulas aguardando conferência" por escola.
            models.Index(
                fields=["escola", "status"],
                name="aula_idx_escola_status",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.disciplina} — {self.turma} ({self.data})"

    def clean(self) -> None:
        """Coerência de escola, vínculo de lecionamento, data e conteúdo."""
        super().clean()
        errors: dict[str, str] = {}

        if self.turma_id and self.escola_id and self.turma.escola_id != self.escola_id:
            errors["turma"] = "A turma deve pertencer à mesma escola do registro."

        if (
            self.disciplina_id
            and self.escola_id
            and self.disciplina.escola_id != self.escola_id
        ):
            errors["disciplina"] = (
                "A disciplina deve pertencer à mesma escola do registro."
            )

        if (
            self.professor_id
            and self.escola_id
            and self.professor.escola_id != self.escola_id
        ):
            errors["professor"] = (
                "O professor deve pertencer à mesma escola do registro."
            )

        # Exige vínculo: o professor só registra aula de turma+disciplina
        # que ele efetivamente leciona.
        if self.professor_id and self.turma_id and self.disciplina_id:
            existe_vinculo = Lecionamento.objects.filter(
                professor_id=self.professor_id,
                turma_id=self.turma_id,
                disciplina_id=self.disciplina_id,
                ativo=True,
            ).exists()
            if not existe_vinculo:
                errors["professor"] = (
                    "Não há lecionamento ativo deste professor para esta "
                    "turma e disciplina."
                )

        if self.data and self.data > date.today():
            errors["data"] = "A data da aula não pode estar no futuro."

        # Conteúdo é obrigatório a partir do momento em que a aula é
        # lançada (rascunho pode ficar vazio enquanto o professor escreve).
        if self.status != self.Status.RASCUNHO and not (self.conteudo or "").strip():
            errors["conteudo"] = "Informe o conteúdo da aula antes de lançar."

        if errors:
            raise ValidationError(errors)
