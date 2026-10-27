"""Testes do transporte do Asaas.

Nenhum toca a rede: `httpx.MockTransport` devolve a resposta que o teste
escreve, e é o motivo de o client receber `transport` no construtor. As
respostas de erro abaixo são as da documentação deles, copiadas no
formato real (`errors: [{code, description}]`) — testar contra um formato
inventado provaria só que o código concorda consigo mesmo.
"""
import json
from decimal import Decimal

import httpx
from django.test import SimpleTestCase

from apps.financeiro.gateways import ErroPermanente, ErroTemporario, SituacaoCobranca
from apps.financeiro.gateways.asaas import (
    PRODUCAO,
    SANDBOX,
    SITUACAO_POR_STATUS,
    ClienteAsaas,
    situacao_de,
    valor_para_json,
)


def _cliente(handler, **kwargs) -> ClienteAsaas:
    kwargs.setdefault("api_key", "$aact_hmlg_chave")
    kwargs.setdefault("base_url", SANDBOX)
    return ClienteAsaas(transport=httpx.MockTransport(handler), **kwargs)


class HeadersTests(SimpleTestCase):
    def test_manda_access_token_user_agent_e_content_type(self):
        """Os três são exigidos pela documentação.

        O `User-Agent` é o menos óbvio: obrigatório pra conta raiz criada
        a partir de 13/06/2024, e sem ele a recusa não diz o motivo.
        """
        capturado = {}

        def handler(request: httpx.Request) -> httpx.Response:
            capturado.update(request.headers)
            return httpx.Response(200, json={"id": "cus_1"})

        _cliente(handler).post("/customers", {"name": "Ana"})

        self.assertEqual(capturado["access_token"], "$aact_hmlg_chave")
        self.assertEqual(capturado["user-agent"], "diario-escolar")
        self.assertEqual(capturado["content-type"], "application/json")

    def test_monta_a_url_a_partir_do_ambiente(self):
        visto = {}

        def handler(request: httpx.Request) -> httpx.Response:
            visto["url"] = str(request.url)
            return httpx.Response(200, json={})

        _cliente(handler, base_url=PRODUCAO).get("/payments/pay_1")

        self.assertEqual(visto["url"], f"{PRODUCAO}/payments/pay_1")


class ConfiguracaoTests(SimpleTestCase):
    def test_sem_chave_falha_ao_chamar_e_nao_ao_construir(self):
        """Ambiente sem a env não pode quebrar o boot.

        O financeiro opera sem gateway — a escola registra Pix e dinheiro
        na mão. Só quem tenta emitir cobrança é que descobre que falta
        configuração, e a mensagem diz o nome da env.
        """
        cliente = ClienteAsaas(api_key="", base_url=SANDBOX)

        with self.assertRaises(ErroPermanente) as ctx:
            cliente.post("/payments", {})

        self.assertEqual(ctx.exception.codigo, "sem_chave")
        self.assertIn("ASAAS_API_KEY", ctx.exception.mensagem)


class ErroTests(SimpleTestCase):
    def _erro(self, status: int, corpo):
        def handler(request: httpx.Request) -> httpx.Response:
            if isinstance(corpo, str):
                return httpx.Response(status, text=corpo)
            return httpx.Response(status, json=corpo)

        return handler

    def test_401_vira_erro_permanente_com_o_codigo_deles(self):
        """Chave errada não melhora com retentativa."""
        corpo = {
            "errors": [
                {
                    "code": "invalid_access_token",
                    "description": "A chave de API fornecida é inválida",
                }
            ]
        }

        with self.assertRaises(ErroPermanente) as ctx:
            _cliente(self._erro(401, corpo)).post("/payments", {})

        self.assertEqual(ctx.exception.codigo, "invalid_access_token")
        self.assertEqual(
            ctx.exception.mensagem, "A chave de API fornecida é inválida"
        )

    def test_401_de_ambiente_trocado_chega_legivel(self):
        """O erro mais provável na virada sandbox -> produção."""
        corpo = {
            "errors": [
                {
                    "code": "invalid_environment",
                    "description": (
                        "A chave de API informada não pertence a este ambiente"
                    ),
                }
            ]
        }

        with self.assertRaises(ErroPermanente) as ctx:
            _cliente(self._erro(401, corpo)).post("/payments", {})

        self.assertEqual(ctx.exception.codigo, "invalid_environment")

    def test_400_de_payload_vira_permanente(self):
        corpo = {
            "errors": [
                {"code": "invalid_cpfCnpj", "description": "CPF ou CNPJ inválido"}
            ]
        }

        with self.assertRaises(ErroPermanente):
            _cliente(self._erro(400, corpo)).post("/customers", {})

    def test_500_vira_temporario(self):
        """Indisponibilidade deles passa; vale tentar de novo."""
        with self.assertRaises(ErroTemporario) as ctx:
            _cliente(self._erro(500, {})).post("/payments", {})

        self.assertEqual(ctx.exception.codigo, "indisponivel")

    def test_429_vira_temporario(self):
        with self.assertRaises(ErroTemporario) as ctx:
            _cliente(self._erro(429, {})).post("/payments", {})

        self.assertEqual(ctx.exception.codigo, "rate_limit")

    def test_502_em_html_nao_estoura_ao_ler_o_corpo(self):
        """Proxy no meio responde HTML, não o JSON de erro deles.

        Sem tolerar isso, a falha real (502) viraria um `ValueError` de
        parse e o erro que chegaria ao Sentry seria o errado.
        """
        with self.assertRaises(ErroTemporario) as ctx:
            _cliente(self._erro(502, "<html>Bad Gateway</html>")).get("/payments")

        self.assertEqual(ctx.exception.codigo, "indisponivel")

    def test_timeout_vira_temporario(self):
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.TimeoutException("demorou", request=request)

        with self.assertRaises(ErroTemporario) as ctx:
            _cliente(handler).post("/payments", {})

        self.assertEqual(ctx.exception.codigo, "timeout")

    def test_falha_de_rede_vira_temporario(self):
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("sem rota", request=request)

        with self.assertRaises(ErroTemporario) as ctx:
            _cliente(handler).post("/payments", {})

        self.assertEqual(ctx.exception.codigo, "falha_de_rede")

    def test_sucesso_com_corpo_nao_json_vira_temporario(self):
        """200 em HTML quer dizer que quem respondeu não foi a API."""

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, text="<html>manutenção</html>")

        with self.assertRaises(ErroTemporario) as ctx:
            _cliente(handler).get("/payments")

        self.assertEqual(ctx.exception.codigo, "resposta_invalida")


class RespostaTests(SimpleTestCase):
    def test_devolve_o_json_do_corpo(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"id": "cus_1", "name": "Ana"})

        dados = _cliente(handler).post("/customers", {"name": "Ana"})

        self.assertEqual(dados["id"], "cus_1")

    def test_corpo_vazio_nao_e_erro(self):
        """`DELETE` pode responder 200 sem corpo."""

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200)

        self.assertEqual(_cliente(handler).delete("/payments/pay_1"), {})

    def test_manda_o_payload_como_json(self):
        visto = {}

        def handler(request: httpx.Request) -> httpx.Response:
            visto["corpo"] = json.loads(request.content)
            return httpx.Response(200, json={})

        _cliente(handler).post("/customers", {"name": "Ana", "cpfCnpj": "529"})

        self.assertEqual(visto["corpo"], {"name": "Ana", "cpfCnpj": "529"})


class SituacaoTests(SimpleTestCase):
    def test_recebido_e_o_unico_caminho_normal_pra_pago(self):
        self.assertEqual(situacao_de("RECEIVED"), SituacaoCobranca.PAGO)
        self.assertEqual(situacao_de("RECEIVED_IN_CASH"), SituacaoCobranca.PAGO)

    def test_confirmado_nao_e_pago(self):
        """A armadilha do Pix: `CONFIRMED` pode virar `REFUNDED` em 72h.

        Tratar como pago marcaria a fatura liquidada e o estorno chegaria
        depois, com a escola já tendo dado baixa.
        """
        self.assertEqual(situacao_de("CONFIRMED"), SituacaoCobranca.PENDENTE)

    def test_vencido(self):
        self.assertEqual(situacao_de("OVERDUE"), SituacaoCobranca.VENCIDO)

    def test_estorno_e_disputa_voltam_a_pendente(self):
        """Dinheiro que saiu deixa a fatura devida de novo, não cancelada."""
        for status in (
            "REFUNDED",
            "REFUND_REQUESTED",
            "CHARGEBACK_REQUESTED",
            "CHARGEBACK_DISPUTE",
        ):
            with self.subTest(status=status):
                self.assertEqual(situacao_de(status), SituacaoCobranca.PENDENTE)

    def test_status_desconhecido_vira_pendente_sem_estourar(self):
        """O Asaas pode acrescentar estado sem avisar.

        Estourar derrubaria a conciliação de todas as faturas por causa
        de uma; pendente não escreve dinheiro nem cancela nada.
        """
        self.assertEqual(situacao_de("ESTADO_NOVO"), SituacaoCobranca.PENDENTE)

    def test_mapa_cobre_os_catorze_status_documentados(self):
        """Trava o mapa contra o enum que a documentação deles publica.

        Se um sumir daqui numa edição, é este teste que avisa.
        """
        documentados = {
            "PENDING",
            "RECEIVED",
            "CONFIRMED",
            "OVERDUE",
            "REFUNDED",
            "RECEIVED_IN_CASH",
            "REFUND_REQUESTED",
            "REFUND_IN_PROGRESS",
            "CHARGEBACK_REQUESTED",
            "CHARGEBACK_DISPUTE",
            "AWAITING_CHARGEBACK_REVERSAL",
            "DUNNING_REQUESTED",
            "DUNNING_RECEIVED",
            "AWAITING_RISK_ANALYSIS",
        }
        self.assertEqual(set(SITUACAO_POR_STATUS), documentados)


class ValorTests(SimpleTestCase):
    def test_converte_decimal_preservando_os_centavos(self):
        self.assertEqual(valor_para_json(Decimal("250.00")), 250.0)
        self.assertEqual(valor_para_json(Decimal("1234.57")), 1234.57)

    def test_sobrevive_ao_round_trip_de_json(self):
        """O que importa não é o float, é o que chega do outro lado.

        `json.dumps` emite a menor representação que volta ao mesmo
        float, então o decimal reconstruído tem que bater com o original.
        """
        for bruto in ("0.01", "99.99", "250.00", "1234.57", "99999999.99"):
            with self.subTest(valor=bruto):
                enviado = json.loads(json.dumps(valor_para_json(Decimal(bruto))))
                self.assertEqual(Decimal(str(enviado)), Decimal(bruto))

    def test_arredonda_pra_centavo(self):
        """Pega a conversão sem arredondar, que mandaria `10.005` cru.

        Não distingue `ROUND_HALF_UP` de `round()` — neste valor os dois
        coincidem. O que ele trava é que o valor sai quantizado em
        centavos, e não com a terceira casa que o `Decimal` aceita.
        """
        self.assertEqual(valor_para_json(Decimal("10.005")), 10.01)
        self.assertEqual(valor_para_json(Decimal("10.0049")), 10.0)
