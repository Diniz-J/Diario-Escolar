"""Testes do validador de CNPJ."""
from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from apps.common.validators import validar_cnpj


class ValidarCnpjTests(SimpleTestCase):
    def test_cnpj_valido_sem_mascara(self):
        validar_cnpj("11444777000161")  # não levanta

    def test_cnpj_valido_com_mascara(self):
        validar_cnpj("11.444.777/0001-61")

    def test_cnpj_vazio_passa(self):
        """`blank=True` chega aqui como string vazia ou None — validador silencia."""
        validar_cnpj("")
        validar_cnpj(None)  # type: ignore[arg-type]

    def test_cnpj_tamanho_incorreto(self):
        with self.assertRaises(ValidationError) as ctx:
            validar_cnpj("12345")
        self.assertEqual(ctx.exception.code, "cnpj_tamanho")

    def test_cnpj_repetido(self):
        with self.assertRaises(ValidationError) as ctx:
            validar_cnpj("11111111111111")
        self.assertEqual(ctx.exception.code, "cnpj_repetido")

    def test_cnpj_dv_invalido(self):
        with self.assertRaises(ValidationError) as ctx:
            validar_cnpj("12345678000199")
        self.assertIn(ctx.exception.code, {"cnpj_dv1", "cnpj_dv2"})

    def test_apenas_letras_levanta_tamanho(self):
        with self.assertRaises(ValidationError) as ctx:
            validar_cnpj("abc")
        self.assertEqual(ctx.exception.code, "cnpj_tamanho")
