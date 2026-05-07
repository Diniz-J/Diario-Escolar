"""Modelos abstratos compartilhados entre as apps de domínio."""
from django.db import models


class TimeStampedModel(models.Model):
    """Adiciona timestamps de auditoria a qualquer modelo concreto que herde."""

    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class BaseModelEscopado(TimeStampedModel):
    """Base para modelos de domínio que pertencem a uma `Escola`.

    A FK usa string lazy ``"escola.Escola"``: a referência só é resolvida
    quando uma classe concreta herda este modelo. `related_name="+"` desabilita
    o reverse accessor genérico — cada subclasse concreta deve sobrescrever
    o campo `escola` se quiser um reverse acessível em `Escola.<nome>`.
    """

    escola = models.ForeignKey(
        "escola.Escola",
        on_delete=models.PROTECT,
        related_name="+",
    )

    class Meta:
        abstract = True
