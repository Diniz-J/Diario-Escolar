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
]
