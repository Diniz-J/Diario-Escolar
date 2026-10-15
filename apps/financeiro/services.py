"""Serviços do financeiro — o que não pertence à view nem ao model.

Três operações, e todas as três existem porque dinheiro não pode ser
escrito em efeito colateral de `save()` (`FINANCEIRO.md` §2.4):

- `gerar_faturas`: a recorrência mensal, idempotente.
- `registrar_pagamento` / `estornar_pagamento`: a conciliação, que é
  quem escreve `valor_pago` e `status` da fatura.
- `marcar_vencidas`: o job diário que move o vencido.

As três são chamáveis de management command, de view e de webhook, e
nenhuma delas depende de request.
"""
import calendar
import logging
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from django.db import transaction
from django.db.models import Q, Sum
from django.utils import timezone
from simple_history.utils import bulk_create_with_history, bulk_update_with_history

from .models import Fatura, FaturaItem, Pagamento, PlanoCobranca, arredondar_dinheiro

logger = logging.getLogger(__name__)


# ====================================================================== #
# Geração recorrente                                                     #
# ====================================================================== #


@dataclass
class ResultadoGeracao:
    """O que a geração fez, pra o command imprimir e o teste conferir."""

    competencia: date
    criadas: int = 0
    # Aluno que já tinha fatura na competência: a segunda execução do mês
    # cai toda aqui, e é o que torna o comando seguro de repetir.
    ignoradas: int = 0
    planos_considerados: int = 0
    # Aluno com mais de um plano cobrindo o mês (virada de contrato):
    # registrado pra ficar visível no log, não é erro.
    alunos_com_plano_concorrente: list[int] = field(default_factory=list)


def primeiro_dia(competencia: date) -> date:
    """Normaliza qualquer data pro dia 1 do seu mês."""
    return competencia.replace(day=1)


def vencimento_da_competencia(competencia: date, dia_vencimento: int) -> date:
    """Resolve o vencimento, travando no último dia do mês quando preciso.

    É aqui que `dia_vencimento=31` deixa de ser problema em fevereiro: o
    cadastro guarda a intenção da escola ("vence no fim do mês") e a
    geração aterra no dia que existe. Ver `FINANCEIRO.md` §2.7.
    """
    competencia = primeiro_dia(competencia)
    ultimo_dia = calendar.monthrange(competencia.year, competencia.month)[1]
    return competencia.replace(day=min(dia_vencimento, ultimo_dia))


def _planos_da_competencia(competencia: date, escola_id: int | None = None):
    """Planos ativos cuja vigência intersecta o mês da competência.

    Intervalo fechado nos dois lados, com `vigencia_fim=None` valendo
    infinito. A ordenação por `(aluno_id, vigencia_inicio)` é o que faz a
    escolha de plano ser determinística — ver `_escolher_plano_por_aluno`.
    """
    competencia = primeiro_dia(competencia)
    ultimo_dia = calendar.monthrange(competencia.year, competencia.month)[1]
    fim_do_mes = competencia.replace(day=ultimo_dia)

    qs = PlanoCobranca.objects.filter(
        ativo=True, vigencia_inicio__lte=fim_do_mes
    ).filter(Q(vigencia_fim__isnull=True) | Q(vigencia_fim__gte=competencia))
    if escola_id is not None:
        qs = qs.filter(escola_id=escola_id)
    return qs.select_related("aluno").order_by("aluno_id", "vigencia_inicio", "id")


def _escolher_plano_por_aluno(planos) -> tuple[dict[int, PlanoCobranca], list[int]]:
    """Um plano por aluno: o de vigência mais antiga entre os que pegam o mês.

    Regra de negócio travada (`FINANCEIRO.md` §2.8): na virada de contrato
    no meio do mês — plano A até o dia 10, plano B do dia 11 — o mês da
    virada é cobrado pelo contrato **que estava valendo no dia 1**, e o
    novo começa a cobrar na competência seguinte. A mesma regra resolve a
    matrícula nova no meio do mês: só existe o contrato novo, então ele
    cobra o mês inteiro (sem rateio por dias, que está fora de escopo).

    Escolher na aplicação, e não no SQL, é deliberado: a alternativa seria
    deixar o unique de banco decidir qual das duas faturas sobrevive, e
    aí quem cobra o mês depende da ordem de inserção — arbitrário num
    número que vai pro boleto do responsável.
    """
    escolhidos: dict[int, PlanoCobranca] = {}
    concorrentes: list[int] = []
    for plano in planos:
        if plano.aluno_id in escolhidos:
            # A ordenação garante que o primeiro visto é o mais antigo.
            concorrentes.append(plano.aluno_id)
            continue
        escolhidos[plano.aluno_id] = plano
    return escolhidos, concorrentes


@transaction.atomic
def gerar_faturas(
    competencia: date,
    escola_id: int | None = None,
    dry_run: bool = False,
) -> ResultadoGeracao:
    """Gera as faturas da competência pros planos ativos. Idempotente.

    Idempotência em duas camadas: a consulta dos alunos que já têm fatura
    no mês (que é o que faz a segunda execução não fazer nada) e o unique
    de banco em `(aluno, competencia)`, que é a rede pra execução
    concorrente. Rodar o comando duas vezes é seguro por construção, não
    por sorte — é o requisito de ter cron chamando isso.

    Cada fatura nasce com uma linha de detalhamento ("Mensalidade
    MM/AAAA") de valor igual ao total, pra que `FaturaItem` e
    `Fatura.valor` nasçam coerentes (`FINANCEIRO.md` §3.5).
    """
    competencia = primeiro_dia(competencia)
    planos = list(_planos_da_competencia(competencia, escola_id))
    escolhidos, concorrentes = _escolher_plano_por_aluno(planos)

    resultado = ResultadoGeracao(
        competencia=competencia,
        planos_considerados=len(planos),
        alunos_com_plano_concorrente=concorrentes,
    )

    ja_faturados = set(
        Fatura.objects.filter(
            aluno_id__in=escolhidos.keys(), competencia=competencia
        ).values_list("aluno_id", flat=True)
    )

    a_criar: list[Fatura] = []
    for aluno_id, plano in escolhidos.items():
        if aluno_id in ja_faturados:
            resultado.ignoradas += 1
            continue
        a_criar.append(
            Fatura(
                escola_id=plano.escola_id,
                plano=plano,
                aluno_id=aluno_id,
                competencia=competencia,
                # Congelado: reajuste depois não reescreve esta fatura.
                valor=plano.valor_efetivo(),
                vencimento=vencimento_da_competencia(
                    competencia, plano.dia_vencimento
                ),
            )
        )

    resultado.criadas = len(a_criar)
    if dry_run or not a_criar:
        return resultado

    criadas = bulk_create_with_history(a_criar, Fatura)
    rotulo = f"Mensalidade {competencia:%m/%Y}"
    bulk_create_with_history(
        [
            FaturaItem(
                escola_id=fatura.escola_id,
                fatura=fatura,
                descricao=rotulo,
                valor=fatura.valor,
            )
            for fatura in criadas
        ],
        FaturaItem,
    )
    logger.info(
        "Geração de faturas %s: %s criadas, %s ignoradas",
        f"{competencia:%m/%Y}",
        resultado.criadas,
        resultado.ignoradas,
    )
    return resultado


# ====================================================================== #
# Conciliação                                                            #
# ====================================================================== #


def _total_pago(fatura: Fatura) -> Decimal:
    """Soma dos pagamentos da fatura, do banco.

    **Recálculo, não incremento.** Somar no valor que já estava gravado
    duplicaria o lançamento se o mesmo evento de webhook fosse processado
    duas vezes por um caminho que escapasse do unique; recalcular é
    idempotente e corrige sozinho um `valor_pago` que tenha divergido.
    """
    total = fatura.pagamentos.aggregate(total=Sum("valor"))["total"]
    return arredondar_dinheiro(total or Decimal("0.00"))


def _reconciliar(fatura: Fatura, hoje: date | None = None) -> Fatura:
    """Reescreve `valor_pago`, `status` e `data_pagamento` a partir dos pagamentos.

    Única função do módulo que escreve esses três campos. Fatura
    cancelada não é tocada: o cancelamento é decisão administrativa e não
    pode ser desfeito por um pagamento que chegou atrasado.
    """
    if fatura.status == Fatura.Status.CANCELADO:
        return fatura

    hoje = hoje or date.today()
    fatura.valor_pago = _total_pago(fatura)

    if fatura.valor_pago >= fatura.valor:
        fatura.status = Fatura.Status.PAGO
        # A data que liquidou é a do último pagamento, não a de hoje:
        # é ela que vale como prova de quitação pro responsável.
        ultimo = fatura.pagamentos.order_by("-data", "-id").first()
        fatura.data_pagamento = ultimo.data if ultimo else hoje
    else:
        fatura.data_pagamento = None
        fatura.status = (
            Fatura.Status.VENCIDO
            if fatura.vencimento < hoje
            else Fatura.Status.PENDENTE
        )

    fatura.save(
        update_fields=["valor_pago", "status", "data_pagamento", "atualizado_em"]
    )
    return fatura


@transaction.atomic
def registrar_pagamento(
    fatura: Fatura,
    valor: Decimal,
    data: date,
    metodo: str,
    referencia_externa: str = "",
) -> Pagamento:
    """Registra o pagamento e reconcilia a fatura, na mesma transação.

    **Idempotente por `referencia_externa`**: chamada repetida com a mesma
    referência devolve o pagamento que já existe, sem criar outro e sem
    levantar erro. É o caso normal do gateway, que reentrega o mesmo
    evento por design — tratar reentrega como falha encheria o Sentry de
    ruído e deixaria a fatia 5 escolhendo entre engolir exceção e
    devolver 500 pro Asaas. Pagamento manual (referência vazia) não tem
    como ser deduplicado e por isso não é: dois Pix iguais no mesmo dia
    são dois pagamentos.

    `select_for_update` na fatura serializa webhook e secretaria: as duas
    podem chegar ao mesmo tempo, e sem o lock as duas leriam o mesmo
    `valor_pago` e uma sobrescreveria a outra.
    """
    if referencia_externa:
        existente = Pagamento.objects.filter(
            referencia_externa=referencia_externa
        ).first()
        if existente is not None:
            logger.info(
                "Pagamento %s já registrado (fatura %s) — reentrega ignorada",
                referencia_externa,
                existente.fatura_id,
            )
            return existente

    fatura = Fatura.objects.select_for_update().get(pk=fatura.pk)

    pagamento = Pagamento(
        escola_id=fatura.escola_id,
        fatura=fatura,
        valor=valor,
        data=data,
        metodo=metodo,
        referencia_externa=referencia_externa,
    )
    # `full_clean` em vez de só `save`: é aqui que "fatura cancelada não
    # recebe pagamento" e "data não futura" valem pros três chamadores
    # (API, command e webhook), em vez de cada um repetir a checagem.
    pagamento.full_clean()
    pagamento.save()

    _reconciliar(fatura)
    return pagamento


@transaction.atomic
def estornar_pagamento(pagamento: Pagamento) -> Fatura:
    """Apaga o pagamento e reconcilia a fatura.

    Estorno é `DELETE` de verdade, não soft delete: o pagamento não
    existiu, e deixar a linha com um sinalizador obrigaria todo cálculo de
    saldo a lembrar de filtrá-la. O que ficou aconteceu está no audit log
    (`HistoricalPagamento` guarda a linha apagada e quem apagou).

    É o que torna acionável a recusa de cancelar fatura com pagamento
    registrado: estorna aqui, cancela depois.
    """
    fatura = Fatura.objects.select_for_update().get(pk=pagamento.fatura_id)
    pagamento.delete()
    return _reconciliar(fatura)


# ====================================================================== #
# Vencimento                                                             #
# ====================================================================== #


def marcar_vencidas(hoje: date | None = None, escola_id: int | None = None) -> int:
    """Move `pendente` com vencimento passado pra `vencido`. Devolve a contagem.

    Só mexe em `pendente`: paga e cancelada não voltam, e `vencido` já
    está no destino. O recorte é naturalmente pequeno (o que venceu desde
    a última execução), então carregar os objetos pra ter audit log sai
    barato — `.update()` em massa seria mais rápido e não geraria
    histórico nem carimbaria `atualizado_em`.

    `esta_vencida()` no modelo continua sendo a verdade do momento, pra
    quando o cron não rodou.
    """
    hoje = hoje or date.today()
    qs = Fatura.objects.filter(status=Fatura.Status.PENDENTE, vencimento__lt=hoje)
    if escola_id is not None:
        qs = qs.filter(escola_id=escola_id)

    vencidas = list(qs)
    if not vencidas:
        return 0

    # `bulk_update_with_history` não dispara `auto_now`, então
    # `atualizado_em` entra na mão (mesma nota de apps/avaliacao/views.py)
    # — sem isso a fatura ficaria com status novo e timestamp velho.
    agora = timezone.now()
    for fatura in vencidas:
        fatura.status = Fatura.Status.VENCIDO
        fatura.atualizado_em = agora
    bulk_update_with_history(
        vencidas, Fatura, ["status", "atualizado_em"], batch_size=500
    )
    logger.info("Faturas marcadas como vencidas em %s: %s", hoje, len(vencidas))
    return len(vencidas)
