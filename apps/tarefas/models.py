"""Modelos da app tarefas.

Dois modelos relacionados:

- `Tarefa` — atividade lançada por um professor para uma turma+disciplina.
  Pode ter prazo (opcional) e pode valer nota (opcional). Quando vale
  nota, `nota_maxima` define o teto.
- `EntregaTarefa` — registro individual por aluno (uma por aluno por
  tarefa). Auto-gerada pela view `perform_create` quando a tarefa é
  criada, espelhando o padrão de `presenca`.

Status individual da entrega (pendente / atrasada / entregue no prazo /
entregue com atraso) é calculado no serializer a partir de `entregue`,
`data_entrega` e `Tarefa.prazo`. Não é armazenado.
"""
from datetime import date

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models

from apps.common.models import BaseModelEscopado
from apps.escola.models import Aluno, Disciplina, Escola, Professor, Turma


class Tarefa(BaseModelEscopado):
    """Atividade lançada por um professor para uma turma+disciplina."""

    turma = models.ForeignKey(
        Turma, on_delete=models.PROTECT, related_name="tarefas"
    )
    disciplina = models.ForeignKey(
        Disciplina, on_delete=models.PROTECT, related_name="tarefas"
    )
    professor = models.ForeignKey(
        Professor,
        on_delete=models.PROTECT,
        related_name="tarefas",
        null=True,
        blank=True,
    )
    titulo = models.CharField(max_length=200)
    descricao = models.TextField(blank=True)
    data_lancamento = models.DateField(default=date.today)
    prazo = models.DateField(null=True, blank=True)
    vale_nota = models.BooleanField(default=False)
    nota_maxima = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
    )
    # Usado pra média ponderada quando o boletim entrar — fora de escopo
    # nesta etapa, mas o campo já fica disponível.
    peso = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        default=1,
        validators=[MinValueValidator(0)],
    )

    # Sobrescreve pra expor `escola.tarefas` no reverse.
    escola = models.ForeignKey(
        Escola, on_delete=models.PROTECT, related_name="tarefas"
    )

    class Meta:
        verbose_name = "tarefa"
        verbose_name_plural = "tarefas"
        ordering = ["-data_lancamento", "-criado_em"]

    def __str__(self) -> str:
        return f"{self.titulo} ({self.turma} · {self.disciplina})"

    def clean(self) -> None:
        super().clean()
        errors: dict[str, str] = {}

        if (
            self.turma_id
            and self.escola_id
            and self.turma.escola_id != self.escola_id
        ):
            errors["turma"] = "A turma deve pertencer à mesma escola da tarefa."

        if (
            self.disciplina_id
            and self.escola_id
            and self.disciplina.escola_id != self.escola_id
        ):
            errors["disciplina"] = (
                "A disciplina deve pertencer à mesma escola da tarefa."
            )

        if (
            self.professor_id
            and self.escola_id
            and self.professor.escola_id != self.escola_id
        ):
            errors["professor"] = (
                "O professor deve pertencer à mesma escola da tarefa."
            )

        if (
            self.prazo
            and self.data_lancamento
            and self.prazo < self.data_lancamento
        ):
            errors["prazo"] = (
                "O prazo não pode ser anterior à data de lançamento."
            )

        if self.vale_nota and (
            self.nota_maxima is None or self.nota_maxima <= 0
        ):
            errors["nota_maxima"] = (
                "Tarefa que vale nota precisa de nota máxima maior que zero."
            )

        if not self.vale_nota and self.nota_maxima is not None:
            # Mantém o campo coerente — se não vale nota, o teto fica null.
            # Não erramos: apenas anulamos no `save()` se quiser ser
            # estrito. Aqui não bloqueamos pra evitar atrito no PATCH.
            pass

        if errors:
            raise ValidationError(errors)


class EntregaTarefa(BaseModelEscopado):
    """Status de entrega de uma tarefa por um aluno específico."""

    tarefa = models.ForeignKey(
        Tarefa, on_delete=models.CASCADE, related_name="entregas"
    )
    aluno = models.ForeignKey(
        Aluno, on_delete=models.PROTECT, related_name="entregas_tarefas"
    )
    entregue = models.BooleanField(default=False)
    data_entrega = models.DateField(null=True, blank=True)
    nota = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
    )
    observacao = models.CharField(max_length=200, blank=True)

    # Derivada de `tarefa.escola` — sincronizada no save().
    escola = models.ForeignKey(
        Escola, on_delete=models.PROTECT, related_name="entregas_tarefas"
    )

    class Meta:
        verbose_name = "entrega de tarefa"
        verbose_name_plural = "entregas de tarefa"
        ordering = ["aluno__nome_completo"]
        constraints = [
            models.UniqueConstraint(
                fields=["tarefa", "aluno"],
                name="entrega_unique_tarefa_aluno",
            ),
        ]

    def __str__(self) -> str:
        marca = "entregue" if self.entregue else "pendente"
        return f"{self.aluno} — {marca}"

    def save(self, *args, **kwargs) -> None:
        """Sincroniza `escola` com `tarefa.escola` antes de gravar.

        Mantém coerência com `EscopoEscolaMixin` (que filtra por
        `escola_id`) sem confiar no payload.
        """
        if self.tarefa_id:
            self.escola_id = self.tarefa.escola_id
        super().save(*args, **kwargs)

    def clean(self) -> None:
        super().clean()
        errors: dict[str, str] = {}

        if self.tarefa_id and self.aluno_id:
            if self.aluno.turma_id != self.tarefa.turma_id:
                errors["aluno"] = (
                    "O aluno deve pertencer à turma da tarefa."
                )
            if self.aluno.escola_id != self.tarefa.escola_id:
                errors["aluno"] = (
                    "O aluno deve pertencer à mesma escola da tarefa."
                )

        if self.nota is not None and self.tarefa_id:
            if not self.tarefa.vale_nota:
                errors["nota"] = (
                    "Esta tarefa não vale nota; o campo deve ficar vazio."
                )
            elif (
                self.tarefa.nota_maxima is not None
                and self.nota > self.tarefa.nota_maxima
            ):
                errors["nota"] = (
                    f"A nota não pode ser maior que {self.tarefa.nota_maxima}."
                )

        if errors:
            raise ValidationError(errors)

    @property
    def status(self) -> str:
        """Computa status legível a partir de `entregue`/`data_entrega`/prazo.

        Retorna uma das chaves:
        - `pendente`: não entregue, dentro do prazo ou sem prazo.
        - `atrasada`: não entregue, prazo vencido.
        - `entregue_no_prazo`: entregue dentro do prazo (ou sem prazo).
        - `entregue_com_atraso`: entregue após o prazo.
        """
        prazo = self.tarefa.prazo if self.tarefa_id else None
        hoje = date.today()

        if not self.entregue:
            if prazo and prazo < hoje:
                return "atrasada"
            return "pendente"

        if prazo and self.data_entrega and self.data_entrega > prazo:
            return "entregue_com_atraso"
        return "entregue_no_prazo"
