"""Modelos do financeiro — contas a receber da mensalidade escolar.

Quatro conceitos, nesta ordem de dependência:

- `PlanoCobranca`: o contrato financeiro do aluno (quanto, que dia vence,
  qual desconto, por quanto tempo vale).
- `Fatura`: uma competência (mês) daquele contrato, já com o valor
  congelado. É a linha do contas a receber.
- `FaturaItem`: o detalhamento da fatura (mensalidade, taxa, material).
- `Pagamento`: o dinheiro que entrou, conciliado contra a fatura.

Fronteira do módulo: a emissão de boleto/Pix NÃO é nossa — é de um
gateway brasileiro (Asaas). Aqui fica o contas a receber, e a
conciliação chega por webhook. Por isso a `Fatura` guarda `id_externo`
e `link_pagamento`: são o ponteiro pra cobrança lá e o link que o
responsável abre, nada mais.

Duas decisões que valem pra qualquer mexida futura (ver `FINANCEIRO.md`):

1. **`valor_pago` e `status` da fatura são escritos pelo `services.py`,
   nunca pelo `save()` do `Pagamento`.** Conciliação implícita em
   `save()` quebraria em `bulk_create` e esconderia o momento em que o
   dinheiro muda o estado da fatura — que é exatamente o que precisa
   ficar rastreável.
2. **Multa e juros são método, não campo.** Gravar o encargo
   congelaria um número que muda todo dia; o que é estável é a regra
   (percentuais no plano). Ver `Fatura.encargos()`.
"""
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import (
    MaxValueValidator,
    MinValueValidator,
    URLValidator,
)
from django.db import models
from django.db.models import Q
from simple_history.models import HistoricalRecords

from apps.common.models import BaseModelEscopado, TimeStampedModel
from apps.escola.models import Aluno, Escola

CENTAVO = Decimal("0.01")

# Só http/https: o link vai pro email do responsável e pro portal, e
# esquema como `javascript:`/`data:` seria vetor de ataque no clique. O
# padrão do `URLField` ainda aceitaria ftp/ftps, que não têm uso aqui.
# Mesma decisão de `apps/materiais/models.py`; duplicado em vez de
# importado pra não acoplar duas apps de domínio por um validator.
validar_link = URLValidator(schemes=["http", "https"])


def arredondar_dinheiro(valor: Decimal) -> Decimal:
    """Quantiza em centavos com `ROUND_HALF_UP` (arredondamento comercial).

    O default do `Decimal` é `ROUND_HALF_EVEN` ("banker's rounding"), que
    arredonda 0,005 pra baixo em metade dos casos — em boleto de escola a
    expectativa é sempre pra cima. Todo cálculo de dinheiro deste módulo
    (desconto, multa, juros) passa por aqui antes de virar resultado.
    """
    return valor.quantize(CENTAVO, rounding=ROUND_HALF_UP)


def multa_percentual_padrao() -> Decimal:
    """Default de `PlanoCobranca.multa_percentual`, lido de settings.

    Callable (e não o valor direto) pra que trocar a env mude o default
    dos contratos novos sem exigir migration. Os contratos já criados
    guardam o percentual que valia no cadastro — é cláusula de contrato,
    não configuração do sistema, então não pode mudar retroativamente.
    """
    return Decimal(str(settings.FINANCEIRO_MULTA_PERCENTUAL_PADRAO))


def juros_mes_percentual_padrao() -> Decimal:
    """Default de `PlanoCobranca.juros_mes_percentual`. Ver acima."""
    return Decimal(str(settings.FINANCEIRO_JUROS_MES_PERCENTUAL_PADRAO))


class PlanoCobranca(BaseModelEscopado):
    """Contrato financeiro de um aluno: a régua que gera as faturas.

    Um aluno pode ter vários planos ao longo do tempo (renovação anual,
    troca de turno, bolsa que começa no meio do ano), mas não dois
    valendo ao mesmo tempo — `clean()` recusa vigência sobreposta entre
    planos **ativos** do mesmo aluno. Desativar o plano antigo é o que
    libera a vigência pro novo.

    Limitação conhecida e consciente (v1): essa checagem é de
    aplicação, não de banco. `objects.create()`/`bulk_create()` não
    chamam `clean()`, e duas requisições concorrentes podem passar as
    duas. A garantia real seria uma exclusion constraint em
    `daterange` (`EXCLUDE USING gist`, extensão `btree_gist`) — está
    anotada no `FINANCEIRO.md` como o caminho pra quando valer o custo.
    O estrago que ela evitaria, aliás, já é barrado no destino: a
    `Fatura` tem unique de banco em `(aluno, competencia)`, então nem
    com dois planos sobrepostos o aluno é cobrado duas vezes no mês.
    """

    class DescontoTipo(models.TextChoices):
        NENHUM = "nenhum", "Sem desconto"
        PERCENTUAL = "percentual", "Percentual"
        FIXO = "fixo", "Valor fixo"

    aluno = models.ForeignKey(
        Aluno, on_delete=models.PROTECT, related_name="planos_cobranca"
    )

    # Quem paga. Mora no plano porque pagador é cláusula de contrato: o
    # aluno com mãe e pai vinculados tem dois responsáveis no portal e um
    # só titular do boleto, e deixar a escolha implícita ("o primeiro que
    # tiver CPF") faria o titular trocar sozinho no dia em que alguém
    # preenchesse o CPF do outro.
    #
    # Opcional porque cobrança online é opt-in da escola: quem recebe Pix
    # na secretaria nunca preenche, e todo plano existente nasceu sem.
    # Referência por string em vez de import pra manter `financeiro`
    # independente de `portal` em tempo de import — a dependência é só de
    # schema, e nenhum dos dois lados precisa do outro carregado.
    pagador = models.ForeignKey(
        "portal.Responsavel",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="planos_pagos",
        help_text="Responsável que paga. Exigido só para emitir cobrança.",
    )

    valor_mensalidade = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(CENTAVO)],
        help_text="Valor cheio da mensalidade, antes do desconto.",
    )
    # 1 a 31: o dia 31 é cadastro legítimo ("vence no último dia"), e
    # quem resolve fevereiro é o clamp da geração (`services.py`), que
    # trava no último dia do mês da competência. Validar em 1..28 aqui
    # obrigaria a escola a mentir no cadastro.
    dia_vencimento = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(31)],
        help_text=(
            "Dia do mês do vencimento (1 a 31). Em mês mais curto, a "
            "geração usa o último dia disponível."
        ),
    )

    desconto_tipo = models.CharField(
        max_length=10,
        choices=DescontoTipo.choices,
        default=DescontoTipo.NENHUM,
    )
    # Serve a dois significados conforme o `desconto_tipo` (percentual ou
    # dinheiro). Dois campos separados deixariam sempre um nulo e a
    # pergunta "qual vale?" de volta na mesa; `clean()` garante a
    # coerência do par.
    desconto_valor = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
        help_text="Percentual (0 a 100) ou valor em reais, conforme o tipo.",
    )

    # Cláusula de contrato, não configuração: o default vem de settings
    # no momento do cadastro e depois pertence a este plano. É também o
    # que o Asaas pede no payload da cobrança (fine/interest).
    multa_percentual = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=multa_percentual_padrao,
        validators=[MinValueValidator(Decimal("0.00")), MaxValueValidator(Decimal("100.00"))],
        help_text="Multa única por atraso, em % do saldo (ex.: 2,00).",
    )
    juros_mes_percentual = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=juros_mes_percentual_padrao,
        validators=[MinValueValidator(Decimal("0.00")), MaxValueValidator(Decimal("100.00"))],
        help_text="Juros de mora ao mês, em % do saldo, pro rata die (ex.: 1,00).",
    )

    vigencia_inicio = models.DateField()
    # Nulo = vigência aberta (contrato corrente, sem data de término).
    vigencia_fim = models.DateField(null=True, blank=True)

    ativo = models.BooleanField(default=True, db_index=True)

    escola = models.ForeignKey(
        Escola, on_delete=models.PROTECT, related_name="planos_cobranca"
    )

    history = HistoricalRecords()

    class Meta:
        verbose_name = "plano de cobrança"
        verbose_name_plural = "planos de cobrança"
        ordering = ["-vigencia_inicio", "-criado_em"]
        indexes = [
            # Geração mensal: planos ativos da escola.
            models.Index(
                fields=["escola", "ativo"],
                name="plano_cob_idx_escola_ativo",
            ),
            # Ficha financeira do aluno.
            models.Index(
                fields=["aluno", "-vigencia_inicio"],
                name="plano_cob_idx_aluno_vigencia",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.aluno} — {self.valor_mensalidade} (dia {self.dia_vencimento})"

    # ------------------------------------------------------------------ #
    # Cálculo                                                            #
    # ------------------------------------------------------------------ #

    def valor_efetivo(self) -> Decimal:
        """Mensalidade já com o desconto aplicado — o valor que vira fatura.

        Nunca negativo: desconto fixo maior que a mensalidade é barrado no
        `clean()`, mas um plano criado por shell poderia passar, e fatura
        de valor negativo não significa nada no contas a receber.
        """
        if self.desconto_tipo == self.DescontoTipo.PERCENTUAL:
            desconto = self.valor_mensalidade * self.desconto_valor / Decimal("100")
        elif self.desconto_tipo == self.DescontoTipo.FIXO:
            desconto = self.desconto_valor
        else:
            desconto = Decimal("0.00")
        return max(
            arredondar_dinheiro(self.valor_mensalidade - desconto), Decimal("0.00")
        )

    def vigente_em(self, dia: date) -> bool:
        """True se o contrato cobre `dia` (ignora `ativo` de propósito).

        Separar as duas perguntas deixa a geração explícita: ela filtra
        `ativo=True` no queryset e usa isto pra competência.
        """
        if dia < self.vigencia_inicio:
            return False
        return self.vigencia_fim is None or dia <= self.vigencia_fim

    # ------------------------------------------------------------------ #
    # Invariantes                                                        #
    # ------------------------------------------------------------------ #

    def plano_sobreposto(self):
        """Outro plano ATIVO do mesmo aluno cuja vigência intersecta a desta.

        Intervalos fechados, com `vigencia_fim=None` valendo infinito.
        Resolvido em SQL (e não iterando em Python) porque um aluno com
        histórico longo traria vários planos pra memória só pra comparar
        duas datas.
        """
        if not self.aluno_id:
            return None
        qs = PlanoCobranca.objects.filter(aluno_id=self.aluno_id, ativo=True)
        if self.pk:
            qs = qs.exclude(pk=self.pk)
        # O outro plano começa antes do fim deste...
        if self.vigencia_fim is not None:
            qs = qs.filter(vigencia_inicio__lte=self.vigencia_fim)
        # ...e termina depois do início deste.
        qs = qs.filter(
            Q(vigencia_fim__isnull=True) | Q(vigencia_fim__gte=self.vigencia_inicio)
        )
        return qs.first()

    def clean(self) -> None:
        super().clean()
        errors: dict[str, str] = {}

        if self.aluno_id and self.escola_id and self.aluno.escola_id != self.escola_id:
            errors["aluno"] = "O aluno deve pertencer à mesma escola do plano."

        # O pagador tem que ser responsável **deste** aluno, não qualquer
        # responsável da escola: o vínculo é o que autoriza alguém a ver os
        # dados do aluno (`RESPONSAVEIS.md`), e cobrar em nome de quem não
        # tem vínculo poria o nome de um terceiro no boleto da família.
        # `elif` pra não empilhar duas mensagens na mesma chave — escola
        # errada é a falha mais fundamental das duas.
        if self.pagador_id:
            if self.escola_id and self.pagador.escola_id != self.escola_id:
                errors["pagador"] = (
                    "O pagador deve pertencer à mesma escola do plano."
                )
            elif (
                self.aluno_id
                and not self.pagador.alunos.filter(pk=self.aluno_id).exists()
            ):
                errors["pagador"] = (
                    "O pagador deve ser um responsável vinculado a este aluno."
                )

        if (
            self.vigencia_inicio
            and self.vigencia_fim
            and self.vigencia_fim < self.vigencia_inicio
        ):
            errors["vigencia_fim"] = "O fim da vigência não pode ser antes do início."

        if self.desconto_tipo == self.DescontoTipo.NENHUM:
            if self.desconto_valor:
                errors["desconto_valor"] = (
                    "Sem desconto, o valor do desconto deve ser zero."
                )
        elif self.desconto_tipo == self.DescontoTipo.PERCENTUAL:
            if self.desconto_valor > Decimal("100"):
                errors["desconto_valor"] = "O desconto percentual não pode passar de 100."
        elif self.desconto_tipo == self.DescontoTipo.FIXO:
            if (
                self.valor_mensalidade is not None
                and self.desconto_valor > self.valor_mensalidade
            ):
                errors["desconto_valor"] = (
                    "O desconto fixo não pode ser maior que a mensalidade."
                )

        if self.ativo and self.vigencia_inicio and (outro := self.plano_sobreposto()):
            if outro.vigencia_fim:
                periodo = (
                    f"de {outro.vigencia_inicio:%d/%m/%Y} "
                    f"a {outro.vigencia_fim:%d/%m/%Y}"
                )
            else:
                periodo = f"desde {outro.vigencia_inicio:%d/%m/%Y}, sem término"
            errors["vigencia_inicio"] = (
                "Este aluno já tem um plano ativo com vigência sobreposta "
                f"({periodo}). Desative o plano anterior ou ajuste as datas."
            )

        if errors:
            raise ValidationError(errors)


class Fatura(BaseModelEscopado):
    """Uma competência do plano: a linha do contas a receber.

    `competencia` é o mês de referência, sempre no dia 1 — `DateField`
    em vez de um par `mes`/`ano` porque ordenação, range (`?de=&ate=`) e
    unique saem de graça, e porque "março de 2026" é uma data, não dois
    inteiros. O dia 1 é imposto no `clean()`.

    `valor` é **congelado na geração**, não lido do plano na hora de
    exibir: reajuste em maio não pode reescrever a fatura de março, que
    já foi enviada ao responsável.

    `aluno` é desnormalizado do plano por um motivo só, e é o que sustenta
    o invariante central do módulo: **uma mensalidade por aluno por mês**.
    Com unique em `(plano, competencia)`, a troca de plano no meio do mês
    (plano A encerra dia 10, plano B começa dia 11 — vigências não
    sobrepostas, cadastro legítimo) geraria duas faturas pra mesma
    competência e cobraria o aluno duas vezes no mês da virada. Uma
    constraint de banco não atravessa FK, então o `aluno` mora aqui.
    `clean()` trava `fatura.aluno == plano.aluno` pra desnormalização não
    poder divergir.
    """

    class Status(models.TextChoices):
        PENDENTE = "pendente", "Pendente"
        PAGO = "pago", "Pago"
        VENCIDO = "vencido", "Vencido"
        CANCELADO = "cancelado", "Cancelado"

    plano = models.ForeignKey(
        PlanoCobranca, on_delete=models.PROTECT, related_name="faturas"
    )
    aluno = models.ForeignKey(
        Aluno, on_delete=models.PROTECT, related_name="faturas"
    )

    competencia = models.DateField(
        help_text="Mês de referência, sempre no dia 1 (ex.: 2026-03-01)."
    )
    valor = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(CENTAVO)],
        help_text="Valor congelado na geração, já com desconto do plano.",
    )
    vencimento = models.DateField()

    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.PENDENTE,
        db_index=True,
    )
    valor_pago = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
        help_text="Soma dos pagamentos conciliados. Escrito pelo services.",
    )
    data_pagamento = models.DateField(
        null=True,
        blank=True,
        help_text="Data do pagamento que liquidou a fatura.",
    )

    # Ponteiro pra cobrança no gateway. `blank` porque a fatura nasce
    # antes de existir cobrança lá (e pode nunca existir, se a escola
    # receber na secretaria).
    id_externo = models.CharField(
        max_length=64,
        blank=True,
        help_text="Id da cobrança no gateway (ex.: pay_... no Asaas).",
    )
    link_pagamento = models.URLField(
        max_length=500,
        blank=True,
        validators=[validar_link],
        help_text="Link do boleto/Pix devolvido pelo gateway.",
    )

    escola = models.ForeignKey(
        Escola, on_delete=models.PROTECT, related_name="faturas"
    )

    history = HistoricalRecords()

    class Meta:
        verbose_name = "fatura"
        verbose_name_plural = "faturas"
        ordering = ["-competencia", "aluno__nome_completo"]
        constraints = [
            # O invariante do módulo: uma mensalidade por aluno por mês,
            # mesmo na virada de plano. Ver docstring da classe.
            models.UniqueConstraint(
                fields=["aluno", "competencia"],
                name="fatura_unique_aluno_competencia",
            ),
            # Duas faturas apontando pra mesma cobrança no gateway fariam
            # o webhook conciliar a errada. Parcial porque vazio é o
            # estado normal de quem nunca foi pro gateway.
            models.UniqueConstraint(
                fields=["id_externo"],
                condition=~Q(id_externo=""),
                name="fatura_unique_id_externo",
            ),
        ]
        indexes = [
            # Tela da secretaria e job de vencimento: o que está em
            # aberto na escola, por data de vencimento.
            models.Index(
                fields=["escola", "status", "vencimento"],
                name="fatura_idx_escola_status_venc",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.aluno} — {self.competencia:%m/%Y} ({self.get_status_display()})"

    # ------------------------------------------------------------------ #
    # Cálculo — multa e juros são regra, não campo                       #
    # ------------------------------------------------------------------ #

    def saldo(self) -> Decimal:
        """Quanto falta do principal. Nunca negativo (pagamento a mais existe)."""
        return max(arredondar_dinheiro(self.valor - self.valor_pago), Decimal("0.00"))

    def dias_atraso(self, hoje: date | None = None) -> int:
        """Dias corridos após o vencimento. Zero no dia do vencimento."""
        hoje = hoje or date.today()
        if hoje <= self.vencimento:
            return 0
        return (hoje - self.vencimento).days

    def encargos(self, hoje: date | None = None) -> Decimal:
        """Multa única + juros de mora pro rata die, sobre o saldo em aberto.

        Lê os percentuais do `plano` — quem chamar em lista precisa de
        `select_related("plano")`, senão é uma query por linha.

        Juros ao mês convertidos em juros ao dia por `/30` (prática
        corrente de cobrança no Brasil: 1% ao mês = 1/30% por dia de
        atraso), não pela quantidade de dias do mês real.

        Fatura cancelada não gera encargo, e fatura sem saldo tampouco —
        o que estiver pago está pago.
        """
        if self.status == self.Status.CANCELADO:
            return Decimal("0.00")
        saldo = self.saldo()
        dias = self.dias_atraso(hoje)
        if saldo <= 0 or dias <= 0:
            return Decimal("0.00")
        multa = saldo * self.plano.multa_percentual / Decimal("100")
        juros = (
            saldo
            * self.plano.juros_mes_percentual
            / Decimal("100")
            * Decimal(dias)
            / Decimal("30")
        )
        return arredondar_dinheiro(multa + juros)

    def valor_atualizado(self, hoje: date | None = None) -> Decimal:
        """Quanto cobrar hoje: saldo + encargos do atraso."""
        return arredondar_dinheiro(self.saldo() + self.encargos(hoje))

    def esta_vencida(self, hoje: date | None = None) -> bool:
        """Verdade do momento, independente do `status` gravado.

        O `status` é o que o banco acredita (e o que a tela mostra); quem
        o move pra `vencido` é o job diário. Este método é a fonte pra
        esse job — e a rede de segurança pra quando ele não rodou.
        """
        if self.status not in (self.Status.PENDENTE, self.Status.VENCIDO):
            return False
        return self.dias_atraso(hoje) > 0

    # ------------------------------------------------------------------ #
    # Invariantes                                                        #
    # ------------------------------------------------------------------ #

    def clean(self) -> None:
        super().clean()
        errors: dict[str, str] = {}

        if self.plano_id and self.escola_id and self.plano.escola_id != self.escola_id:
            errors["plano"] = "O plano deve pertencer à mesma escola da fatura."
        if self.aluno_id and self.escola_id and self.aluno.escola_id != self.escola_id:
            errors["aluno"] = "O aluno deve pertencer à mesma escola da fatura."
        # A desnormalização não pode divergir do contrato que gerou a fatura.
        if self.plano_id and self.aluno_id and self.plano.aluno_id != self.aluno_id:
            errors["aluno"] = "O aluno da fatura deve ser o mesmo aluno do plano."

        if self.competencia and self.competencia.day != 1:
            errors["competencia"] = (
                "A competência deve ser o dia 1 do mês de referência."
            )

        if self.competencia and self.vencimento and self.vencimento < self.competencia:
            errors["vencimento"] = (
                "O vencimento não pode ser antes do mês de competência."
            )

        if self.status == self.Status.PAGO:
            if not self.data_pagamento:
                errors["data_pagamento"] = (
                    "Fatura paga precisa da data do pagamento."
                )
        elif self.data_pagamento:
            errors["data_pagamento"] = (
                "Só fatura paga tem data de pagamento."
            )

        if self.status == self.Status.CANCELADO and self.valor_pago:
            errors["status"] = (
                "Fatura com pagamento registrado não pode ser cancelada — "
                "estorne o pagamento primeiro."
            )

        if errors:
            raise ValidationError(errors)


class FaturaItem(BaseModelEscopado):
    """Linha do detalhamento da fatura (mensalidade, taxa, material).

    `CASCADE` na fatura, como `ItemPresenca` no registro de presença: o
    ciclo de vida da linha pertence ao documento, e item órfão não
    significa nada. É a única exceção de `PROTECT` que este módulo abre.

    `Fatura.valor` continua sendo a fonte da verdade do quanto cobrar; o
    item é detalhamento pro responsável entender a composição. A
    igualdade entre a soma das linhas e o valor da fatura é
    responsabilidade de quem monta as duas coisas (`services.py`), não
    uma invariante de banco — travá-la aqui faria a ordem dos saves
    importar, e qualquer item salvo antes do ajuste do total cairia num
    erro de validação sem culpa.
    """

    fatura = models.ForeignKey(
        Fatura, on_delete=models.CASCADE, related_name="itens"
    )
    descricao = models.CharField(max_length=120)
    valor = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(CENTAVO)],
    )

    escola = models.ForeignKey(
        Escola, on_delete=models.PROTECT, related_name="fatura_itens"
    )

    history = HistoricalRecords()

    class Meta:
        verbose_name = "item de fatura"
        verbose_name_plural = "itens de fatura"
        ordering = ["id"]

    def __str__(self) -> str:
        return f"{self.descricao} — {self.valor}"

    def clean(self) -> None:
        super().clean()
        if (
            self.fatura_id
            and self.escola_id
            and self.fatura.escola_id != self.escola_id
        ):
            raise ValidationError(
                {"fatura": "A fatura deve pertencer à mesma escola do item."}
            )


class Pagamento(BaseModelEscopado):
    """Dinheiro que entrou, conciliado contra uma fatura.

    Pode vir do gateway (webhook) ou da secretaria (recebeu em dinheiro,
    Pix na conta da escola). `referencia_externa` distingue os dois e é o
    que torna a conciliação idempotente: o unique parcial impede que a
    reentrega do mesmo evento de webhook — que o Asaas faz por design —
    registre o pagamento duas vezes.

    Pagamento a mais que o saldo é permitido de propósito: o responsável
    que paga boleto vencido com multa deposita mais que o principal, e
    recusar isso impediria registrar o que de fato aconteceu.
    """

    class Metodo(models.TextChoices):
        PIX = "pix", "Pix"
        BOLETO = "boleto", "Boleto"
        CARTAO = "cartao", "Cartão"
        DINHEIRO = "dinheiro", "Dinheiro"
        # Existe pro que chega pelo gateway num meio que não modelamos: a
        # doc do Asaas diz que valor entrando na conta por Pix ou TED é
        # associado a uma cobrança, então a mensalidade emitida com
        # "pagador escolhe" pode voltar paga como `TRANSFER`/`DEPOSIT`.
        # Não é opção de secretaria — ela escolhe entre os quatro de cima.
        OUTRO = "outro", "Outro"

    fatura = models.ForeignKey(
        Fatura, on_delete=models.PROTECT, related_name="pagamentos"
    )
    valor = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(CENTAVO)],
    )
    data = models.DateField()
    metodo = models.CharField(max_length=10, choices=Metodo.choices)
    referencia_externa = models.CharField(
        max_length=64,
        blank=True,
        help_text="Id do pagamento no gateway. Vazio quando registrado na secretaria.",
    )

    escola = models.ForeignKey(
        Escola, on_delete=models.PROTECT, related_name="pagamentos"
    )

    history = HistoricalRecords()

    class Meta:
        verbose_name = "pagamento"
        verbose_name_plural = "pagamentos"
        ordering = ["-data", "-criado_em"]
        constraints = [
            # Idempotência da conciliação: o mesmo pagamento do gateway
            # não entra duas vezes. Parcial porque vazio é o estado
            # normal do recebimento manual.
            models.UniqueConstraint(
                fields=["referencia_externa"],
                condition=~Q(referencia_externa=""),
                name="pagamento_unique_referencia_externa",
            ),
        ]
        indexes = [
            # Caixa do dia / conciliação do período na escola.
            models.Index(
                fields=["escola", "-data"],
                name="pagamento_idx_escola_data",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.valor} em {self.data:%d/%m/%Y} ({self.get_metodo_display()})"

    def clean(self) -> None:
        super().clean()
        errors: dict[str, str] = {}

        if (
            self.fatura_id
            and self.escola_id
            and self.fatura.escola_id != self.escola_id
        ):
            errors["fatura"] = "A fatura deve pertencer à mesma escola do pagamento."

        if self.data and self.data > date.today():
            errors["data"] = "A data do pagamento não pode ser no futuro."

        if self.fatura_id and self.fatura.status == Fatura.Status.CANCELADO:
            errors["fatura"] = "Fatura cancelada não recebe pagamento."

        if errors:
            raise ValidationError(errors)


class EventoWebhook(TimeStampedModel):
    """Evento de cobrança recebido do gateway, guardado antes de processado.

    **Não é `BaseModelEscopado`**, ao contrário de todo o resto do módulo.
    O evento chega por um endpoint sem autenticação e sem tenant: a escola
    só se descobre depois, resolvendo a fatura que o evento aponta. Exigir
    `escola` no insert obrigaria a resolver o tenant antes de persistir, o
    que é o inverso do que a confiabilidade pede aqui — grava primeiro,
    processa depois, pra que uma falha de processamento não perca o
    evento. A `fatura` (e por ela a escola) fica nula enquanto não
    resolver.

    `id_evento` é o id do provedor, e o `unique` nele é o que torna a
    conciliação idempotente: reentrega é comportamento normal do Asaas,
    não erro (a doc deles diz que 15 falhas consecutivas pausam a fila, e
    por isso o endpoint responde 200 rápido e processa de forma repetível).

    Sem `HistoricalRecords`: isto já é um log append-only de fato externo,
    e auditar um log seria guardar duas vezes a mesma coisa. O que muda
    depois da criação são só `fatura`, `processado_em` e `erro`, escritos
    pelo processamento.
    """

    # 128 porque o id deles é `evt_<hash>&<numero>` (uns 45 caracteres no
    # exemplo da doc) e o formato é deles pra mudar.
    id_evento = models.CharField(
        max_length=128,
        unique=True,
        help_text="Id do evento no gateway. Único — reentrega não duplica.",
    )
    tipo = models.CharField(
        max_length=60,
        help_text="Tipo do evento no gateway (ex.: PAYMENT_RECEIVED).",
    )
    # Corpo cru: é o que permite reprocessar ou entender um evento que o
    # código da época não soube tratar, sem depender do log do provedor.
    payload = models.JSONField(default=dict)

    fatura = models.ForeignKey(
        Fatura,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="eventos_webhook",
        help_text="Fatura que o evento aponta. Nula se não foi resolvida.",
    )

    processado_em = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Quando o evento foi tratado. Nulo = pendente ou falhou.",
    )
    # Guardado além de ir pro log porque é o que deixa a falha visível no
    # admin pra quem não tem acesso ao Sentry.
    erro = models.TextField(blank=True)

    class Meta:
        verbose_name = "evento de webhook"
        verbose_name_plural = "eventos de webhook"
        ordering = ["-criado_em"]
        indexes = [
            # A pergunta operacional é "o que chegou e não foi tratado".
            models.Index(
                fields=["processado_em", "criado_em"],
                name="evento_wh_idx_processado",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.tipo} — {self.id_evento}"
