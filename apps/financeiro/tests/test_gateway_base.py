"""Testes do contrato do gateway.

Não há provedor ainda (fatia 4 entrega o Asaas), então o que se testa
aqui é o contrato em si: que ele obriga as quatro operações, que o
vocabulário de situação não desencontra do `Fatura.Status` e que a
hierarquia de erro permite decidir retentativa sem ler mensagem.
"""
from datetime import date
from decimal import Decimal

from django.test import SimpleTestCase

from apps.financeiro.gateways import (
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
from apps.financeiro.models import Fatura, Pagamento


class _GatewayCompleto(CobrancaGateway):
    """Implementação mínima, só pra provar que o contrato é satisfazível."""

    def criar_pagador(self, dados: DadosPagador) -> Pagador:
        return Pagador(id_externo="cus_1")

    def criar_cobranca(self, dados: DadosCobranca) -> Cobranca:
        return Cobranca(
            id_externo="pay_1",
            situacao=SituacaoCobranca.PENDENTE,
            valor=dados.valor,
            vencimento=dados.vencimento,
        )

    def consultar_cobranca(self, id_externo: str) -> Cobranca:
        return Cobranca(
            id_externo=id_externo,
            situacao=SituacaoCobranca.PENDENTE,
            valor=Decimal("100.00"),
            vencimento=date(2026, 3, 10),
        )

    def cancelar_cobranca(self, id_externo: str) -> Cobranca:
        return Cobranca(
            id_externo=id_externo,
            situacao=SituacaoCobranca.CANCELADO,
            valor=Decimal("100.00"),
            vencimento=date(2026, 3, 10),
        )


class _GatewayIncompleto(CobrancaGateway):
    """Só uma das quatro operações — não deve poder ser instanciado."""

    def criar_pagador(self, dados: DadosPagador) -> Pagador:
        return Pagador(id_externo="cus_1")


class ContratoTests(SimpleTestCase):
    def test_implementacao_completa_e_instanciavel(self):
        gateway = _GatewayCompleto()
        cobranca = gateway.criar_cobranca(
            DadosCobranca(
                pagador=Pagador(id_externo="cus_1"),
                valor=Decimal("250.00"),
                vencimento=date(2026, 3, 10),
            )
        )
        self.assertEqual(cobranca.id_externo, "pay_1")
        self.assertEqual(cobranca.situacao, SituacaoCobranca.PENDENTE)

    def test_implementacao_parcial_nao_e_instanciavel(self):
        """O ABC é o que impede um provedor novo de esquecer um método.

        Sem isso a falta só apareceria em produção, na primeira
        conciliação que chamasse `consultar_cobranca`.
        """
        with self.assertRaises(TypeError):
            _GatewayIncompleto()


class SituacaoTests(SimpleTestCase):
    def test_situacao_cobre_exatamente_os_status_da_fatura(self):
        """Trava o vocabulário reduzido contra o `Fatura.Status`.

        Se alguém acrescentar um status na fatura sem decidir o que o
        gateway devolve nesse caso, é aqui que aparece — e não num
        `KeyError` do adaptador meses depois.
        """
        self.assertEqual(
            {s.value for s in SituacaoCobranca},
            {s.value for s in Fatura.Status},
        )

    def test_metodos_de_cobranca_existem_no_pagamento(self):
        """O `metodo` de `DadosCobranca` fala a língua do `Pagamento`.

        Dinheiro fica de fora de propósito: não passa por gateway.
        """
        metodos_do_gateway = {"pix", "boleto", "cartao"}
        self.assertTrue(
            metodos_do_gateway.issubset({m.value for m in Pagamento.Metodo})
        )
        self.assertNotIn(Pagamento.Metodo.DINHEIRO.value, metodos_do_gateway)


class ErroTests(SimpleTestCase):
    def test_temporario_e_permanente_sao_erro_de_gateway(self):
        """Quem só quer tratar "falhou" pega a base e não precisa dos dois."""
        self.assertTrue(issubclass(ErroTemporario, ErroDeGateway))
        self.assertTrue(issubclass(ErroPermanente, ErroDeGateway))

    def test_permanente_nao_e_temporario(self):
        """A distinção é o que decide retentativa — não podem se confundir."""
        self.assertFalse(issubclass(ErroPermanente, ErroTemporario))
        self.assertFalse(issubclass(ErroTemporario, ErroPermanente))

    def test_erro_carrega_codigo_do_provedor(self):
        erro = ErroPermanente("A chave de API fornecida é inválida", "invalid_access_token")
        self.assertEqual(erro.codigo, "invalid_access_token")
        self.assertEqual(str(erro), "A chave de API fornecida é inválida")

    def test_codigo_e_opcional(self):
        """Falha de transporte não tem código do provedor."""
        self.assertEqual(ErroTemporario("timeout").codigo, "")
