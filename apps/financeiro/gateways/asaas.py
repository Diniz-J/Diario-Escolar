"""Integração com o Asaas — transporte HTTP e adaptador do contrato.

Duas camadas, nesta ordem: `ClienteAsaas` monta a requisição, escolhe o
ambiente e traduz falha em exceção nossa; `GatewayAsaas` implementa o
`CobrancaGateway` de `base.py`, traduzindo campo e status.

Escrito contra a documentação deles (o OpenAPI de `docs.asaas.com`), não
de memória — que é o que o `FINANCEIRO.md` §6 exige. As pegadinhas que
só aparecem lendo o contrato real (o `DELETE` que não devolve a cobrança,
`deleted` ganhando do `status`, `value` em vez de `netValue`, `interest`
sem `type`) estão registradas no `FINANCEIRO.md` §6 e nos comentários dos
pontos em que importam.

Três coisas que a documentação deles obriga e não são óbvias:

- **`User-Agent` é obrigatório** para contas raiz criadas a partir de
  13/06/2024. Sem ele a requisição é recusada, e o erro não diz isso.
- **Chave e ambiente andam juntos.** Chave de produção em URL de sandbox
  (ou o contrário) devolve 401 `invalid_environment`, não um erro de
  rede. Por isso os dois saem da mesma configuração.
- **O corpo de erro é sempre `errors: [{code, description}]`**, inclusive
  nos 401. É de lá que sai a mensagem que a secretaria lê.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any

import httpx
from django.conf import settings

from .base import (
    Cobranca,
    CobrancaGateway,
    DadosCobranca,
    DadosPagador,
    ErroPermanente,
    ErroTemporario,
    Pagador,
    SituacaoCobranca,
)

logger = logging.getLogger(__name__)

SANDBOX = "https://api-sandbox.asaas.com/v3"
PRODUCAO = "https://api.asaas.com/v3"

# Timeout curto: a cobrança é criada dentro de uma request da secretaria,
# e pendurar o worker esperando o Asaas é pior que falhar e deixar ela
# tentar de novo. Mesmo princípio do `EMAIL_TIMEOUT`.
TIMEOUT_PADRAO = 10


# O Asaas tem catorze status; a `Fatura` tem quatro. A redução é
# conservadora por decisão de produto: só o que é dinheiro liquidado e
# irreversível pelo fluxo normal vira `PAGO`.
#
# `CONFIRMED` é o caso que justifica a regra. A documentação deles avisa
# que, em conta de pessoa física, um Pix pode ficar `CONFIRMED` por até
# 72h em bloqueio cautelar e depois virar `RECEIVED` **ou `REFUNDED`**.
# Conciliar ali marcaria como paga uma fatura que ainda pode ser
# estornada — então `CONFIRMED` é pendente, e só sai disso quando vira
# `RECEIVED`.
#
# A mesma lógica joga disputa, análise de risco e pedido de estorno pra
# `PENDENTE`: nenhum deles é dinheiro no caixa, e nenhum é o fim da
# linha. `REFUNDED` e `CHARGEBACK_*` resolvidos contra nós não viram
# `CANCELADO`: a fatura continua devida, o que mudou foi o pagamento.
SITUACAO_POR_STATUS: dict[str, SituacaoCobranca] = {
    "PENDING": SituacaoCobranca.PENDENTE,
    "AWAITING_RISK_ANALYSIS": SituacaoCobranca.PENDENTE,
    "CONFIRMED": SituacaoCobranca.PENDENTE,
    "RECEIVED": SituacaoCobranca.PAGO,
    "RECEIVED_IN_CASH": SituacaoCobranca.PAGO,
    "OVERDUE": SituacaoCobranca.VENCIDO,
    "REFUNDED": SituacaoCobranca.PENDENTE,
    "REFUND_REQUESTED": SituacaoCobranca.PENDENTE,
    "REFUND_IN_PROGRESS": SituacaoCobranca.PENDENTE,
    "CHARGEBACK_REQUESTED": SituacaoCobranca.PENDENTE,
    "CHARGEBACK_DISPUTE": SituacaoCobranca.PENDENTE,
    "AWAITING_CHARGEBACK_REVERSAL": SituacaoCobranca.PENDENTE,
    "DUNNING_REQUESTED": SituacaoCobranca.PENDENTE,
    "DUNNING_RECEIVED": SituacaoCobranca.PAGO,
}

_CENTAVOS = Decimal("0.01")


def situacao_de(status: str) -> SituacaoCobranca:
    """Traduz o status do Asaas pro vocabulário da `Fatura`.

    Status desconhecido vira `PENDENTE` e é logado: o Asaas pode
    acrescentar estado sem avisar, e a alternativa (estourar) derrubaria
    a conciliação de todas as faturas por causa de uma. Pendente é o
    estado seguro — não escreve dinheiro e não cancela nada.
    """
    situacao = SITUACAO_POR_STATUS.get(status)
    if situacao is None:
        logger.warning("Status desconhecido do Asaas: %s", status)
        return SituacaoCobranca.PENDENTE
    return situacao


def valor_para_json(valor: Decimal) -> float:
    """Converte dinheiro pro `number` que o JSON deles espera.

    O campo `value` é declarado `number`, e `json.dumps` não serializa
    `Decimal`. Arredonda pra centavo antes de converter: nessa faixa
    (o modelo tem `max_digits=10`, ou seja, no máximo 99999999.99) todo
    valor de dois decimais tem representação exata o bastante pra que o
    `json` emita de volta o mesmo decimal. O arredondamento é o comercial
    do módulo (`ROUND_HALF_UP`), não o bancário que o float faria
    sozinho.
    """
    return float(valor.quantize(_CENTAVOS, rounding=ROUND_HALF_UP))


class ClienteAsaas:
    """Cliente HTTP fino do Asaas.

    Fino de propósito: não existe SDK Python maduro (`FINANCEIRO.md` §6),
    e um wrapper grande em cima de quatro chamadas seria mais código pra
    manter do que as chamadas. O que ele faz é o que toda chamada precisa
    — header, ambiente, timeout e tradução de erro.

    Sem chave configurada o cliente ainda **constrói**, e só falha ao
    chamar. É o mesmo princípio do Sentry: ambiente sem a env não pode
    quebrar o boot, porque o financeiro funciona sem gateway (a escola
    registra Pix e dinheiro na mão).
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout: float | None = None,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.api_key = (
            api_key
            if api_key is not None
            else getattr(settings, "ASAAS_API_KEY", "")
        )
        self.base_url = (
            base_url
            if base_url is not None
            else getattr(settings, "ASAAS_BASE_URL", SANDBOX)
        )
        self.timeout = (
            timeout
            if timeout is not None
            else getattr(settings, "ASAAS_TIMEOUT", TIMEOUT_PADRAO)
        )
        # Injetável pra teste: `httpx.MockTransport` responde sem rede.
        self._transport = transport

    def _headers(self) -> dict[str, str]:
        return {
            "Content-Type": "application/json",
            # Obrigatório desde 13/06/2024 pra contas raiz novas.
            "User-Agent": "diario-escolar",
            "access_token": self.api_key,
        }

    def post(self, caminho: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self._requisitar("POST", caminho, json=payload)

    def get(
        self, caminho: str, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        return self._requisitar("GET", caminho, params=params)

    def delete(self, caminho: str) -> dict[str, Any]:
        return self._requisitar("DELETE", caminho)

    def _requisitar(
        self, metodo: str, caminho: str, **kwargs: Any
    ) -> dict[str, Any]:
        if not self.api_key:
            raise ErroPermanente(
                "Cobrança online não está configurada: falta a chave do "
                "Asaas (ASAAS_API_KEY).",
                "sem_chave",
            )
        url = f"{self.base_url}{caminho}"
        try:
            with httpx.Client(
                timeout=self.timeout, transport=self._transport
            ) as cliente:
                resposta = cliente.request(
                    metodo, url, headers=self._headers(), **kwargs
                )
        except httpx.TimeoutException as exc:
            # Timeout é o caso que mais se repete e o que mais vale
            # retentar: a cobrança pode até ter sido criada do lado de lá.
            raise ErroTemporario(
                "O Asaas não respondeu a tempo. Tente de novo.", "timeout"
            ) from exc
        except httpx.HTTPError as exc:
            raise ErroTemporario(
                "Não foi possível falar com o Asaas.", "falha_de_rede"
            ) from exc

        return self._interpretar(resposta)

    def _interpretar(self, resposta: httpx.Response) -> dict[str, Any]:
        """Transforma a resposta em dados ou em exceção nossa.

        A divisão entre temporário e permanente é pela natureza da falha,
        não pelo texto: 5xx e 429 passam com o tempo, 4xx não passa sem
        alguém corrigir o payload ou a chave.
        """
        if resposta.is_success:
            return self._corpo(resposta)

        codigo, descricao = self._erro_do_corpo(resposta)
        if resposta.status_code == 429:
            raise ErroTemporario(
                descricao or "Limite de requisições do Asaas atingido.",
                codigo or "rate_limit",
            )
        if resposta.status_code >= 500:
            raise ErroTemporario(
                descricao or "O Asaas está indisponível.",
                codigo or "indisponivel",
            )
        raise ErroPermanente(
            descricao or f"O Asaas recusou a requisição ({resposta.status_code}).",
            codigo,
        )

    @staticmethod
    def _corpo(resposta: httpx.Response) -> dict[str, Any]:
        """Lê o JSON da resposta.

        `DELETE` pode vir sem corpo; um 200 vazio não é erro, é ausência
        de dados. Corpo que deveria ser JSON e não é significa que quem
        respondeu não foi a API (proxy, página de manutenção) — isso é
        temporário, não payload inválido nosso.
        """
        if not resposta.content:
            return {}
        try:
            return resposta.json()
        except ValueError as exc:
            raise ErroTemporario(
                "O Asaas respondeu em formato inesperado.", "resposta_invalida"
            ) from exc

    @staticmethod
    def _erro_do_corpo(resposta: httpx.Response) -> tuple[str, str]:
        """Extrai `code` e `description` do primeiro erro do corpo.

        O formato é sempre `{"errors": [{"code", "description"}]}`, mas um
        502 de proxy vem em HTML — por isso nada aqui pode estourar: a
        falha real é o status, e o corpo é só detalhe.
        """
        try:
            dados = resposta.json()
        except ValueError:
            return "", ""
        erros = dados.get("errors") if isinstance(dados, dict) else None
        if not erros:
            return "", ""
        primeiro = erros[0]
        if not isinstance(primeiro, dict):
            return "", ""
        return primeiro.get("code", ""), primeiro.get("description", "")


# `billingType` que o Asaas devolve traduzido pro vocabulário do
# `Pagamento.Metodo`. `DEBIT_CARD` cai em `cartao` junto do crédito: a
# distinção não muda nada no contas a receber.
#
# `TRANSFER`, `DEPOSIT` e `UNDEFINED` caem em `OUTRO`, e o caso é real,
# não defensivo: a doc deles diz que um valor que entra na conta Asaas
# por Pix ou TED é associado a uma cobrança existente, então a
# mensalidade criada com `UNDEFINED` (pagador escolhe) pode voltar paga
# por um meio que o nosso enum não modela. Chutar `boleto` ali gravaria
# fato errado numa tabela de dinheiro auditada.
# Os valores são os de `Pagamento.Metodo` escritos à mão, e não
# importados: a camada de gateway não importa model (mesma razão pela qual
# `SituacaoCobranca` existe em vez de reusar `Fatura.Status`). Um teste
# trava os dois conjuntos juntos, que é como o projeto já garante o par.
METODO_POR_BILLING_TYPE: dict[str, str] = {
    "PIX": "pix",
    "BOLETO": "boleto",
    "CREDIT_CARD": "cartao",
    "DEBIT_CARD": "cartao",
}

METODO_OUTRO = "outro"

# O que mandamos quando a cobrança é criada. `UNDEFINED` é o default de
# propósito: mensalidade é o caso em que a família decide na hora entre
# Pix e boleto, e fixar o meio na emissão tiraria essa escolha.
BILLING_TYPE_POR_METODO: dict[str, str] = {
    "pix": "PIX",
    "boleto": "BOLETO",
    "cartao": "CREDIT_CARD",
}


def metodo_de(billing_type: str) -> str:
    """Traduz o `billingType` deles pro valor de `Pagamento.Metodo`."""
    return METODO_POR_BILLING_TYPE.get(billing_type, METODO_OUTRO)


def _sem_vazios(payload: dict[str, Any]) -> dict[str, Any]:
    """Remove as chaves vazias do payload.

    Mandar `"email": ""` não é o mesmo que omitir o campo: o Asaas valida
    o formato do que recebe e recusaria a requisição por causa de um
    opcional que a escola simplesmente não preencheu.
    """
    return {k: v for k, v in payload.items() if v not in ("", None)}


def _data_de(valor: Any) -> date | None:
    """Lê uma data do JSON deles, tolerando ausência e data com hora.

    Os campos de cobrança vêm como `YYYY-MM-DD`, mas o mesmo corpo traz
    `dateCreated` do evento como `YYYY-MM-DD HH:MM:SS` — cortar em dez
    caracteres atende os dois sem precisar saber qual é qual. Formato
    inesperado devolve `None` em vez de estourar: data ilegível não pode
    derrubar a conciliação de uma fatura cujo valor e status estão
    legíveis.
    """
    if not isinstance(valor, str) or not valor:
        return None
    try:
        return date.fromisoformat(valor[:10])
    except ValueError:
        logger.warning("Data ilegível vinda do Asaas: %r", valor)
        return None


def _decimal_de(valor: Any) -> Decimal | None:
    """Converte o `number` do JSON em `Decimal` sem passar por float.

    `Decimal(str(100.1))` dá `100.1`; `Decimal(100.1)` dá a dízima do
    binário. Como o valor já chegou como float no parse do JSON, o `str`
    é o que recupera o decimal que eles emitiram.
    """
    if valor is None:
        return None
    try:
        return Decimal(str(valor)).quantize(_CENTAVOS, rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError):
        logger.warning("Valor ilegível vindo do Asaas: %r", valor)
        return None


class GatewayAsaas(CobrancaGateway):
    """Adaptador do Asaas pro contrato de `base.py`.

    Tudo que é dialeto deles mora aqui: nomes de campo, `billingType`,
    catálogo de status. Quem chama fala só `DadosCobranca`/`Cobranca`.

    O cliente HTTP é injetável pra que o teste use
    `httpx.MockTransport` e nenhuma suíte dependa de rede.
    """

    def __init__(self, cliente: ClienteAsaas | None = None) -> None:
        self.cliente = cliente or ClienteAsaas()

    # ------------------------------------------------------------------ #
    # Pagador                                                            #
    # ------------------------------------------------------------------ #

    def criar_pagador(self, dados: DadosPagador) -> Pagador:
        corpo = self.cliente.post(
            "/customers",
            _sem_vazios(
                {
                    "name": dados.nome,
                    "cpfCnpj": dados.documento,
                    "email": dados.email,
                    "mobilePhone": dados.telefone,
                    "externalReference": dados.referencia_externa,
                }
            ),
        )
        # `notificationDisabled` não é enviado: o default do Asaas avisa a
        # família do vencimento, e lembrete de vencimento é coisa que o
        # sistema não faz. Desligar lá sem ter substituto aqui só tiraria
        # aviso de quem paga.
        return Pagador(id_externo=self._id_obrigatorio(corpo, "pagador"))

    # ------------------------------------------------------------------ #
    # Cobrança                                                           #
    # ------------------------------------------------------------------ #

    def criar_cobranca(self, dados: DadosCobranca) -> Cobranca:
        payload: dict[str, Any] = {
            "customer": dados.pagador.id_externo,
            "billingType": BILLING_TYPE_POR_METODO.get(dados.metodo, "UNDEFINED"),
            "value": valor_para_json(dados.valor),
            "dueDate": dados.vencimento.isoformat(),
            "description": dados.descricao,
            "externalReference": dados.referencia_externa,
        }
        # Multa e juros só entram se o contrato tiver cláusula: mandar zero
        # é o mesmo que não mandar, e payload menor é menos superfície pra
        # eles recusarem.
        if dados.multa_percentual > 0:
            payload["fine"] = {
                "value": valor_para_json(dados.multa_percentual),
                # Percentual, não valor fixo: é como a cláusula é escrita
                # no plano (`multa_percentual`).
                "type": "PERCENTAGE",
            }
        if dados.juros_mes_percentual > 0:
            # `interest` aceita só `value`, e ele já é entendido como
            # percentual ao mês — não existe `type` aqui, ao contrário do
            # `fine`. Mandar `type` faria o Asaas recusar.
            payload["interest"] = {
                "value": valor_para_json(dados.juros_mes_percentual)
            }

        corpo = self.cliente.post("/payments", _sem_vazios(payload))
        return self._cobranca_de(corpo)

    def consultar_cobranca(self, id_externo: str) -> Cobranca:
        corpo = self.cliente.get(f"/payments/{id_externo}")
        return self._cobranca_de(corpo)

    def cancelar_cobranca(self, id_externo: str) -> Cobranca:
        """Remove a cobrança e devolve como ela ficou.

        São duas chamadas porque o `DELETE` deles responde só
        `{deleted, id}` — não a cobrança — e o contrato promete uma
        `Cobranca` com valor e vencimento. A releitura também é o que
        confirma o cancelamento no estado real, em vez de na nossa
        suposição.

        Consequência pra quem chama: se o `DELETE` passar e a releitura
        falhar (rede), isto levanta erro embora a cobrança já esteja
        cancelada lá. Cancelar a fatura **aqui** não pode depender disso,
        então o `services.py` trata a falha como aviso, não como bloqueio.
        """
        corpo = self.cliente.delete(f"/payments/{id_externo}")
        if corpo.get("deleted") is not True:
            raise ErroPermanente(
                "O Asaas não confirmou a remoção da cobrança.",
                "remocao_nao_confirmada",
            )
        return self.consultar_cobranca(id_externo)

    # ------------------------------------------------------------------ #
    # Tradução de resposta                                               #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _id_obrigatorio(corpo: dict[str, Any], o_que: str) -> str:
        """Lê o `id` da resposta, que é o único campo sem o qual nada serve.

        Sucesso sem id é resposta que não entendemos — temporário, não
        permanente: repetir pode trazer uma resposta íntegra, e tratar
        como permanente deixaria a escola sem cobrança e sem motivo.
        """
        id_externo = corpo.get("id") or ""
        if not id_externo:
            raise ErroTemporario(
                f"O Asaas respondeu sem o id do {o_que}.", "resposta_sem_id"
            )
        return str(id_externo)

    def _cobranca_de(self, corpo: dict[str, Any]) -> Cobranca:
        """Monta a `Cobranca` do contrato a partir do JSON deles.

        Duas traduções que não se deduzem dos nomes dos campos:

        - **`deleted` ganha do `status`.** Cobrança removida continua
          respondendo o status que tinha (`PENDING`, por exemplo), então
          ler só o status faria uma cobrança cancelada voltar como
          pendente — e a conciliação trataria como viva algo que a escola
          já baixou.
        - **o valor pago é `value`, não `netValue`.** `netValue` é o
          líquido depois da tarifa deles, que é menor do que a família
          pagou; usá-lo deixaria toda fatura com saldo residual. Quando o
          pagamento sai diferente do original (atraso com multa), é
          `originalValue` que guarda o original e `value` que traz o
          efetivamente pago — ou seja, `value` é o certo nos dois casos.
        """
        situacao = (
            SituacaoCobranca.CANCELADO
            if corpo.get("deleted") is True
            else situacao_de(str(corpo.get("status") or ""))
        )
        valor = _decimal_de(corpo.get("value")) or Decimal("0.00")

        # Só faz sentido falar de valor pago quando houve liquidação; zero
        # seria ambíguo com estorno total (ver `Cobranca`).
        valor_pago = valor if situacao == SituacaoCobranca.PAGO else None

        # `clientPaymentDate` é quando a família pagou; `paymentDate` é
        # quando liquidou no Asaas. A primeira é a que vale como prova de
        # quitação pro responsável, então ela vem na frente — a segunda é
        # o fallback pros meios em que a primeira não existe.
        data_pagamento = _data_de(corpo.get("clientPaymentDate")) or _data_de(
            corpo.get("paymentDate")
        )

        vencimento = _data_de(corpo.get("dueDate"))
        if vencimento is None:
            # O contrato promete uma data; sem ela a `Cobranca` mentiria o
            # tipo. Temporário pelo mesmo motivo do id ausente.
            raise ErroTemporario(
                "O Asaas respondeu sem o vencimento da cobrança.",
                "resposta_sem_vencimento",
            )

        return Cobranca(
            id_externo=self._id_obrigatorio(corpo, "cobrança"),
            situacao=situacao,
            valor=valor,
            vencimento=vencimento,
            link_pagamento=str(corpo.get("invoiceUrl") or ""),
            valor_pago=valor_pago,
            data_pagamento=data_pagamento,
            # Só faz sentido falar de meio de pagamento depois de pago: a
            # cobrança criada como `UNDEFINED` ainda não tem um, e
            # traduzi-lo ali gravaria "outro" como se fosse fato.
            metodo=(
                metodo_de(str(corpo.get("billingType") or ""))
                if situacao == SituacaoCobranca.PAGO
                else ""
            ),
        )


@dataclass(frozen=True)
class EventoAsaas:
    """Um evento de webhook do Asaas, reduzido ao que a conciliação usa.

    Mora aqui, e não em `base.py`, porque a forma do corpo é deles. O
    endpoint também é por provedor (`/webhooks/asaas/`): um segundo
    gateway ganha a sua própria rota em vez de disputar esta, e assim o
    parsing nunca precisa adivinhar de quem é o corpo.

    `referencia_externa` é o id da `Fatura` que mandamos na criação, e é
    por ele que a fatura é achada — não pelo corpo, que não é confiável
    pra valor (`FINANCEIRO.md` §6).
    """

    id_evento: str
    tipo: str
    id_cobranca: str
    referencia_externa: str = ""


def ler_evento(corpo: dict[str, Any]) -> EventoAsaas:
    """Extrai de um corpo de webhook o que importa, ou recusa o corpo.

    Recusa (`ErroPermanente`) o corpo sem id de evento ou sem cobrança:
    sem o primeiro não há como deduplicar a reentrega, e sem o segundo não
    há o que conciliar. Repetir não conserta nenhum dos dois, daí
    permanente.
    """
    id_evento = str(corpo.get("id") or "")
    pagamento = corpo.get("payment")
    if not isinstance(pagamento, dict):
        pagamento = {}
    id_cobranca = str(pagamento.get("id") or "")

    if not id_evento or not id_cobranca:
        raise ErroPermanente(
            "Corpo de webhook sem id de evento ou de cobrança.",
            "corpo_invalido",
        )

    return EventoAsaas(
        id_evento=id_evento,
        tipo=str(corpo.get("event") or ""),
        id_cobranca=id_cobranca,
        referencia_externa=str(pagamento.get("externalReference") or ""),
    )
