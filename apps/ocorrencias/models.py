"""Modelos da app ocorrencias.

Uma `Ocorrencia` registra um evento envolvendo um aluno em uma turma — pode
ser disciplinar, pedagógica, comportamental, etc. O `professor` que registra
é opcional porque admin/diretor também podem abrir ocorrências sem ter um
objeto `Professor` vinculado.

Invariantes garantidas em `clean()` (e espelhadas no serializer):
- `aluno.escola == self.escola`
- `aluno.turma == self.turma` (a turma da ocorrência é a turma atual do aluno)
- `professor.escola == self.escola` quando `professor` é fornecido
- `data_ocorrencia <= hoje` (não aceita data futura)
"""
from datetime import date

from django.core.exceptions import ValidationError
from django.db import models
from simple_history.models import HistoricalRecords

from apps.common.models import BaseModelEscopado
from apps.escola.models import Aluno, Escola, Professor, Turma


class Ocorrencia(BaseModelEscopado):
    """Registro de uma ocorrência escolar envolvendo um aluno."""

    class Status(models.TextChoices):
        ABERTA = "aberta", "Aberta"
        EM_ANDAMENTO = "em_andamento", "Em andamento"
        RESOLVIDA = "resolvida", "Resolvida"
        ARQUIVADA = "arquivada", "Arquivada"

    turma = models.ForeignKey(
        Turma, on_delete=models.PROTECT, related_name="ocorrencias"
    )
    aluno = models.ForeignKey(
        Aluno, on_delete=models.PROTECT, related_name="ocorrencias"
    )
    professor = models.ForeignKey(
        Professor,
        on_delete=models.PROTECT,
        related_name="ocorrencias",
        null=True,
        blank=True,
    )
    descricao = models.TextField()
    # Indexado: aparece em filtros de range (`?data_inicio=&data_fim=`) e
    # no ordering default (-data_ocorrencia).
    data_ocorrencia = models.DateField(default=date.today, db_index=True)
    # Indexado: filtro recorrente no dashboard e listagens
    # (`?status=aberta`, `?status=em_andamento`).
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ABERTA,
        db_index=True,
    )

    # Sobrescreve o campo herdado para expor `escola.ocorrencias` no reverse.
    escola = models.ForeignKey(
        Escola, on_delete=models.PROTECT, related_name="ocorrencias"
    )

    history = HistoricalRecords()

    class Meta:
        verbose_name = "ocorrência"
        verbose_name_plural = "ocorrências"
        ordering = ["-data_ocorrencia", "-criado_em"]

    def __str__(self) -> str:
        return f"{self.aluno} — {self.get_status_display()} ({self.data_ocorrencia})"

    def clean(self) -> None:
        """Garante coerência entre escola, turma, aluno, professor e data."""
        super().clean()
        errors: dict[str, str] = {}

        if self.aluno_id and self.escola_id and self.aluno.escola_id != self.escola_id:
            errors["aluno"] = "O aluno deve pertencer à mesma escola da ocorrência."

        if self.turma_id and self.aluno_id and self.aluno.turma_id != self.turma_id:
            errors["turma"] = "A turma da ocorrência deve ser a turma atual do aluno."

        if (
            self.professor_id
            and self.escola_id
            and self.professor.escola_id != self.escola_id
        ):
            errors["professor"] = (
                "O professor deve pertencer à mesma escola da ocorrência."
            )

        if self.data_ocorrencia and self.data_ocorrencia > date.today():
            errors["data_ocorrencia"] = "Data da ocorrência não pode estar no futuro."

        if errors:
            raise ValidationError(errors)
