"""Mural de materiais — o que o professor publica pra turma e o responsável lê.

Quadro de avisos com link, não sala de aula (`PORTAL.md`, seção 1): sem
entrega de atividade, sem correção, sem upload. Upload exigiria object
storage — o disco do container do Render é efêmero.

Mesmo molde do `RegistroAula` (app `aulas`): professor só publica em
turma+disciplina que leciona (`Lecionamento` ativo), validado no `clean()`
e espelhado no serializer.
"""
from django.core.exceptions import ValidationError
from django.core.validators import URLValidator
from django.db import models
from django.utils import timezone
from simple_history.models import HistoricalRecords

from apps.common.models import BaseModelEscopado
from apps.escola.models import Disciplina, Escola, Lecionamento, Professor, Turma

# Só http/https: o link vira `<a href>` no portal dos pais, e esquema como
# `javascript:` ou `data:` seria vetor de ataque no clique. O padrão do
# `URLField` ainda aceitaria ftp/ftps, que não têm uso aqui.
validar_link = URLValidator(schemes=["http", "https"])


class Material(BaseModelEscopado):
    """Material publicado por um professor pra uma turma, numa disciplina."""

    turma = models.ForeignKey(
        Turma, on_delete=models.PROTECT, related_name="materiais"
    )
    disciplina = models.ForeignKey(
        Disciplina, on_delete=models.PROTECT, related_name="materiais"
    )
    professor = models.ForeignKey(
        Professor, on_delete=models.PROTECT, related_name="materiais"
    )
    titulo = models.CharField(max_length=200)
    descricao = models.TextField(blank=True)
    link = models.URLField(max_length=500, blank=True, validators=[validar_link])
    publicado_em = models.DateTimeField(default=timezone.now)
    # Soft delete: "excluir" desativa. Some do portal, fica no histórico.
    ativo = models.BooleanField(default=True)

    # Sobrescreve o campo herdado para expor `escola.materiais` no reverse.
    escola = models.ForeignKey(
        Escola, on_delete=models.PROTECT, related_name="materiais"
    )

    history = HistoricalRecords()

    class Meta:
        verbose_name = "material"
        verbose_name_plural = "materiais"
        ordering = ["-publicado_em"]
        indexes = [
            # Portal: mural da turma do filho, só ativos, mais recente primeiro.
            models.Index(
                fields=["turma", "ativo", "-publicado_em"],
                name="material_idx_turma_ativo_pub",
            ),
            # Staff: lista do professor.
            models.Index(
                fields=["professor", "-publicado_em"],
                name="material_idx_prof_pub",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.titulo} ({self.turma})"

    def clean(self) -> None:
        """Escola alinhada e lecionamento ativo pro trio."""
        super().clean()
        errors: dict[str, str] = {}

        for campo in ("turma", "disciplina", "professor"):
            if not (getattr(self, f"{campo}_id") and self.escola_id):
                continue
            if getattr(self, campo).escola_id != self.escola_id:
                errors[campo] = f"O campo {campo} deve pertencer à mesma escola do material."

        if self.professor_id and self.turma_id and self.disciplina_id:
            if not leciona(self.professor_id, self.turma_id, self.disciplina_id):
                errors["professor"] = (
                    "Não há lecionamento ativo deste professor para esta "
                    "turma e disciplina."
                )

        if errors:
            raise ValidationError(errors)


def leciona(professor_id, turma_id, disciplina_id) -> bool:
    """True se há `Lecionamento` ativo pro trio — compartilhado com o serializer."""
    return Lecionamento.objects.filter(
        professor_id=professor_id,
        turma_id=turma_id,
        disciplina_id=disciplina_id,
        ativo=True,
    ).exists()
