"""Validadores reutilizáveis."""
import re

from django.core.exceptions import ValidationError


_DIGITOS = re.compile(r"\D")
_PESOS_PRIMEIRO = (5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2)
_PESOS_SEGUNDO = (6,) + _PESOS_PRIMEIRO
# CPF usa pesos decrescentes simples, mas a conta do DV é a mesma do
# CNPJ — por isso os dois compartilham `_calcula_dv`.
_PESOS_CPF_PRIMEIRO = tuple(range(10, 1, -1))
_PESOS_CPF_SEGUNDO = (11,) + _PESOS_CPF_PRIMEIRO


def apenas_digitos(valor: str) -> str:
    """Descarta tudo que não for dígito. Usado pra normalizar documento.

    Público porque o gateway de cobrança também precisa (manda CPF sem
    máscara) — duas implementações disso divergiriam na primeira máscara
    nova.
    """
    return _DIGITOS.sub("", valor or "")


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


def validar_cpf(valor: str) -> None:
    """Valida CPF pelos dois dígitos verificadores.

    Aceita com ou sem máscara: ``"123.456.789-09"`` ou ``"12345678909"``.
    Levanta ``ValidationError`` se o tamanho estiver errado, se for
    sequência repetida (``"11111111111"`` passa nos dois DVs e é o CPF
    falso mais digitado) ou se qualquer DV falhar.

    Existe porque o gateway de cobrança exige documento do pagador e
    recusa remotamente o que estiver malformado — validar aqui troca um
    erro de API por uma mensagem na tela de cadastro.
    """
    if not valor:
        return
    digitos = _DIGITOS.sub("", valor)
    if len(digitos) != 11:
        raise ValidationError("CPF deve ter 11 dígitos.", code="cpf_tamanho")
    if digitos == digitos[0] * 11:
        raise ValidationError("CPF inválido.", code="cpf_repetido")
    if int(digitos[9]) != _calcula_dv(digitos[:9], _PESOS_CPF_PRIMEIRO):
        raise ValidationError("CPF inválido.", code="cpf_dv1")
    if int(digitos[10]) != _calcula_dv(digitos[:10], _PESOS_CPF_SEGUNDO):
        raise ValidationError("CPF inválido.", code="cpf_dv2")
