"""Testes dos helpers compartilhados de PDF.

`slug_arquivo` vai cru pra dentro de `Content-Disposition:
attachment; filename="..."`, então o que ela deixa passar vira header.
"""
from django.test import SimpleTestCase

from apps.common.pdf import slug_arquivo


class SlugArquivoTests(SimpleTestCase):
    def test_tira_acento(self):
        self.assertEqual(
            slug_arquivo("Ensino Médio A", fallback="turma"),
            "ensino_medio_a",
        )

    def test_aspa_nao_passa(self):
        """Com a aspa, o `filename="..."` fecharia no meio do nome."""
        self.assertEqual(
            slug_arquivo('Turma "X"', fallback="turma"), "turma_x"
        )

    def test_barra_e_contrabarra_nao_passam(self):
        self.assertEqual(slug_arquivo("A/B", fallback="turma"), "a_b")
        self.assertEqual(
            slug_arquivo("nome\\com\\barra", fallback="turma"),
            "nome_com_barra",
        )

    def test_quebra_de_linha_nao_passa(self):
        """Newline no header separaria um cabeçalho novo."""
        self.assertEqual(
            slug_arquivo("1A\nX-Injetado: 1", fallback="turma"),
            "1a_x-injetado_1",
        )

    def test_so_sobra_caractere_seguro(self):
        resultado = slug_arquivo("a;b,c<d>e|f*g?h", fallback="turma")
        self.assertEqual(resultado, "a_b_c_d_e_f_g_h")

    def test_vazio_e_so_separador_caem_no_fallback(self):
        for entrada in (None, "", "   ", "///", "???"):
            self.assertEqual(
                slug_arquivo(entrada, fallback="turma"),
                "turma",
                f"entrada {entrada!r}",
            )
