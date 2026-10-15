"""Testes do `services.py` e dos management commands (fatia 3).

O que precisa ficar travado:

- a geração é **idempotente** (é o requisito de estar no cron);
- na virada de contrato no meio do mês, quem cobra é o contrato mais
  antigo — determinístico, não dependente de ordem de inserção;
- o vencimento aterra no último dia do mês quando o dia cadastrado não
  existe (fevereiro com `dia_vencimento=31`);
- a conciliação **recalcula** `valor_pago` em vez de incrementar, e é
  idempotente por `referencia_externa` (o gateway reentrega eventos);
- estorno reconcilia de volta;
- `marcar_vencidas` só toca em `pendente`.

Datas relativas a hoje onde o estado depende de "está vencida", pra o
teste não apodrecer quando a data do calendário passar.
"""
from datetime import date, timedelta
from decimal import Decimal
from io import StringIO

from django.core.exceptions import ValidationError
from django.core.management import CommandError, call_command
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from apps.escola.models import Aluno, Escola, Turma
from apps.financeiro.models import Fatura, FaturaItem, Pagamento, PlanoCobranca
from apps.financeiro.services import (
    estornar_pagamento,
    gerar_faturas,
    marcar_vencidas,
    registrar_pagamento,
    vencimento_da_competencia,
)


class _Setup(TestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        cls.hoje = date.today()
        cls.competencia = cls.hoje.replace(day=1)

        cls.escola = Escola.objects.create(nome="Escola A")
        cls.outra = Escola.objects.create(nome="Escola B")
        cls.turma = Turma.objects.create(
            escola=cls.escola, nome="1A", turno=Turma.Turno.MATUTINO, ano_letivo=2026
        )
        cls.turma_b = Turma.objects.create(
            escola=cls.outra, nome="1A", turno=Turma.Turno.MATUTINO, ano_letivo=2026
        )
        cls.ana = Aluno.objects.create(
            escola=cls.escola, turma=cls.turma, matricula="001", nome_completo="Ana"
        )
        cls.bia = Aluno.objects.create(
            escola=cls.escola, turma=cls.turma, matricula="002", nome_completo="Bia"
        )
        cls.caio = Aluno.objects.create(
            escola=cls.outra, turma=cls.turma_b, matricula="001", nome_completo="Caio"
        )

    def plano(self, aluno=None, escola=None, **extra) -> PlanoCobranca:
        dados = {
            "escola": escola or self.escola,
            "aluno": aluno or self.ana,
            "valor_mensalidade": Decimal("1000.00"),
            "dia_vencimento": 10,
            "vigencia_inicio": self.competencia,
        }
        dados.update(extra)
        return PlanoCobranca.objects.create(**dados)

    def fatura(self, plano, **extra) -> Fatura:
        dados = {
            "escola": plano.escola,
            "plano": plano,
            "aluno": plano.aluno,
            "competencia": self.competencia,
            "valor": Decimal("1000.00"),
            "vencimento": self.hoje + timedelta(days=30),
        }
        dados.update(extra)
        return Fatura.objects.create(**dados)


# ====================================================================== #
# Vencimento                                                             #
# ====================================================================== #


class VencimentoTests(_Setup):
    def test_dia_que_existe_no_mes(self):
        self.assertEqual(
            vencimento_da_competencia(date(2026, 3, 1), 10), date(2026, 3, 10)
        )

    def test_clamp_no_ultimo_dia_de_fevereiro(self):
        """`dia_vencimento=31` é cadastro legítimo; fevereiro é que é curto."""
        self.assertEqual(
            vencimento_da_competencia(date(2026, 2, 1), 31), date(2026, 2, 28)
        )

    def test_clamp_em_ano_bissexto(self):
        self.assertEqual(
            vencimento_da_competencia(date(2028, 2, 1), 31), date(2028, 2, 29)
        )

    def test_competencia_fora_do_dia_primeiro_e_normalizada(self):
        self.assertEqual(
            vencimento_da_competencia(date(2026, 3, 20), 5), date(2026, 3, 5)
        )


# ====================================================================== #
# Geração                                                                #
# ====================================================================== #


class GerarFaturasTests(_Setup):
    def test_gera_para_plano_ativo(self):
        plano = self.plano()
        resultado = gerar_faturas(self.competencia)
        self.assertEqual(resultado.criadas, 1)
        fatura = Fatura.objects.get()
        self.assertEqual(fatura.plano, plano)
        self.assertEqual(fatura.aluno, self.ana)
        self.assertEqual(fatura.valor, Decimal("1000.00"))
        self.assertEqual(fatura.status, Fatura.Status.PENDENTE)

    def test_valor_sai_com_desconto_do_plano(self):
        self.plano(
            desconto_tipo=PlanoCobranca.DescontoTipo.PERCENTUAL,
            desconto_valor=Decimal("25.00"),
        )
        gerar_faturas(self.competencia)
        self.assertEqual(Fatura.objects.get().valor, Decimal("750.00"))

    def test_cria_a_linha_de_detalhamento(self):
        """Item e total nascem coerentes — ver FINANCEIRO.md §3.5."""
        self.plano()
        gerar_faturas(self.competencia)
        item = FaturaItem.objects.get()
        self.assertEqual(item.descricao, f"Mensalidade {self.competencia:%m/%Y}")
        self.assertEqual(item.valor, item.fatura.valor)
        self.assertEqual(item.escola, item.fatura.escola)

    def test_segunda_execucao_nao_duplica(self):
        """É o requisito de poder deixar no cron."""
        self.plano()
        gerar_faturas(self.competencia)
        resultado = gerar_faturas(self.competencia)
        self.assertEqual(resultado.criadas, 0)
        self.assertEqual(resultado.ignoradas, 1)
        self.assertEqual(Fatura.objects.count(), 1)
        self.assertEqual(FaturaItem.objects.count(), 1)

    def test_ignora_plano_inativo(self):
        self.plano(ativo=False)
        self.assertEqual(gerar_faturas(self.competencia).criadas, 0)

    def test_ignora_plano_que_nao_cobre_o_mes(self):
        self.plano(
            vigencia_inicio=self.competencia - timedelta(days=200),
            vigencia_fim=self.competencia - timedelta(days=1),
        )
        self.assertEqual(gerar_faturas(self.competencia).criadas, 0)

    def test_plano_de_vigencia_aberta_cobre_qualquer_mes(self):
        self.plano(vigencia_inicio=date(2020, 1, 1))
        self.assertEqual(gerar_faturas(self.competencia).criadas, 1)

    def test_escopo_por_escola(self):
        self.plano()
        self.plano(aluno=self.caio, escola=self.outra)
        resultado = gerar_faturas(self.competencia, escola_id=self.escola.pk)
        self.assertEqual(resultado.criadas, 1)
        self.assertEqual(Fatura.objects.get().escola, self.escola)

    def test_dry_run_nao_escreve(self):
        self.plano()
        resultado = gerar_faturas(self.competencia, dry_run=True)
        self.assertEqual(resultado.criadas, 1)
        self.assertEqual(Fatura.objects.count(), 0)

    def test_virada_de_plano_cobra_pelo_contrato_mais_antigo(self):
        """Plano A até o dia 10, plano B do dia 11: o mês sai pelo A.

        Determinismo é o ponto. Sem escolher na aplicação, as duas faturas
        seriam tentadas e o unique de banco decidiria qual sobrevive — o
        valor do boleto dependendo da ordem de inserção.
        """
        antigo = self.plano(
            vigencia_inicio=self.competencia,
            vigencia_fim=self.competencia + timedelta(days=9),
            valor_mensalidade=Decimal("1000.00"),
        )
        self.plano(
            vigencia_inicio=self.competencia + timedelta(days=10),
            valor_mensalidade=Decimal("1200.00"),
        )
        resultado = gerar_faturas(self.competencia)
        self.assertEqual(resultado.criadas, 1)
        fatura = Fatura.objects.get()
        self.assertEqual(fatura.plano, antigo)
        self.assertEqual(fatura.valor, Decimal("1000.00"))
        self.assertEqual(resultado.alunos_com_plano_concorrente, [self.ana.pk])

    def test_matricula_nova_no_meio_do_mes_cobra_valor_cheio(self):
        """Só existe o contrato novo: ele cobra o mês (rateio fora de escopo)."""
        self.plano(vigencia_inicio=self.competencia + timedelta(days=10))
        resultado = gerar_faturas(self.competencia)
        self.assertEqual(resultado.criadas, 1)
        self.assertEqual(Fatura.objects.get().valor, Decimal("1000.00"))
        self.assertEqual(resultado.alunos_com_plano_concorrente, [])

    def test_nao_cresce_em_queries_com_mais_planos(self):
        """Geração é em bulk: as queries não acompanham o número de planos.

        Mede duas competências diferentes, a segunda com o dobro de
        planos. Repetir a mesma competência não serviria: os alunos já
        teriam fatura e o caminho de criação não rodaria.
        """
        self.plano(vigencia_inicio=date(2025, 1, 1))
        self.plano(aluno=self.bia, vigencia_inicio=date(2025, 1, 1))
        with CaptureQueriesContext(connection) as com_dois:
            gerar_faturas(date(2026, 1, 1))

        self.plano(
            aluno=self.caio, escola=self.outra, vigencia_inicio=date(2025, 1, 1)
        )
        davi = Aluno.objects.create(
            escola=self.escola, turma=self.turma, matricula="003", nome_completo="Davi"
        )
        self.plano(aluno=davi, vigencia_inicio=date(2025, 1, 1))
        with CaptureQueriesContext(connection) as com_quatro:
            gerar_faturas(date(2026, 2, 1))

        self.assertEqual(len(com_quatro), len(com_dois))
        self.assertEqual(Fatura.objects.filter(competencia=date(2026, 2, 1)).count(), 4)


# ====================================================================== #
# Conciliação                                                            #
# ====================================================================== #


class RegistrarPagamentoTests(_Setup):
    def setUp(self) -> None:
        self.p = self.plano()
        self.f = self.fatura(self.p)

    def test_pagamento_parcial_mantem_pendente(self):
        registrar_pagamento(
            self.f, Decimal("400.00"), self.hoje, Pagamento.Metodo.PIX
        )
        self.f.refresh_from_db()
        self.assertEqual(self.f.valor_pago, Decimal("400.00"))
        self.assertEqual(self.f.status, Fatura.Status.PENDENTE)
        self.assertIsNone(self.f.data_pagamento)
        self.assertEqual(self.f.saldo(), Decimal("600.00"))

    def test_quitacao_marca_pago_com_a_data_do_pagamento(self):
        ontem = self.hoje - timedelta(days=1)
        registrar_pagamento(self.f, Decimal("1000.00"), ontem, Pagamento.Metodo.BOLETO)
        self.f.refresh_from_db()
        self.assertEqual(self.f.status, Fatura.Status.PAGO)
        self.assertEqual(self.f.data_pagamento, ontem)

    def test_parcelas_somam_e_quitam(self):
        registrar_pagamento(self.f, Decimal("400.00"), self.hoje, Pagamento.Metodo.PIX)
        registrar_pagamento(self.f, Decimal("600.00"), self.hoje, Pagamento.Metodo.PIX)
        self.f.refresh_from_db()
        self.assertEqual(self.f.valor_pago, Decimal("1000.00"))
        self.assertEqual(self.f.status, Fatura.Status.PAGO)
        self.assertEqual(self.f.pagamentos.count(), 2)

    def test_pagamento_a_mais_quita(self):
        registrar_pagamento(
            self.f, Decimal("1050.00"), self.hoje, Pagamento.Metodo.BOLETO
        )
        self.f.refresh_from_db()
        self.assertEqual(self.f.status, Fatura.Status.PAGO)
        self.assertEqual(self.f.saldo(), Decimal("0.00"))

    def test_fatura_vencida_com_pagamento_parcial_segue_vencida(self):
        self.f.vencimento = self.hoje - timedelta(days=5)
        self.f.save(update_fields=["vencimento", "atualizado_em"])
        registrar_pagamento(self.f, Decimal("100.00"), self.hoje, Pagamento.Metodo.PIX)
        self.f.refresh_from_db()
        self.assertEqual(self.f.status, Fatura.Status.VENCIDO)

    def test_reentrega_do_mesmo_evento_nao_duplica(self):
        """O Asaas reentrega por design — reentrega não é falha."""
        primeiro = registrar_pagamento(
            self.f,
            Decimal("1000.00"),
            self.hoje,
            Pagamento.Metodo.PIX,
            referencia_externa="pay_123",
        )
        segundo = registrar_pagamento(
            self.f,
            Decimal("1000.00"),
            self.hoje,
            Pagamento.Metodo.PIX,
            referencia_externa="pay_123",
        )
        self.assertEqual(primeiro.pk, segundo.pk)
        self.assertEqual(Pagamento.objects.count(), 1)
        self.f.refresh_from_db()
        self.assertEqual(self.f.valor_pago, Decimal("1000.00"))

    def test_pagamento_manual_repetido_nao_e_deduplicado(self):
        """Dois Pix iguais no mesmo dia são dois pagamentos."""
        registrar_pagamento(self.f, Decimal("100.00"), self.hoje, Pagamento.Metodo.PIX)
        registrar_pagamento(self.f, Decimal("100.00"), self.hoje, Pagamento.Metodo.PIX)
        self.assertEqual(Pagamento.objects.count(), 2)
        self.f.refresh_from_db()
        self.assertEqual(self.f.valor_pago, Decimal("200.00"))

    def test_valor_pago_e_recalculado_e_nao_incrementado(self):
        """`valor_pago` divergente se autocorrige na próxima conciliação."""
        self.f.valor_pago = Decimal("999.00")
        self.f.save(update_fields=["valor_pago", "atualizado_em"])
        registrar_pagamento(self.f, Decimal("100.00"), self.hoje, Pagamento.Metodo.PIX)
        self.f.refresh_from_db()
        self.assertEqual(self.f.valor_pago, Decimal("100.00"))

    def test_fatura_cancelada_recusa_pagamento(self):
        self.f.status = Fatura.Status.CANCELADO
        self.f.save(update_fields=["status", "atualizado_em"])
        with self.assertRaises(ValidationError):
            registrar_pagamento(
                self.f, Decimal("100.00"), self.hoje, Pagamento.Metodo.PIX
            )
        self.assertEqual(Pagamento.objects.count(), 0)

    def test_data_futura_recusada(self):
        with self.assertRaises(ValidationError):
            registrar_pagamento(
                self.f,
                Decimal("100.00"),
                self.hoje + timedelta(days=1),
                Pagamento.Metodo.PIX,
            )


class EstornarPagamentoTests(_Setup):
    def setUp(self) -> None:
        self.p = self.plano()
        self.f = self.fatura(self.p)
        self.pagamento = registrar_pagamento(
            self.f, Decimal("1000.00"), self.hoje, Pagamento.Metodo.PIX
        )

    def test_estorno_reconcilia_de_volta(self):
        estornar_pagamento(self.pagamento)
        self.f.refresh_from_db()
        self.assertEqual(Pagamento.objects.count(), 0)
        self.assertEqual(self.f.valor_pago, Decimal("0.00"))
        self.assertEqual(self.f.status, Fatura.Status.PENDENTE)
        self.assertIsNone(self.f.data_pagamento)

    def test_estorno_parcial_mantem_o_resto(self):
        outro = registrar_pagamento(
            self.f, Decimal("500.00"), self.hoje, Pagamento.Metodo.DINHEIRO
        )
        estornar_pagamento(outro)
        self.f.refresh_from_db()
        self.assertEqual(self.f.valor_pago, Decimal("1000.00"))
        self.assertEqual(self.f.status, Fatura.Status.PAGO)

    def test_estorno_destrava_o_cancelamento(self):
        """É o furo que o estorno fecha: antes dele, cancelar era impossível."""
        estornar_pagamento(self.pagamento)
        self.f.refresh_from_db()
        self.f.status = Fatura.Status.CANCELADO
        self.f.full_clean()

    def test_estorno_fica_no_audit_log(self):
        pk = self.pagamento.pk
        estornar_pagamento(self.pagamento)
        self.assertTrue(Pagamento.history.filter(id=pk).exists())


# ====================================================================== #
# Vencidas                                                               #
# ====================================================================== #


class MarcarVencidasTests(_Setup):
    def setUp(self) -> None:
        self.p = self.plano()

    def test_marca_pendente_com_vencimento_passado(self):
        f = self.fatura(self.p, vencimento=self.hoje - timedelta(days=1))
        self.assertEqual(marcar_vencidas(), 1)
        f.refresh_from_db()
        self.assertEqual(f.status, Fatura.Status.VENCIDO)

    def test_nao_marca_quem_vence_hoje(self):
        f = self.fatura(self.p, vencimento=self.hoje)
        self.assertEqual(marcar_vencidas(), 0)
        f.refresh_from_db()
        self.assertEqual(f.status, Fatura.Status.PENDENTE)

    def test_nao_toca_paga_nem_cancelada(self):
        paga = self.fatura(
            self.p,
            vencimento=self.hoje - timedelta(days=5),
            status=Fatura.Status.PAGO,
            valor_pago=Decimal("1000.00"),
            data_pagamento=self.hoje - timedelta(days=6),
        )
        cancelada = self.fatura(
            self.p,
            aluno=self.bia,
            competencia=self.competencia,
            vencimento=self.hoje - timedelta(days=5),
            status=Fatura.Status.CANCELADO,
        )
        self.assertEqual(marcar_vencidas(), 0)
        paga.refresh_from_db()
        cancelada.refresh_from_db()
        self.assertEqual(paga.status, Fatura.Status.PAGO)
        self.assertEqual(cancelada.status, Fatura.Status.CANCELADO)

    def test_segunda_execucao_nao_faz_nada(self):
        self.fatura(self.p, vencimento=self.hoje - timedelta(days=1))
        marcar_vencidas()
        self.assertEqual(marcar_vencidas(), 0)

    def test_carimba_atualizado_em_e_gera_historico(self):
        f = self.fatura(self.p, vencimento=self.hoje - timedelta(days=1))
        antes = f.atualizado_em
        marcar_vencidas()
        f.refresh_from_db()
        self.assertGreater(f.atualizado_em, antes)
        self.assertEqual(f.history.count(), 2)

    def test_escopo_por_escola(self):
        plano_b = self.plano(aluno=self.caio, escola=self.outra)
        minha = self.fatura(self.p, vencimento=self.hoje - timedelta(days=1))
        dela = self.fatura(plano_b, vencimento=self.hoje - timedelta(days=1))
        self.assertEqual(marcar_vencidas(escola_id=self.escola.pk), 1)
        minha.refresh_from_db()
        dela.refresh_from_db()
        self.assertEqual(minha.status, Fatura.Status.VENCIDO)
        self.assertEqual(dela.status, Fatura.Status.PENDENTE)


# ====================================================================== #
# Management commands                                                    #
# ====================================================================== #


class CommandTests(_Setup):
    def test_gerar_faturas_com_competencia(self):
        self.plano(vigencia_inicio=date(2026, 1, 1))
        call_command(
            "financeiro_gerar_faturas", "--competencia", "2026-04", stdout=StringIO()
        )
        fatura = Fatura.objects.get()
        self.assertEqual(fatura.competencia, date(2026, 4, 1))
        self.assertEqual(fatura.vencimento, date(2026, 4, 10))

    def test_gerar_faturas_sem_competencia_usa_o_mes_corrente(self):
        self.plano()
        call_command("financeiro_gerar_faturas", stdout=StringIO())
        self.assertEqual(Fatura.objects.get().competencia, self.competencia)

    def test_gerar_faturas_dry_run(self):
        self.plano()
        call_command("financeiro_gerar_faturas", "--dry-run", stdout=StringIO())
        self.assertEqual(Fatura.objects.count(), 0)

    def test_gerar_faturas_por_escola(self):
        self.plano()
        self.plano(aluno=self.caio, escola=self.outra)
        call_command(
            "financeiro_gerar_faturas",
            "--escola",
            str(self.outra.pk),
            stdout=StringIO(),
        )
        self.assertEqual(Fatura.objects.get().escola, self.outra)

    def test_gerar_faturas_competencia_invalida(self):
        for valor in ("2026-13", "abril", "2026-04-01"):
            with self.subTest(valor=valor), self.assertRaises(CommandError):
                call_command("financeiro_gerar_faturas", "--competencia", valor)

    def test_marcar_vencidas(self):
        plano = self.plano()
        f = self.fatura(plano, vencimento=self.hoje - timedelta(days=1))
        call_command("financeiro_marcar_vencidas", stdout=StringIO())
        f.refresh_from_db()
        self.assertEqual(f.status, Fatura.Status.VENCIDO)
