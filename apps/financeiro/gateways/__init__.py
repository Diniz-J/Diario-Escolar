"""Integração com gateway de cobrança.

`base.py` define o contrato; cada provedor entra como um módulo irmão
(`asaas.py`). O resto do financeiro importa daqui, nunca do provedor —
é o que mantém "trocar de gateway" como troca de uma classe.
"""
from .base import (
    Cobranca,
    CobrancaGateway,
    DadosCobranca,
    DadosPagador,
    ErroDeGateway,
    ErroPermanente,
    ErroTemporario,
    Pagador,
    SituacaoCobranca,
)

__all__ = [
    "Cobranca",
    "CobrancaGateway",
    "DadosCobranca",
    "DadosPagador",
    "ErroDeGateway",
    "ErroPermanente",
    "ErroTemporario",
    "Pagador",
    "SituacaoCobranca",
    "gateway_configurado",
]


def gateway_configurado() -> CobrancaGateway | None:
    """Devolve o gateway da escola, ou `None` quando não há cobrança online.

    `None` não é erro: o módulo financeiro funciona sem gateway — a escola
    cadastra o plano, o cron gera a fatura e a secretaria registra o Pix
    ou o dinheiro que recebeu (`FINANCEIRO.md` §9). Quem chama decide o
    que fazer com a ausência; a API devolve 400 explicando, o command
    pula.

    Um provedor só por enquanto. Quando houver dois, o que muda aqui é a
    escolha (env ou campo na `Escola`), não a assinatura — é pra isso que
    o retorno é o tipo do contrato e não a classe do Asaas.
    """
    from django.conf import settings

    from .asaas import GatewayAsaas

    if not getattr(settings, "ASAAS_API_KEY", ""):
        return None
    return GatewayAsaas()
