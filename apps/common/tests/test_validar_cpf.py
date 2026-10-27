"""Testes do validador de CPF.

O CPF entrou porque o gateway de cobrança exige documento do pagador e
recusa remotamente o que estiver malformado. Validar aqui só vale se
pegar o que o gateway pegaria — por isso os casos abaixo cobrem os dois
dígitos verificadores separadamente, e não só "número feio".
"""
from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from apps.common.validators import apenas_digitos, validar_cpf


class ValidarCpfTests(SimpleTestCase):
    def test_aceita_cpf_valido_sem_mascara(self):
        validar_cpf("52998224725")

    def test_aceita_cpf_valido_com_mascara(self):
        """A máscara chega do formulário; tirar dígito é trabalho daqui."""
        validar_cpf("529.982.247-25")

    def test_vazio_passa(self):
        """O campo é opcional: só quem vai cobrar precisa preencher."""
        validar_cpf("")

    def test_tamanho_errado(self):
        with self.assertRaises(ValidationError) as ctx:
            validar_cpf("123456789")
        self.assertEqual(ctx.exception.code, "cpf_tamanho")

    def test_sequencia_repetida(self):
        """`11111111111` passa nos dois DVs — sem este caso, entraria.

        É o CPF falso mais digitado, então é exatamente o que apareceria
        num cadastro preenchido de qualquer jeito.
        """
        with self.assertRaises(ValidationError) as ctx:
            validar_cpf("111.111.111-11")
        self.assertEqual(ctx.exception.code, "cpf_repetido")

    def test_primeiro_dv_errado(self):
        # 52998224725 é válido; trocar o 10º dígito quebra só o 1º DV.
        with self.assertRaises(ValidationError) as ctx:
            validar_cpf("52998224715")
        self.assertEqual(ctx.exception.code, "cpf_dv1")

    def test_segundo_dv_errado(self):
        # Mantém o 1º DV correto e quebra só o 2º.
        with self.assertRaises(ValidationError) as ctx:
            validar_cpf("52998224724")
        self.assertEqual(ctx.exception.code, "cpf_dv2")


class ApenasDigitosTests(SimpleTestCase):
    def test_remove_mascara(self):
        self.assertEqual(apenas_digitos("529.982.247-25"), "52998224725")

    def test_tolera_vazio_e_none(self):
        """Chamado sobre campo `blank`, que chega como string vazia."""
        self.assertEqual(apenas_digitos(""), "")
        self.assertEqual(apenas_digitos(None), "")
