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

from .gateways import (
    CobrancaGateway,
    DadosCobranca,
    DadosPagador,
    ErroDeGateway,
    Pagador,
    SituacaoCobranca,
)
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


# ====================================================================== #
# Ficha financeira do aluno                                              #
# ====================================================================== #


@dataclass
class TotaisFicha:
    """Consolidado da situação do aluno. Tudo em `Decimal`."""

    em_aberto: Decimal
    vencido: Decimal
    encargos_hoje: Decimal
    a_cobrar_hoje: Decimal
    pago_no_ano: Decimal
    faturas_abertas: int


@dataclass
class FichaFinanceira:
    """O que a ficha do aluno mostra: consolidado mais os três históricos."""

    aluno: object
    totais: TotaisFicha
    planos: list
    faturas: list
    pagamentos: list


def ficha_financeira(aluno, hoje: date | None = None) -> FichaFinanceira:
    """Monta a ficha financeira de um aluno, agregando on-the-fly.

    Sem modelo próprio, no mesmo molde de `boletins` e `relatorios`: a
    pergunta "quanto este aluno deve" não é um dado guardado, é uma
    consulta sobre faturas e pagamentos.

    **Os totais são somados em Python, sobre os métodos do modelo, e não
    em SQL.** Dois motivos, nesta ordem:

    1. `Fatura.saldo()` trava em zero quando o pagamento foi a mais, e
       `encargos()` depende de multa e juros do plano mais os dias de
       atraso de hoje. Um `Sum(F("valor") - F("valor_pago"))` no banco
       faria o excesso de uma fatura abater o saldo de outra — a ficha
       mostraria dívida menor do que a real.
    2. Reusar os métodos garante que a ficha e a tela de faturas nunca
       discordem. Uma soma reescrita em SQL é a maneira mais fácil de a
       ficha dizer um número e o detalhe da fatura dizer outro.

    O custo é carregar as faturas do aluno em memória, o que é um recorte
    naturalmente pequeno (uma por mês por contrato).

    `pago_no_ano` vem do banco porque ali é soma simples de pagamentos,
    sem piso nem regra: não há o que divergir.
    """
    hoje = hoje or date.today()

    faturas = list(
        aluno.faturas.select_related("plano").order_by("-competencia", "-id")
    )
    # Cancelada não é dívida; paga não é dívida. Sobram pendente e vencido.
    abertas = [
        f
        for f in faturas
        if f.status in (Fatura.Status.PENDENTE, Fatura.Status.VENCIDO)
    ]

    em_aberto = sum((f.saldo() for f in abertas), Decimal("0.00"))
    vencido = sum(
        (f.saldo() for f in abertas if f.esta_vencida(hoje)), Decimal("0.00")
    )
    encargos = sum((f.encargos(hoje) for f in abertas), Decimal("0.00"))

    pago_no_ano = Pagamento.objects.filter(
        fatura__aluno=aluno, data__year=hoje.year
    ).aggregate(total=Sum("valor"))["total"] or Decimal("0.00")

    totais = TotaisFicha(
        em_aberto=arredondar_dinheiro(em_aberto),
        vencido=arredondar_dinheiro(vencido),
        encargos_hoje=arredondar_dinheiro(encargos),
        a_cobrar_hoje=arredondar_dinheiro(em_aberto + encargos),
        pago_no_ano=arredondar_dinheiro(pago_no_ano),
        faturas_abertas=len(abertas),
    )

    return FichaFinanceira(
        aluno=aluno,
        totais=totais,
        # Inclui plano encerrado: a ficha é histórico, e saber que o aluno
        # era bolsista até março explica a fatura de março.
        planos=list(
            aluno.planos_cobranca.order_by("-vigencia_inicio", "-id")
        ),
        faturas=faturas,
        pagamentos=list(
            Pagamento.objects.filter(fatura__aluno=aluno)
            .select_related("fatura__aluno")
            .order_by("-data", "-id")
        ),
    )


# ====================================================================== #
# Emissão de cobrança no gateway                                         #
# ====================================================================== #


class EmissaoRecusadaError(Exception):
    """A emissão não pode acontecer, e o motivo não é o provedor.

    Cobre cadastro incompleto (plano sem pagador, pagador sem CPF) e
    estado que não admite cobrança (fatura paga ou cancelada). Separado de
    `ErroDeGateway` porque retentar não resolve: a correção é na tela, não
    na rede. A mensagem é a que a secretaria lê pra saber o que fazer.
    """


def _dados_do_pagador(plano: PlanoCobranca) -> DadosPagador:
    """Monta o cadastro do pagador, ou explica o que falta preencher.

    O CPF é exigido aqui, e não em `_pagador_no_gateway`, de propósito: só
    quem ainda **não** tem cadastro no provedor precisa dele. Checar antes
    bloquearia a emissão de uma família já cadastrada por causa de um CPF
    que o provedor não vai mais pedir.

    A checagem existe porque o provedor recusaria com mensagem em inglês
    sobre `cpfCnpj` — inútil pra quem está operando a secretaria.
    """
    pagador = plano.pagador
    if not pagador.cpf:
        raise EmissaoRecusadaError(
            f"O responsável {pagador.nome} está sem CPF, que o gateway "
            "exige para emitir cobrança."
        )
    return DadosPagador(
        nome=pagador.nome,
        documento=pagador.cpf,
        email=pagador.email,
        # O nosso id vai junto pra que o cadastro de lá seja reconciliável
        # com o nosso sem depender do nome, que repete.
        referencia_externa=str(pagador.pk),
    )


def _pagador_no_gateway(plano: PlanoCobranca, gateway: CobrancaGateway) -> Pagador:
    """Devolve o pagador do provedor, criando o cadastro na primeira vez.

    O id fica guardado em `Responsavel.id_externo_gateway` porque criar
    cliente lá **não** é idempotente: sem guardar, cada emissão abriria
    outro cadastro pra mesma família e o histórico dela ficaria espalhado
    por vários clientes.

    `update_fields` enxuto de propósito: salvar o `Responsavel` inteiro
    aqui reescreveria `password` e `last_login` junto, e esta função não
    tem nada a ver com a credencial de ninguém.
    """
    responsavel = plano.pagador
    if responsavel is None:
        raise EmissaoRecusadaError(
            "Este plano não tem pagador definido. Escolha o responsável "
            "que recebe a cobrança antes de emitir."
        )
    if responsavel.id_externo_gateway:
        return Pagador(id_externo=responsavel.id_externo_gateway)

    pagador = gateway.criar_pagador(_dados_do_pagador(plano))
    responsavel.id_externo_gateway = pagador.id_externo
    responsavel.save(update_fields=["id_externo_gateway", "atualizado_em"])
    logger.info(
        "Pagador %s cadastrado no gateway como %s",
        responsavel.pk,
        pagador.id_externo,
    )
    return pagador


def emitir_cobranca(
    fatura: Fatura, gateway: CobrancaGateway, metodo: str = ""
) -> Fatura:
    """Cria a cobrança no provedor e guarda o ponteiro dela na fatura.

    **Idempotente pelo `id_externo`**: fatura que já foi emitida volta
    como está, sem criar segunda cobrança. É o que torna seguro repetir o
    command do lote e clicar duas vezes no botão — e a razão de a
    verificação vir antes de qualquer chamada HTTP.

    **Fora de transação, e de propósito.** A chamada é de rede: manter
    uma transação aberta enquanto o Asaas responde prenderia o lock da
    fatura pelo tempo deles, e no lote uma falha no aluno 40 desfaria os
    39 que já tinham cobrança criada lá — cobrança que continuaria
    existindo no provedor, agora órfã. Por isso o `save` é pontual, nos
    dois campos que esta função escreve.

    Fatura cancelada ou paga não vai pro gateway: emitir cobrança do que
    a escola já baixou ou já recebeu é pedir dinheiro duas vezes.
    """
    if fatura.id_externo:
        logger.info(
            "Fatura %s já emitida no gateway (%s) — emissão ignorada",
            fatura.pk,
            fatura.id_externo,
        )
        return fatura

    if fatura.status in (Fatura.Status.CANCELADO, Fatura.Status.PAGO):
        raise EmissaoRecusadaError(
            f"Fatura {fatura.get_status_display().lower()} não pode ser "
            "enviada para cobrança."
        )

    plano = fatura.plano
    pagador = _pagador_no_gateway(plano, gateway)

    cobranca = gateway.criar_cobranca(
        DadosCobranca(
            pagador=pagador,
            valor=fatura.valor,
            vencimento=fatura.vencimento,
            descricao=f"Mensalidade {fatura.competencia:%m/%Y} — {fatura.aluno}",
            metodo=metodo,
            # O id da fatura é o que permite achar a fatura a partir de um
            # evento do provedor sem confiar no corpo dele.
            referencia_externa=str(fatura.pk),
            multa_percentual=plano.multa_percentual,
            juros_mes_percentual=plano.juros_mes_percentual,
        )
    )

    fatura.id_externo = cobranca.id_externo
    fatura.link_pagamento = cobranca.link_pagamento
    fatura.save(update_fields=["id_externo", "link_pagamento", "atualizado_em"])
    logger.info(
        "Cobrança %s criada no gateway para a fatura %s",
        cobranca.id_externo,
        fatura.pk,
    )
    return fatura


def cancelar_cobranca(fatura: Fatura, gateway: CobrancaGateway) -> bool:
    """Cancela no provedor a cobrança da fatura. Devolve se chegou a cancelar.

    **Falha não propaga.** Quem chama é o cancelamento da fatura, que é
    decisão administrativa já tomada: deixar o `DELETE` do provedor
    derrubar a requisição faria a secretaria não conseguir cancelar uma
    fatura por indisponibilidade de terceiro. O preço de engolir é a
    família poder receber lembrete de uma cobrança baixada aqui — visível
    no log e no Sentry, e corrigível na mão no painel deles.

    Limpa `id_externo` e `link_pagamento` no sucesso: o link morto não
    ajuda ninguém, e liberar o `id_externo` é o que permite reemitir a
    competência depois sem bater no unique parcial da fatura.
    """
    if not fatura.id_externo:
        return False
    try:
        gateway.cancelar_cobranca(fatura.id_externo)
    except ErroDeGateway:
        logger.exception(
            "Falha ao cancelar no gateway a cobrança %s (fatura %s)",
            fatura.id_externo,
            fatura.pk,
        )
        return False

    fatura.id_externo = ""
    fatura.link_pagamento = ""
    fatura.save(update_fields=["id_externo", "link_pagamento", "atualizado_em"])
    return True


# ====================================================================== #
# Conciliação a partir do gateway                                        #
# ====================================================================== #


def conciliar_cobranca(
    fatura: Fatura, gateway: CobrancaGateway
) -> Pagamento | None:
    """Reconsulta a cobrança no provedor e registra o pagamento, se houver.

    **Reconsulta em vez de confiar no corpo do evento** (`FINANCEIRO.md`
    §6). O corpo do webhook é entrada não autenticada em termos de
    conteúdo: o token prova quem mandou, não que o valor ali é o valor
    que entrou. Quem decide quanto foi pago é o `GET` na cobrança.

    Devolve `None` quando não há o que conciliar — cobrança ainda
    pendente, vencida, cancelada, ou num estado intermediário de
    confirmação que pode virar estorno (o `CONFIRMED` do Asaas, que fica
    até 72h assim). Nenhum desses é erro: é o caminho normal dos eventos
    que não são liquidação.

    A `referencia_externa` do pagamento é o **id da cobrança**, não o do
    evento. É o que garante um pagamento por cobrança: dois eventos
    diferentes do mesmo pagamento (confirmação e recebimento, ou a
    reentrega de um deles) convergem pra mesma referência e o
    `registrar_pagamento` devolve o pagamento que já existe em vez de
    lançar outro.
    """
    cobranca = gateway.consultar_cobranca(fatura.id_externo)

    if cobranca.situacao != SituacaoCobranca.PAGO:
        logger.info(
            "Fatura %s: cobrança %s em %s — nada a conciliar",
            fatura.pk,
            cobranca.id_externo,
            cobranca.situacao.value,
        )
        return None

    # Liquidada sem valor é resposta que não entendemos; registrar o valor
    # de face seria inventar quanto entrou.
    if cobranca.valor_pago is None:
        raise ErroDeGateway(
            f"Cobrança {cobranca.id_externo} veio paga sem valor pago."
        )

    return registrar_pagamento(
        fatura,
        valor=cobranca.valor_pago,
        # Sem data do provedor, hoje: o pagamento existe e precisa de uma
        # data: `Pagamento.data` é obrigatório, e recusar o lançamento por
        # falta de um campo acessório deixaria a fatura aberta com
        # dinheiro recebido.
        data=cobranca.data_pagamento or date.today(),
        metodo=cobranca.metodo or Pagamento.Metodo.OUTRO,
        referencia_externa=cobranca.id_externo,
    )
