"""Testes do modelo PeriodoAvaliativo.

Cobre invariantes que dependem do banco (constraints unique) e da
validação de domínio em `clean()` (ordenação de datas, não-sobreposição).
"""
from datetime import date

from django.core.exceptions import ValidationError
from django.db.utils import IntegrityError
from django.test import TestCase

from apps.avaliacao.models import PeriodoAvaliativo
from apps.escola.models import Escola


class PeriodoAvaliativoModelTests(TestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        cls.escola_a = Escola.objects.create(nome="Escola A")
        cls.escola_b = Escola.objects.create(nome="Escola B")

    # ------------------------------------------------------------------ #
    # Estado (placeholder)                                                #
    # ------------------------------------------------------------------ #

    def test_estado_inicial_eh_vazio(self):
        """Hoje todo período recém-criado é 'vazio' — não tem Avaliacao
        nem NotaPeriodo apontando pra ele ainda (modelos vêm em PRs seguintes)."""
        periodo = PeriodoAvaliativo.objects.create(
            escola=self.escola_a,
            nome="1º Bim",
            ordem=1,
            ano_letivo=2026,
            data_inicio=date(2026, 2, 1),
            data_fim=date(2026, 4, 30),
        )
        self.assertEqual(periodo.estado, PeriodoAvaliativo.ESTADO_VAZIO)

    # ------------------------------------------------------------------ #
    # Validação de datas                                                  #
    # ------------------------------------------------------------------ #

    def test_data_fim_anterior_data_inicio_falha(self):
        periodo = PeriodoAvaliativo(
            escola=self.escola_a,
            nome="1º Bim",
            ordem=1,
            ano_letivo=2026,
            data_inicio=date(2026, 4, 30),
            data_fim=date(2026, 2, 1),
        )
        with self.assertRaises(ValidationError) as ctx:
            periodo.clean()
        self.assertIn("data_fim", ctx.exception.message_dict)

    def test_data_fim_igual_data_inicio_falha(self):
        """Bordas: o sistema exige fim ESTRITAMENTE depois do início."""
        periodo = PeriodoAvaliativo(
            escola=self.escola_a,
            nome="1º Bim",
            ordem=1,
            ano_letivo=2026,
            data_inicio=date(2026, 2, 1),
            data_fim=date(2026, 2, 1),
        )
        with self.assertRaises(ValidationError):
            periodo.clean()

    # ------------------------------------------------------------------ #
    # Sobreposição                                                        #
    # ------------------------------------------------------------------ #

    def test_sobreposicao_no_mesmo_ano_falha(self):
        PeriodoAvaliativo.objects.create(
            escola=self.escola_a,
            nome="1º Bim",
            ordem=1,
            ano_letivo=2026,
            data_inicio=date(2026, 2, 1),
            data_fim=date(2026, 4, 30),
        )
        sobreposto = PeriodoAvaliativo(
            escola=self.escola_a,
            nome="2º Bim",
            ordem=2,
            ano_letivo=2026,
            data_inicio=date(2026, 4, 15),  # 15 dias dentro do 1º
            data_fim=date(2026, 6, 30),
        )
        with self.assertRaises(ValidationError) as ctx:
            sobreposto.clean()
        self.assertIn("data_inicio", ctx.exception.message_dict)

    def test_sobreposicao_em_anos_diferentes_passa(self):
        """Anos letivos distintos são escopos independentes."""
        PeriodoAvaliativo.objects.create(
            escola=self.escola_a,
            nome="1º Bim",
            ordem=1,
            ano_letivo=2026,
            data_inicio=date(2026, 2, 1),
            data_fim=date(2026, 4, 30),
        )
        outro = PeriodoAvaliativo(
            escola=self.escola_a,
            nome="1º Bim",
            ordem=1,
            ano_letivo=2027,
            data_inicio=date(2026, 2, 1),  # mesma data, ano diferente
            data_fim=date(2026, 4, 30),
        )
        outro.clean()  # não deve levantar

    def test_sobreposicao_em_escolas_diferentes_passa(self):
        """Escolas distintas são escopos independentes."""
        PeriodoAvaliativo.objects.create(
            escola=self.escola_a,
            nome="1º Bim",
            ordem=1,
            ano_letivo=2026,
            data_inicio=date(2026, 2, 1),
            data_fim=date(2026, 4, 30),
        )
        outro = PeriodoAvaliativo(
            escola=self.escola_b,
            nome="1º Bim",
            ordem=1,
            ano_letivo=2026,
            data_inicio=date(2026, 2, 1),
            data_fim=date(2026, 4, 30),
        )
        outro.clean()

    def test_edicao_do_proprio_periodo_nao_dispara_sobreposicao(self):
        """Editar um período mantendo as datas dele mesmo é OK."""
        periodo = PeriodoAvaliativo.objects.create(
            escola=self.escola_a,
            nome="1º Bim",
            ordem=1,
            ano_letivo=2026,
            data_inicio=date(2026, 2, 1),
            data_fim=date(2026, 4, 30),
        )
        periodo.nome = "1º Bimestre (renomeado)"
        periodo.clean()  # não deve levantar — período se enxerga

    # ------------------------------------------------------------------ #
    # Unique constraints                                                  #
    # ------------------------------------------------------------------ #

    def test_nome_duplicado_no_mesmo_ano_falha(self):
        PeriodoAvaliativo.objects.create(
            escola=self.escola_a,
            nome="1º Bim",
            ordem=1,
            ano_letivo=2026,
            data_inicio=date(2026, 2, 1),
            data_fim=date(2026, 4, 30),
        )
        with self.assertRaises(IntegrityError):
            PeriodoAvaliativo.objects.create(
                escola=self.escola_a,
                nome="1º Bim",  # mesmo nome
                ordem=2,  # ordem diferente
                ano_letivo=2026,
                data_inicio=date(2026, 5, 1),
                data_fim=date(2026, 7, 30),
            )

    def test_ordem_duplicada_no_mesmo_ano_falha(self):
        PeriodoAvaliativo.objects.create(
            escola=self.escola_a,
            nome="1º Bim",
            ordem=1,
            ano_letivo=2026,
            data_inicio=date(2026, 2, 1),
            data_fim=date(2026, 4, 30),
        )
        with self.assertRaises(IntegrityError):
            PeriodoAvaliativo.objects.create(
                escola=self.escola_a,
                nome="Outro",
                ordem=1,  # mesma ordem
                ano_letivo=2026,
                data_inicio=date(2026, 5, 1),
                data_fim=date(2026, 7, 30),
            )

    # ------------------------------------------------------------------ #
    # Helper de domínio                                                   #
    # ------------------------------------------------------------------ #

    def test_contem_data_dentro_do_periodo(self):
        periodo = PeriodoAvaliativo.objects.create(
            escola=self.escola_a,
            nome="1º Bim",
            ordem=1,
            ano_letivo=2026,
            data_inicio=date(2026, 2, 1),
            data_fim=date(2026, 4, 30),
        )
        self.assertTrue(periodo.contem(date(2026, 3, 15)))
        self.assertTrue(periodo.contem(date(2026, 2, 1)))  # borda início
        self.assertTrue(periodo.contem(date(2026, 4, 30)))  # borda fim
        self.assertFalse(periodo.contem(date(2026, 5, 1)))
        self.assertFalse(periodo.contem(date(2026, 1, 31)))
