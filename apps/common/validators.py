"""Validadores reutilizáveis."""
import re

from django.core.exceptions import ValidationError


_DIGITOS = re.compile(r"\D")
_PESOS_PRIMEIRO = (5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2)
_PESOS_SEGUNDO = (6,) + _PESOS_PRIMEIRO


def _calcula_dv(digitos: str, pesos: tuple[int, ...]) -> int:
    soma = sum(int(d) * p for d, p in zip(digitos, pesos))
    resto = soma % 11
    return 0 if resto < 2 else 11 - resto


def validar_cnpj(valor: str) -> None:
    """Valida CNPJ pelos dois dígitos verificadores.

    Aceita formato com ou sem máscara: ``"12.345.678/0001-95"`` ou
    ``"12345678000195"``. Levanta ``ValidationError`` se o CNPJ tem tamanho
    incorreto, é uma sequência repetida (ex.: ``"11111111111111"``) ou se
    qualquer um dos DVs falha.
    """
    if not valor:
        return
    digitos = _DIGITOS.sub("", valor)
    if len(digitos) != 14:
        raise ValidationError("CNPJ deve ter 14 dígitos.", code="cnpj_tamanho")
    if digitos == digitos[0] * 14:
        raise ValidationError("CNPJ inválido.", code="cnpj_repetido")
    if int(digitos[12]) != _calcula_dv(digitos[:12], _PESOS_PRIMEIRO):
        raise ValidationError("CNPJ inválido.", code="cnpj_dv1")
    if int(digitos[13]) != _calcula_dv(digitos[:13], _PESOS_SEGUNDO):
        raise ValidationError("CNPJ inválido.", code="cnpj_dv2")
