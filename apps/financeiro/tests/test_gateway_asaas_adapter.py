"""Testes do adaptador do Asaas — a tradução entre o dialeto deles e o nosso.

Nenhum toca a rede. As respostas abaixo são recortes do contrato real
(OpenAPI de `docs.asaas.com` e o payload de exemplo do webhook deles),
com os nomes e os formatos como eles emitem: `value` como number,
`dueDate` como `YYYY-MM-DD`, `invoiceUrl`, `clientPaymentDate`. Inventar
o formato provaria só que o código concorda consigo mesmo.
"""
import json
from datetime import date
from decimal import Decimal

import httpx
from django.test import SimpleTestCase

from apps.financeiro.gateways import (
    DadosCobranca,
    DadosPagador,
    ErroPermanente,
    ErroTemporario,
    Pagador,
    SituacaoCobranca,
)
from apps.financeiro.gateways.asaas import (
    BILLING_TYPE_POR_METODO,
    METODO_POR_BILLING_TYPE,
    SANDBOX,
    ClienteAsaas,
    GatewayAsaas,
    metodo_de,
)
from apps.financeiro.models import Pagamento

# Resposta de `POST /payments` / `GET /payments/{id}`, nos campos que o
# adaptador lê. Valores do exemplo da documentação.
COBRANCA_PENDENTE = {
    "object": "payment",
    "id": "pay_080225913252",
    "customer": "cus_G7Dvo4iphUNk",
    "value": 1000.0,
    "netValue": 970.51,
    "status": "PENDING",
    "dueDate": "2026-03-10",
    "invoiceUrl": "https://www.asaas.com/i/080225913252",
    "bankSlipUrl": None,
    "externalReference": "42",
    "deleted": False,
    "clientPaymentDate": None,
    "paymentDate": None,
}

COBRANCA_RECEBIDA = {
    **COBRANCA_PENDENTE,
    "status": "RECEIVED",
    # Pagou com multa e juros: `value` passa a ser o efetivamente pago e
    # `originalValue` guarda o original. É o caso que decide se o
    # adaptador lê `value` ou `netValue`.
    "value": 1025.50,
    "originalValue": 1000.0,
    "interestValue": 25.50,
    "clientPaymentDate": "2026-03-15",
    "paymentDate": "2026-03-16",
}


def _gateway(handler) -> GatewayAsaas:
    cliente = ClienteAsaas(
        api_key="$aact_hmlg_chave",
        base_url=SANDBOX,
        transport=httpx.MockTransport(handler),
    )
    return GatewayAsaas(cliente)


class VocabularioTests(SimpleTestCase):
    """O mapa de método escrito à mão não pode desencontrar do modelo."""

    def test_metodos_mapeados_existem_no_modelo(self):
        validos = set(Pagamento.Metodo.values)
        for billing_type, metodo in METODO_POR_BILLING_TYPE.items():
            with self.subTest(billingType=billing_type):
                self.assertIn(metodo, validos)
        for metodo in BILLING_TYPE_POR_METODO:
            with self.subTest(metodo=metodo):
                self.assertIn(metodo, validos)

    def test_billing_type_desconhecido_vira_outro(self):
        """TED e depósito associados a uma cobrança são caso real na doc."""
        self.assertEqual(metodo_de("TRANSFER"), Pagamento.Metodo.OUTRO)
        self.assertEqual(metodo_de("DEPOSIT"), Pagamento.Metodo.OUTRO)
        self.assertEqual(metodo_de("UNDEFINED"), Pagamento.Metodo.OUTRO)

    def test_debito_e_credito_caem_em_cartao(self):
        self.assertEqual(metodo_de("DEBIT_CARD"), Pagamento.Metodo.CARTAO)
        self.assertEqual(metodo_de("CREDIT_CARD"), Pagamento.Metodo.CARTAO)


class CriarPagadorTests(SimpleTestCase):
    def test_manda_nome_e_documento_e_devolve_o_id(self):
        visto = {}

        def handler(request: httpx.Request) -> httpx.Response:
            visto["url"] = str(request.url)
            visto["corpo"] = json.loads(request.read().decode())
            return httpx.Response(200, json={"id": "cus_000005219613"})

        pagador = _gateway(handler).criar_pagador(
            DadosPagador(
                nome="Maria Souza",
                documento="52998224725",
                email="maria@exemplo.com",
                referencia_externa="7",
            )
        )

        self.assertEqual(pagador.id_externo, "cus_000005219613")
        self.assertIn("/customers", visto["url"])
        self.assertEqual(visto["corpo"]["cpfCnpj"], "52998224725")
        self.assertEqual(visto["corpo"]["name"], "Maria Souza")
        self.assertEqual(visto["corpo"]["externalReference"], "7")

    def test_omite_opcionais_vazios(self):
        """`"email": ""` seria validado como formato inválido, não ignorado."""
        visto = {}

        def handler(request: httpx.Request) -> httpx.Response:
            visto["corpo"] = json.loads(request.read().decode())
            return httpx.Response(200, json={"id": "cus_1"})

        _gateway(handler).criar_pagador(
            DadosPagador(nome="Maria", documento="52998224725")
        )

        self.assertNotIn("email", visto["corpo"])
        self.assertNotIn("mobilePhone", visto["corpo"])
        self.assertNotIn("externalReference", visto["corpo"])

    def test_sucesso_sem_id_vira_temporario(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"object": "customer"})

        with self.assertRaises(ErroTemporario):
            _gateway(handler).criar_pagador(
                DadosPagador(nome="Maria", documento="52998224725")
            )


class CriarCobrancaTests(SimpleTestCase):
    def _dados(self, **kwargs) -> DadosCobranca:
        base = {
            "pagador": Pagador(id_externo="cus_G7Dvo4iphUNk"),
            "valor": Decimal("1000.00"),
            "vencimento": date(2026, 3, 10),
            "descricao": "Mensalidade 03/2026",
            "referencia_externa": "42",
        }
        base.update(kwargs)
        return DadosCobranca(**base)

    def _captura(self, resposta=None):
        visto = {}

        def handler(request: httpx.Request) -> httpx.Response:
            visto["url"] = str(request.url)
            visto["corpo"] = json.loads(request.read().decode())
            return httpx.Response(200, json=resposta or COBRANCA_PENDENTE)

        return visto, handler

    def test_sem_metodo_deixa_o_pagador_escolher(self):
        """Mensalidade: a família decide entre Pix e boleto na hora."""
        visto, handler = self._captura()
        _gateway(handler).criar_cobranca(self._dados())
        self.assertEqual(visto["corpo"]["billingType"], "UNDEFINED")

    def test_metodo_fixo_vai_traduzido(self):
        visto, handler = self._captura()
        _gateway(handler).criar_cobranca(self._dados(metodo="pix"))
        self.assertEqual(visto["corpo"]["billingType"], "PIX")

    def test_manda_valor_vencimento_e_referencia(self):
        visto, handler = self._captura()
        _gateway(handler).criar_cobranca(self._dados())
        corpo = visto["corpo"]
        self.assertEqual(corpo["value"], 1000.0)
        self.assertEqual(corpo["dueDate"], "2026-03-10")
        self.assertEqual(corpo["externalReference"], "42")
        self.assertEqual(corpo["customer"], "cus_G7Dvo4iphUNk")

    def test_multa_e_juros_do_contrato_vao_no_payload(self):
        """Sem isso o atraso sai cobrado pelo valor de face no boleto."""
        visto, handler = self._captura()
        _gateway(handler).criar_cobranca(
            self._dados(
                multa_percentual=Decimal("2.00"),
                juros_mes_percentual=Decimal("1.00"),
            )
        )
        corpo = visto["corpo"]
        self.assertEqual(corpo["fine"], {"value": 2.0, "type": "PERCENTAGE"})
        # `interest` não aceita `type` — mandar faria o Asaas recusar.
        self.assertEqual(corpo["interest"], {"value": 1.0})

    def test_contrato_sem_clausula_nao_manda_multa_nem_juros(self):
        visto, handler = self._captura()
        _gateway(handler).criar_cobranca(self._dados())
        self.assertNotIn("fine", visto["corpo"])
        self.assertNotIn("interest", visto["corpo"])

    def test_devolve_id_link_e_situacao(self):
        _, handler = self._captura()
        cobranca = _gateway(handler).criar_cobranca(self._dados())
        self.assertEqual(cobranca.id_externo, "pay_080225913252")
        self.assertEqual(cobranca.situacao, SituacaoCobranca.PENDENTE)
        self.assertEqual(cobranca.valor, Decimal("1000.00"))
        self.assertEqual(cobranca.vencimento, date(2026, 3, 10))
        self.assertEqual(
            cobranca.link_pagamento, "https://www.asaas.com/i/080225913252"
        )
        self.assertIsNone(cobranca.valor_pago)


class ConsultarCobrancaTests(SimpleTestCase):
    def _handler(self, resposta):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=resposta)

        return handler

    def test_recebida_traz_valor_pago_e_data(self):
        cobranca = _gateway(self._handler(COBRANCA_RECEBIDA)).consultar_cobranca(
            "pay_080225913252"
        )
        self.assertEqual(cobranca.situacao, SituacaoCobranca.PAGO)
        # `value`, não `netValue`: o líquido já desconta a tarifa deles e
        # deixaria saldo residual em toda fatura.
        self.assertEqual(cobranca.valor_pago, Decimal("1025.50"))

    def test_data_de_pagamento_e_a_do_cliente(self):
        """`clientPaymentDate` é quando a família pagou — a prova de quitação."""
        cobranca = _gateway(self._handler(COBRANCA_RECEBIDA)).consultar_cobranca(
            "pay_1"
        )
        self.assertEqual(cobranca.data_pagamento, date(2026, 3, 15))

    def test_sem_data_do_cliente_cai_na_de_liquidacao(self):
        resposta = {**COBRANCA_RECEBIDA, "clientPaymentDate": None}
        cobranca = _gateway(self._handler(resposta)).consultar_cobranca("pay_1")
        self.assertEqual(cobranca.data_pagamento, date(2026, 3, 16))

    def test_pendente_nao_tem_valor_pago(self):
        """Zero seria ambíguo com estorno total."""
        cobranca = _gateway(self._handler(COBRANCA_PENDENTE)).consultar_cobranca(
            "pay_1"
        )
        self.assertIsNone(cobranca.valor_pago)

    def test_removida_e_cancelada_mesmo_com_status_pendente(self):
        """`deleted` ganha do `status`: removida continua PENDING pra eles.

        Ler só o status faria a conciliação tratar como viva uma cobrança
        que a escola já baixou.
        """
        resposta = {**COBRANCA_PENDENTE, "deleted": True}
        cobranca = _gateway(self._handler(resposta)).consultar_cobranca("pay_1")
        self.assertEqual(cobranca.situacao, SituacaoCobranca.CANCELADO)

    def test_confirmado_nao_vira_pago(self):
        """Pix em bloqueio cautelar pode virar estorno em até 72h."""
        resposta = {**COBRANCA_RECEBIDA, "status": "CONFIRMED"}
        cobranca = _gateway(self._handler(resposta)).consultar_cobranca("pay_1")
        self.assertEqual(cobranca.situacao, SituacaoCobranca.PENDENTE)
        self.assertIsNone(cobranca.valor_pago)

    def test_data_ilegivel_nao_derruba_a_leitura(self):
        resposta = {**COBRANCA_RECEBIDA, "clientPaymentDate": "15/03/2026"}
        cobranca = _gateway(self._handler(resposta)).consultar_cobranca("pay_1")
        # Cai no fallback; valor e situação seguem legíveis.
        self.assertEqual(cobranca.data_pagamento, date(2026, 3, 16))
        self.assertEqual(cobranca.situacao, SituacaoCobranca.PAGO)

    def test_sem_vencimento_vira_temporario(self):
        resposta = {**COBRANCA_PENDENTE, "dueDate": None}
        with self.assertRaises(ErroTemporario):
            _gateway(self._handler(resposta)).consultar_cobranca("pay_1")


class CancelarCobrancaTests(SimpleTestCase):
    def test_apaga_e_releia_para_devolver_a_cobranca(self):
        """O `DELETE` deles responde só `{deleted, id}` — daí a releitura."""
        chamadas = []

        def handler(request: httpx.Request) -> httpx.Response:
            chamadas.append(request.method)
            if request.method == "DELETE":
                return httpx.Response(
                    200, json={"deleted": True, "id": "pay_080225913252"}
                )
            return httpx.Response(
                200, json={**COBRANCA_PENDENTE, "deleted": True}
            )

        cobranca = _gateway(handler).cancelar_cobranca("pay_080225913252")

        self.assertEqual(chamadas, ["DELETE", "GET"])
        self.assertEqual(cobranca.situacao, SituacaoCobranca.CANCELADO)

    def test_remocao_nao_confirmada_vira_permanente(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"deleted": False, "id": "pay_1"})

        with self.assertRaises(ErroPermanente):
            _gateway(handler).cancelar_cobranca("pay_1")
