"""Transporte HTTP do Asaas — a camada que fala com a API deles.

O que mora aqui é só o que não depende do formato das respostas de
cobrança: montar a requisição, escolher o ambiente, traduzir falha em
exceção nossa e converter o catálogo de status deles no nosso. A classe
que implementa `CobrancaGateway` entra junto com as quatro operações,
quando o contrato de resposta de `/payments` estiver em mãos — adaptador
escrito de memória é exatamente o que o `FINANCEIRO.md` §6 proíbe.

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
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

import httpx
from django.conf import settings

from .base import ErroPermanente, ErroTemporario, SituacaoCobranca

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
