"""Modelos da app avaliacao.

Esta app vai concentrar a frente de avaliação/notas do produto. No PR
inicial entra só `PeriodoAvaliativo` — o esqueleto temporal sobre o
qual `Avaliacao`, `NotaAvaliacao` e `NotaPeriodo` vão ser construídos
nos próximos PRs.

Decisão de design: **o sistema NÃO calcula média.** Armazena nota
individual de cada avaliação + média final POR período POR disciplina
(`NotaPeriodo`) que o professor digita manualmente. Frequência é a
ÚNICA agregação automática — é objetiva, sem regra de negócio.
"""
from datetime import date

from django.core.exceptions import ValidationError
from django.db import models
from simple_history.models import HistoricalRecords

from apps.common.models import BaseModelEscopado


class PeriodoAvaliativo(BaseModelEscopado):
    """Bimestre/trimestre/semestre de uma escola num ano letivo.

    Modelado como faixa temporal `[data_inicio, data_fim]` em vez de
    "número do bimestre" pra acomodar trimestre/semestre sem ter que
    refatorar — cada escola configura quantos períodos quiser, com
    nomes e datas próprias.

    Unique por `(escola, nome, ano_letivo)` e por `(escola, ordem,
    ano_letivo)`: não dá pra ter "1º Bimestre" repetido nem dois
    períodos com a mesma ordem no mesmo ano.

    `clean()` impede sobreposição de datas: cadastrar "1º Bim 01/02–30/04"
    e "2º Bim 15/04–30/06" na mesma escola+ano levanta `ValidationError`
    — esses 15 dias de overlap quebrariam a regra de alocação automática
    de Avaliacao por data (cada avaliação pertence a UM período).

    Soft delete via `ativo=False`. Não pode hard delete uma vez que
    `Avaliacao`/`NotaPeriodo` apontarem pra ele (FK `PROTECT`).
    """

    nome = models.CharField(
        max_length=50,
        help_text="Ex.: '1º Bimestre', '2º Trimestre', '1º Semestre'.",
    )
    ordem = models.PositiveSmallIntegerField(
        help_text="Posição sequencial no ano (1, 2, 3...).",
    )
    ano_letivo = models.PositiveIntegerField()
    data_inicio = models.DateField()
    data_fim = models.DateField()
    ativo = models.BooleanField(default=True)

    # Sobrescreve o campo herdado pra expor o reverse `escola.periodos_avaliativos`.
    escola = models.ForeignKey(
        "escola.Escola",
        on_delete=models.PROTECT,
        related_name="periodos_avaliativos",
    )

    history = HistoricalRecords()

    class Meta:
        verbose_name = "período avaliativo"
        verbose_name_plural = "períodos avaliativos"
        ordering = ["-ano_letivo", "ordem"]
        constraints = [
            models.UniqueConstraint(
                fields=["escola", "nome", "ano_letivo"],
                name="periodo_unique_escola_nome_ano",
            ),
            models.UniqueConstraint(
                fields=["escola", "ordem", "ano_letivo"],
                name="periodo_unique_escola_ordem_ano",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.nome} ({self.ano_letivo}) — {self.escola}"

    # ------------------------------------------------------------------ #
    # Estado (vazio / em uso / fechado)                                   #
    # ------------------------------------------------------------------ #

    ESTADO_VAZIO = "vazio"
    ESTADO_EM_USO = "em_uso"
    ESTADO_FECHADO = "fechado"

    @property
    def estado(self) -> str:
        """Computa o estado do período em função dos dependentes.

        Hoje (PR inicial), `Avaliacao` e `NotaPeriodo` ainda não existem,
        então sempre retorna 'vazio'. A property fica preparada pra
        evoluir nos próximos PRs:

        - `em_uso`: existe pelo menos uma `Avaliacao` apontando pra
          este período, mas nenhuma `NotaPeriodo` foi lançada ainda.
        - `fechado`: já tem `NotaPeriodo` consolidada — o boletim do
          período "saiu". Editar datas/ordem fica bloqueado; pra mexer,
          precisa "Reabrir período" (ação explícita do admin/diretor
          com confirmação dupla + audit).
        - `vazio`: caso base; nenhuma avaliação ainda. Edição livre.

        A regra de transição é aplicada na camada de view/serializer
        — o model é só fonte da verdade do estado atual.
        """
        # Placeholder: enquanto Avaliacao/NotaPeriodo não existem, todo
        # período é considerado vazio. Substituir pelos `exists()` reais
        # nos PRs seguintes.
        return self.ESTADO_VAZIO

    # ------------------------------------------------------------------ #
    # Validação                                                          #
    # ------------------------------------------------------------------ #

    def clean(self) -> None:
        """Valida ordenação de datas e ausência de sobreposição.

        Não-sobreposição é a regra crítica: duas faixas se sobrepõem
        quando `inicio_1 <= fim_2 AND inicio_2 <= fim_1`. Verificamos
        no escopo `(escola, ano_letivo)`, excluindo o próprio registro
        em edições.
        """
        super().clean()
        errors: dict[str, str] = {}

        if self.data_inicio and self.data_fim:
            if self.data_inicio >= self.data_fim:
                errors["data_fim"] = (
                    "A data de fim precisa ser posterior à data de início."
                )
            elif self.escola_id and self.ano_letivo:
                # Procura conflito de faixa no mesmo escopo escola+ano.
                conflito_qs = PeriodoAvaliativo.objects.filter(
                    escola_id=self.escola_id,
                    ano_letivo=self.ano_letivo,
                    data_inicio__lte=self.data_fim,
                    data_fim__gte=self.data_inicio,
                )
                if self.pk:
                    conflito_qs = conflito_qs.exclude(pk=self.pk)
                conflito = conflito_qs.first()
                if conflito is not None:
                    errors["data_inicio"] = (
                        f"As datas se sobrepõem ao período "
                        f"'{conflito.nome}' ({conflito.data_inicio} → "
                        f"{conflito.data_fim})."
                    )

        if errors:
            raise ValidationError(errors)

    # ------------------------------------------------------------------ #
    # Helper de domínio                                                   #
    # ------------------------------------------------------------------ #

    def contem(self, data: date) -> bool:
        """Indica se `data` cai dentro deste período (inclusivo)."""
        return self.data_inicio <= data <= self.data_fim
