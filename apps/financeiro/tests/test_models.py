"""Testes dos modelos do financeiro.

Cobre o que o módulo promete e não dá pra inferir do schema:

- o invariante de "uma mensalidade por aluno por mês", inclusive na
  virada de plano (o caso que um unique em `(plano, competencia)` não
  pegaria);
- a aritmética de dinheiro (desconto, multa, juros) em `Decimal`, com
  arredondamento comercial;
- a fronteira entre modelo e service: registrar `Pagamento` NÃO move
  `valor_pago`/`status` da fatura.
"""
from datetime import date, timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from apps.escola.models import Aluno, Escola, Turma
from apps.financeiro.models import Fatura, FaturaItem, Pagamento, PlanoCobranca
from apps.portal.models import Responsavel, ResponsavelAluno


class _Setup(TestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        cls.escola_a = Escola.objects.create(nome="A")
        cls.escola_b = Escola.objects.create(nome="B")
        cls.turma_a = Turma.objects.create(
            escola=cls.escola_a,
            nome="1A",
            turno=Turma.Turno.MATUTINO,
            ano_letivo=2026,
        )
        cls.turma_b = Turma.objects.create(
            escola=cls.escola_b,
            nome="1A",
            turno=Turma.Turno.MATUTINO,
            ano_letivo=2026,
        )
        cls.aluno_a = Aluno.objects.create(
            escola=cls.escola_a,
            turma=cls.turma_a,
            matricula="001",
            nome_completo="Ana",
        )
        cls.aluno_b = Aluno.objects.create(
            escola=cls.escola_b,
            turma=cls.turma_b,
            matricula="001",
            nome_completo="Bruno",
        )

    def plano(self, **kwargs) -> PlanoCobranca:
        """Plano válido na escola A, com os campos sobrescrevíveis."""
        dados = {
            "escola": self.escola_a,
            "aluno": self.aluno_a,
            "valor_mensalidade": Decimal("1000.00"),
            "dia_vencimento": 10,
            "vigencia_inicio": date(2026, 1, 1),
        }
        dados.update(kwargs)
        return PlanoCobranca(**dados)

    def fatura(self, plano: PlanoCobranca, **kwargs) -> Fatura:
        dados = {
            "escola": self.escola_a,
            "plano": plano,
            "aluno": plano.aluno,
            "competencia": date(2026, 3, 1),
            "valor": Decimal("1000.00"),
            "vencimento": date(2026, 3, 10),
        }
        dados.update(kwargs)
        return Fatura(**dados)


# ====================================================================== #
# PlanoCobranca                                                          #
# ====================================================================== #


class PlanoCleanTests(_Setup):
    def test_caminho_feliz(self):
        self.plano().full_clean()

    def test_aluno_de_outra_escola(self):
        with self.assertRaises(ValidationError) as ctx:
            self.plano(aluno=self.aluno_b).full_clean()
        self.assertIn("aluno", ctx.exception.message_dict)

    def test_fim_de_vigencia_antes_do_inicio(self):
        p = self.plano(vigencia_inicio=date(2026, 3, 1), vigencia_fim=date(2026, 2, 1))
        with self.assertRaises(ValidationError) as ctx:
            p.full_clean()
        self.assertIn("vigencia_fim", ctx.exception.message_dict)

    def test_dia_vencimento_fora_da_faixa(self):
        for dia in (0, 32):
            with self.subTest(dia=dia), self.assertRaises(ValidationError) as ctx:
                self.plano(dia_vencimento=dia).full_clean()
            self.assertIn("dia_vencimento", ctx.exception.message_dict)

    def test_dia_31_e_cadastro_legitimo(self):
        """Quem resolve fevereiro é o clamp da geração, não o cadastro."""
        self.plano(dia_vencimento=31).full_clean()

    def test_sem_desconto_exige_valor_zero(self):
        p = self.plano(
            desconto_tipo=PlanoCobranca.DescontoTipo.NENHUM,
            desconto_valor=Decimal("50.00"),
        )
        with self.assertRaises(ValidationError) as ctx:
            p.full_clean()
        self.assertIn("desconto_valor", ctx.exception.message_dict)

    def test_desconto_percentual_acima_de_cem(self):
        p = self.plano(
            desconto_tipo=PlanoCobranca.DescontoTipo.PERCENTUAL,
            desconto_valor=Decimal("120.00"),
        )
        with self.assertRaises(ValidationError) as ctx:
            p.full_clean()
        self.assertIn("desconto_valor", ctx.exception.message_dict)

    def test_desconto_fixo_maior_que_a_mensalidade(self):
        p = self.plano(
            desconto_tipo=PlanoCobranca.DescontoTipo.FIXO,
            desconto_valor=Decimal("1500.00"),
        )
        with self.assertRaises(ValidationError) as ctx:
            p.full_clean()
        self.assertIn("desconto_valor", ctx.exception.message_dict)


class PlanoVigenciaSobrepostaTests(_Setup):
    def test_sobreposicao_com_plano_de_vigencia_aberta(self):
        self.plano(vigencia_inicio=date(2026, 1, 1)).save()
        p = self.plano(vigencia_inicio=date(2026, 6, 1))
        with self.assertRaises(ValidationError) as ctx:
            p.full_clean()
        self.assertIn("vigencia_inicio", ctx.exception.message_dict)

    def test_sobreposicao_parcial(self):
        self.plano(
            vigencia_inicio=date(2026, 1, 1), vigencia_fim=date(2026, 6, 30)
        ).save()
        p = self.plano(vigencia_inicio=date(2026, 6, 1), vigencia_fim=date(2026, 12, 31))
        with self.assertRaises(ValidationError) as ctx:
            p.full_clean()
        self.assertIn("vigencia_inicio", ctx.exception.message_dict)

    def test_vigencias_adjacentes_passam(self):
        """Troca de plano no meio do mês é cadastro legítimo."""
        self.plano(
            vigencia_inicio=date(2026, 1, 1), vigencia_fim=date(2026, 3, 10)
        ).save()
        self.plano(vigencia_inicio=date(2026, 3, 11)).full_clean()

    def test_plano_inativo_nao_bloqueia(self):
        self.plano(vigencia_inicio=date(2026, 1, 1), ativo=False).save()
        self.plano(vigencia_inicio=date(2026, 2, 1)).full_clean()

    def test_plano_de_outro_aluno_nao_bloqueia(self):
        self.plano(vigencia_inicio=date(2026, 1, 1)).save()
        PlanoCobranca(
            escola=self.escola_b,
            aluno=self.aluno_b,
            valor_mensalidade=Decimal("500.00"),
            dia_vencimento=5,
            vigencia_inicio=date(2026, 1, 1),
        ).full_clean()

    def test_editar_o_proprio_plano_nao_colide_consigo(self):
        p = self.plano(vigencia_inicio=date(2026, 1, 1))
        p.save()
        p.valor_mensalidade = Decimal("1100.00")
        p.full_clean()


class PlanoValorEfetivoTests(_Setup):
    def test_sem_desconto(self):
        self.assertEqual(self.plano().valor_efetivo(), Decimal("1000.00"))

    def test_desconto_percentual(self):
        p = self.plano(
            desconto_tipo=PlanoCobranca.DescontoTipo.PERCENTUAL,
            desconto_valor=Decimal("10.00"),
        )
        self.assertEqual(p.valor_efetivo(), Decimal("900.00"))

    def test_desconto_fixo(self):
        p = self.plano(
            desconto_tipo=PlanoCobranca.DescontoTipo.FIXO,
            desconto_valor=Decimal("150.00"),
        )
        self.assertEqual(p.valor_efetivo(), Decimal("850.00"))

    def test_arredondamento_comercial(self):
        """110,00 com 8,65% dá 100,485 — half-up sobe, half-even desceria."""
        p = self.plano(
            valor_mensalidade=Decimal("110.00"),
            desconto_tipo=PlanoCobranca.DescontoTipo.PERCENTUAL,
            desconto_valor=Decimal("8.65"),
        )
        self.assertEqual(p.valor_efetivo(), Decimal("100.49"))

    def test_nunca_negativo(self):
        """`clean()` barra, mas criação por shell não — e fatura negativa não existe."""
        p = self.plano(
            desconto_tipo=PlanoCobranca.DescontoTipo.FIXO,
            desconto_valor=Decimal("1500.00"),
        )
        self.assertEqual(p.valor_efetivo(), Decimal("0.00"))

    def test_vigente_em(self):
        p = self.plano(
            vigencia_inicio=date(2026, 3, 1), vigencia_fim=date(2026, 6, 30)
        )
        self.assertFalse(p.vigente_em(date(2026, 2, 28)))
        self.assertTrue(p.vigente_em(date(2026, 3, 1)))
        self.assertTrue(p.vigente_em(date(2026, 6, 30)))
        self.assertFalse(p.vigente_em(date(2026, 7, 1)))

    def test_vigencia_aberta_nao_tem_fim(self):
        p = self.plano(vigencia_inicio=date(2026, 3, 1))
        self.assertTrue(p.vigente_em(date(2030, 1, 1)))


# ====================================================================== #
# Fatura                                                                 #
# ====================================================================== #


class FaturaCleanTests(_Setup):
    def setUp(self) -> None:
        self.p = self.plano()
        self.p.save()

    def test_caminho_feliz(self):
        self.fatura(self.p).full_clean()

    def test_paga_com_data_de_pagamento_passa(self):
        """Caminho feliz da fatura PAGA — o par status+data é válido.

        Fixa o lado que aprova: os ramos de erro cobrem paga-sem-data e
        data-sem-estar-paga, mas sem isto um aperto futuro na regra
        (ex.: exigir `valor_pago`) quebraria o caso legítimo sem teste.
        """
        self.fatura(
            self.p,
            status=Fatura.Status.PAGO,
            valor_pago=Decimal("1000.00"),
            data_pagamento=date(2026, 3, 9),
        ).full_clean()

    def test_plano_de_outra_escola(self):
        outro = PlanoCobranca.objects.create(
            escola=self.escola_b,
            aluno=self.aluno_b,
            valor_mensalidade=Decimal("500.00"),
            dia_vencimento=5,
            vigencia_inicio=date(2026, 1, 1),
        )
        f = self.fatura(outro, aluno=self.aluno_b)
        with self.assertRaises(ValidationError) as ctx:
            f.full_clean()
        self.assertIn("plano", ctx.exception.message_dict)

    def test_aluno_divergente_do_plano(self):
        """A desnormalização não pode apontar pra outro aluno."""
        f = self.fatura(self.p, aluno=self.aluno_b)
        with self.assertRaises(ValidationError) as ctx:
            f.full_clean()
        self.assertIn("aluno", ctx.exception.message_dict)

    def test_competencia_fora_do_dia_primeiro(self):
        f = self.fatura(self.p, competencia=date(2026, 3, 15))
        with self.assertRaises(ValidationError) as ctx:
            f.full_clean()
        self.assertIn("competencia", ctx.exception.message_dict)

    def test_vencimento_antes_da_competencia(self):
        f = self.fatura(self.p, vencimento=date(2026, 2, 10))
        with self.assertRaises(ValidationError) as ctx:
            f.full_clean()
        self.assertIn("vencimento", ctx.exception.message_dict)

    def test_vencimento_no_mes_seguinte_passa(self):
        self.fatura(self.p, vencimento=date(2026, 4, 5)).full_clean()

    def test_paga_exige_data_de_pagamento(self):
        f = self.fatura(
            self.p, status=Fatura.Status.PAGO, valor_pago=Decimal("1000.00")
        )
        with self.assertRaises(ValidationError) as ctx:
            f.full_clean()
        self.assertIn("data_pagamento", ctx.exception.message_dict)

    def test_data_de_pagamento_sem_estar_paga(self):
        f = self.fatura(self.p, data_pagamento=date(2026, 3, 9))
        with self.assertRaises(ValidationError) as ctx:
            f.full_clean()
        self.assertIn("data_pagamento", ctx.exception.message_dict)

    def test_cancelada_com_pagamento_registrado(self):
        f = self.fatura(
            self.p, status=Fatura.Status.CANCELADO, valor_pago=Decimal("500.00")
        )
        with self.assertRaises(ValidationError) as ctx:
            f.full_clean()
        self.assertIn("status", ctx.exception.message_dict)


class FaturaUniqueTests(_Setup):
    def setUp(self) -> None:
        self.p = self.plano(
            vigencia_inicio=date(2026, 1, 1), vigencia_fim=date(2026, 3, 10)
        )
        self.p.save()

    def test_uma_fatura_por_aluno_por_competencia(self):
        self.fatura(self.p).save()
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.fatura(self.p).save()

    def test_troca_de_plano_no_meio_do_mes_nao_cobra_duas_vezes(self):
        """O caso que um unique em (plano, competencia) deixaria passar.

        Plano A encerra dia 10, plano B começa dia 11 — vigências não
        sobrepostas, as duas passam no `clean()`. Sem o unique por
        `(aluno, competencia)`, a geração mensal criaria duas faturas de
        março e o aluno seria cobrado duas vezes no mês da virada.
        """
        plano_b = self.plano(vigencia_inicio=date(2026, 3, 11))
        plano_b.full_clean()
        plano_b.save()

        self.fatura(self.p).save()
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.fatura(plano_b).save()

    def test_competencias_diferentes_convivem(self):
        self.fatura(self.p).save()
        self.fatura(
            self.p, competencia=date(2026, 4, 1), vencimento=date(2026, 4, 10)
        ).save()
        self.assertEqual(Fatura.objects.count(), 2)

    def test_id_externo_vazio_nao_colide(self):
        self.fatura(self.p).save()
        self.fatura(
            self.p, competencia=date(2026, 4, 1), vencimento=date(2026, 4, 10)
        ).save()
        self.assertEqual(Fatura.objects.filter(id_externo="").count(), 2)

    def test_id_externo_repetido_e_recusado(self):
        """Duas faturas na mesma cobrança fariam o webhook conciliar a errada."""
        self.fatura(self.p, id_externo="pay_123").save()
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.fatura(
                self.p,
                competencia=date(2026, 4, 1),
                vencimento=date(2026, 4, 10),
                id_externo="pay_123",
            ).save()


class FaturaCalculoTests(_Setup):
    def setUp(self) -> None:
        self.p = self.plano()
        self.p.save()
        self.f = self.fatura(self.p)
        self.f.save()

    def test_saldo(self):
        self.assertEqual(self.f.saldo(), Decimal("1000.00"))
        self.f.valor_pago = Decimal("400.00")
        self.assertEqual(self.f.saldo(), Decimal("600.00"))

    def test_saldo_nunca_negativo(self):
        """Quem paga boleto vencido deposita mais que o principal."""
        self.f.valor_pago = Decimal("1100.00")
        self.assertEqual(self.f.saldo(), Decimal("0.00"))

    def test_dias_atraso(self):
        self.assertEqual(self.f.dias_atraso(date(2026, 3, 1)), 0)
        self.assertEqual(self.f.dias_atraso(date(2026, 3, 10)), 0)
        self.assertEqual(self.f.dias_atraso(date(2026, 3, 25)), 15)

    def test_encargos_multa_mais_juros_pro_rata(self):
        """1000,00 com 15 dias: multa 2% = 20,00; juros 1%/mês = 5,00."""
        self.assertEqual(self.f.encargos(date(2026, 3, 25)), Decimal("25.00"))
        self.assertEqual(self.f.valor_atualizado(date(2026, 3, 25)), Decimal("1025.00"))

    def test_encargos_sobre_o_saldo_e_nao_sobre_o_valor(self):
        self.f.valor_pago = Decimal("500.00")
        # Saldo 500: multa 10,00 + juros 2,50.
        self.assertEqual(self.f.encargos(date(2026, 3, 25)), Decimal("12.50"))

    def test_sem_atraso_nao_tem_encargo(self):
        self.assertEqual(self.f.encargos(date(2026, 3, 10)), Decimal("0.00"))
        self.assertEqual(self.f.valor_atualizado(date(2026, 3, 10)), Decimal("1000.00"))

    def test_fatura_cancelada_nao_gera_encargo(self):
        self.f.status = Fatura.Status.CANCELADO
        self.assertEqual(self.f.encargos(date(2026, 3, 25)), Decimal("0.00"))

    def test_saldo_zerado_nao_gera_encargo(self):
        self.f.valor_pago = Decimal("1000.00")
        self.assertEqual(self.f.encargos(date(2026, 3, 25)), Decimal("0.00"))

    def test_plano_sem_multa_nem_juros(self):
        p = self.plano(
            aluno=self.aluno_a,
            multa_percentual=Decimal("0.00"),
            juros_mes_percentual=Decimal("0.00"),
        )
        self.f.plano = p
        self.assertEqual(self.f.encargos(date(2026, 3, 25)), Decimal("0.00"))

    def test_esta_vencida(self):
        self.assertFalse(self.f.esta_vencida(date(2026, 3, 10)))
        self.assertTrue(self.f.esta_vencida(date(2026, 3, 11)))

    def test_paga_ou_cancelada_nunca_esta_vencida(self):
        for status in (Fatura.Status.PAGO, Fatura.Status.CANCELADO):
            with self.subTest(status=status):
                self.f.status = status
                self.assertFalse(self.f.esta_vencida(date(2026, 3, 25)))

    def test_percentuais_vem_do_plano_e_nao_de_settings(self):
        """Reajuste da env não reescreve contrato já cadastrado."""
        p = self.plano(multa_percentual=Decimal("5.00"))
        self.f.plano = p
        # Multa 5% = 50,00 + juros 5,00.
        self.assertEqual(self.f.encargos(date(2026, 3, 25)), Decimal("55.00"))


# ====================================================================== #
# FaturaItem                                                             #
# ====================================================================== #


class FaturaItemTests(_Setup):
    def setUp(self) -> None:
        self.p = self.plano()
        self.p.save()
        self.f = self.fatura(self.p)
        self.f.save()

    def test_caminho_feliz(self):
        FaturaItem(
            escola=self.escola_a,
            fatura=self.f,
            descricao="Mensalidade março",
            valor=Decimal("1000.00"),
        ).full_clean()

    def test_fatura_de_outra_escola(self):
        item = FaturaItem(
            escola=self.escola_b,
            fatura=self.f,
            descricao="Taxa",
            valor=Decimal("50.00"),
        )
        with self.assertRaises(ValidationError) as ctx:
            item.full_clean()
        self.assertIn("fatura", ctx.exception.message_dict)

    def test_apagar_a_fatura_leva_os_itens(self):
        """`CASCADE` por design: item órfão não significa nada."""
        FaturaItem.objects.create(
            escola=self.escola_a,
            fatura=self.f,
            descricao="Mensalidade março",
            valor=Decimal("1000.00"),
        )
        self.f.delete()
        self.assertEqual(FaturaItem.objects.count(), 0)


# ====================================================================== #
# Pagamento                                                              #
# ====================================================================== #


class PagamentoTests(_Setup):
    def setUp(self) -> None:
        self.p = self.plano()
        self.p.save()
        self.f = self.fatura(self.p)
        self.f.save()

    def pagamento(self, **kwargs) -> Pagamento:
        dados = {
            "escola": self.escola_a,
            "fatura": self.f,
            "valor": Decimal("1000.00"),
            "data": date.today(),
            "metodo": Pagamento.Metodo.PIX,
        }
        dados.update(kwargs)
        return Pagamento(**dados)

    def test_caminho_feliz(self):
        self.pagamento().full_clean()

    def test_fatura_de_outra_escola(self):
        with self.assertRaises(ValidationError) as ctx:
            self.pagamento(escola=self.escola_b).full_clean()
        self.assertIn("fatura", ctx.exception.message_dict)

    def test_data_futura(self):
        p = self.pagamento(data=date.today() + timedelta(days=1))
        with self.assertRaises(ValidationError) as ctx:
            p.full_clean()
        self.assertIn("data", ctx.exception.message_dict)

    def test_fatura_cancelada_nao_recebe_pagamento(self):
        self.f.status = Fatura.Status.CANCELADO
        self.f.save(update_fields=["status", "atualizado_em"])
        with self.assertRaises(ValidationError) as ctx:
            self.pagamento().full_clean()
        self.assertIn("fatura", ctx.exception.message_dict)

    def test_pagamento_a_mais_que_o_saldo_e_permitido(self):
        """Boleto vencido pago com multa entra pelo valor depositado."""
        self.pagamento(valor=Decimal("1025.00")).full_clean()

    def test_referencia_externa_vazia_nao_colide(self):
        self.pagamento().save()
        self.pagamento(valor=Decimal("10.00")).save()
        self.assertEqual(Pagamento.objects.filter(referencia_externa="").count(), 2)

    def test_referencia_externa_repetida_e_recusada(self):
        """Idempotência da conciliação: o Asaas reentrega o mesmo evento."""
        self.pagamento(referencia_externa="pay_123").save()
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.pagamento(referencia_externa="pay_123").save()

    def test_salvar_pagamento_nao_toca_na_fatura(self):
        """Conciliação é do `services.py` — ver docstring de `models.py`.

        Se um dia alguém mover isso pro `save()`, este teste cai e a
        decisão volta pra mesa em vez de mudar em silêncio.
        """
        self.pagamento().save()
        self.f.refresh_from_db()
        self.assertEqual(self.f.valor_pago, Decimal("0.00"))
        self.assertEqual(self.f.status, Fatura.Status.PENDENTE)
        self.assertIsNone(self.f.data_pagamento)


# ====================================================================== #
# Audit log                                                              #
# ====================================================================== #


class HistoricoTests(_Setup):
    def test_os_quatro_modelos_sao_auditados(self):
        plano = self.plano()
        plano.save()
        fatura = self.fatura(plano)
        fatura.save()
        item = FaturaItem.objects.create(
            escola=self.escola_a,
            fatura=fatura,
            descricao="Mensalidade março",
            valor=Decimal("1000.00"),
        )
        pagamento = Pagamento.objects.create(
            escola=self.escola_a,
            fatura=fatura,
            valor=Decimal("1000.00"),
            data=date.today(),
            metodo=Pagamento.Metodo.PIX,
        )
        for obj in (plano, fatura, item, pagamento):
            with self.subTest(modelo=type(obj).__name__):
                self.assertEqual(obj.history.count(), 1)

    def test_edicao_gera_nova_entrada_no_historico(self):
        plano = self.plano()
        plano.save()
        plano.valor_mensalidade = Decimal("1100.00")
        plano.save()
        self.assertEqual(plano.history.count(), 2)
        self.assertEqual(
            plano.history.first().valor_mensalidade, Decimal("1100.00")
        )


class PlanoPagadorTests(_Setup):
    """Invariantes do pagador: quem assina o contrato é responsável do aluno.

    O vínculo é o que autoriza alguém a ver os dados do aluno
    (`RESPONSAVEIS.md`); aceitar um pagador sem vínculo poria o nome de um
    terceiro no boleto da família, e a escola só descobriria pelo boleto.
    """

    def responsavel(self, escola, email="mae@exemplo.com", aluno=None):
        resp = Responsavel.objects.create(
            escola=escola, nome="Maria", email=email
        )
        if aluno is not None:
            ResponsavelAluno.objects.create(responsavel=resp, aluno=aluno)
        return resp

    def test_pagador_vinculado_ao_aluno_passa(self):
        pagador = self.responsavel(self.escola_a, aluno=self.aluno_a)
        self.plano(pagador=pagador).full_clean()

    def test_plano_sem_pagador_passa(self):
        """Cobrança online é opt-in: plano sem pagador é cadastro normal."""
        self.plano(pagador=None).full_clean()

    def test_pagador_de_outra_escola(self):
        pagador = self.responsavel(self.escola_b, aluno=self.aluno_b)
        with self.assertRaises(ValidationError) as ctx:
            self.plano(pagador=pagador).full_clean()
        self.assertIn("pagador", ctx.exception.message_dict)

    def test_pagador_sem_vinculo_com_o_aluno(self):
        """Responsável da escola certa, mas de outro aluno (ou de nenhum)."""
        pagador = self.responsavel(self.escola_a)
        with self.assertRaises(ValidationError) as ctx:
            self.plano(pagador=pagador).full_clean()
        self.assertIn("pagador", ctx.exception.message_dict)

    def test_pagador_vinculado_a_outro_aluno_da_mesma_escola(self):
        outro = Aluno.objects.create(
            escola=self.escola_a,
            turma=self.turma_a,
            matricula="002",
            nome_completo="Carla",
        )
        pagador = self.responsavel(self.escola_a, aluno=outro)
        with self.assertRaises(ValidationError) as ctx:
            self.plano(pagador=pagador).full_clean()
        self.assertIn("pagador", ctx.exception.message_dict)
