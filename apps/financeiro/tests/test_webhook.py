"""Testes do webhook e da conciliação automática (fatia 5).

O que a fatia promete e precisa ficar travado:

- **token obrigatório**, e recusa quando a env não está configurada (o
  endpoint é a única rota sem autenticação do projeto);
- **reentrega não duplica pagamento** — é comportamento normal do Asaas,
  não erro;
- **o valor vem da reconsulta, não do corpo do evento**: o token prova
  quem mandou, não quanto entrou;
- falha de processamento responde **200** com o erro registrado, porque 15
  falhas consecutivas pausam a fila deles e param a escola inteira;
- o responsável é avisado pelos **vínculos**, com uma mensagem por pessoa.
"""
from dataclasses import replace
from datetime import date
from decimal import Decimal

from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.escola.models import Aluno, Escola, Turma
from apps.financeiro.gateways import (
    Cobranca,
    CobrancaGateway,
    DadosCobranca,
    DadosPagador,
    ErroTemporario,
    Pagador,
    SituacaoCobranca,
)
from apps.financeiro.models import EventoWebhook, Fatura, Pagamento, PlanoCobranca
from apps.financeiro.services import conciliar_cobranca
from apps.portal.models import Responsavel, ResponsavelAluno

URL = reverse("api_v1:webhook-asaas")
TOKEN = "token-do-hook"


def corpo_evento(
    id_evento="evt_05b708f961d739ea7eba7e4db318f621&368604920",
    tipo="PAYMENT_RECEIVED",
    id_cobranca="pay_080225913252",
    referencia="",
    valor=1000.0,
) -> dict:
    """Corpo no formato do exemplo da documentação deles."""
    return {
        "id": id_evento,
        "event": tipo,
        "dateCreated": "2026-03-15 16:45:03",
        "account": {"id": "47ed0d25-f9fb-4b35-b23a-d8895caf92b7", "ownerId": None},
        "payment": {
            "object": "payment",
            "id": id_cobranca,
            "value": valor,
            "status": "RECEIVED",
            "dueDate": "2026-03-10",
            "externalReference": referencia,
            "billingType": "PIX",
            "deleted": False,
        },
    }


class GatewayDublê(CobrancaGateway):
    """Devolve a cobrança que o teste definir, contando as consultas."""

    def __init__(self, cobranca: Cobranca | None = None, falha=None) -> None:
        self.cobranca = cobranca
        self.falha = falha
        self.consultas: list[str] = []

    def criar_pagador(self, dados: DadosPagador) -> Pagador:
        return Pagador(id_externo="cus_1")

    def criar_cobranca(self, dados: DadosCobranca) -> Cobranca:
        raise NotImplementedError

    def consultar_cobranca(self, id_externo: str) -> Cobranca:
        self.consultas.append(id_externo)
        if self.falha:
            raise self.falha
        return self.cobranca

    def cancelar_cobranca(self, id_externo: str) -> Cobranca:
        raise NotImplementedError


def cobranca_paga(valor="1000.00", data=date(2026, 3, 15)) -> Cobranca:
    return Cobranca(
        id_externo="pay_080225913252",
        situacao=SituacaoCobranca.PAGO,
        valor=Decimal(valor),
        vencimento=date(2026, 3, 10),
        valor_pago=Decimal(valor),
        data_pagamento=data,
        metodo=Pagamento.Metodo.PIX,
    )


class _Setup(TestCase):
    def setUp(self) -> None:
        self.escola = Escola.objects.create(nome="Escola A")
        self.turma = Turma.objects.create(
            escola=self.escola,
            nome="1A",
            turno=Turma.Turno.MATUTINO,
            ano_letivo=2026,
        )
        self.ana = Aluno.objects.create(
            escola=self.escola,
            turma=self.turma,
            matricula="001",
            nome_completo="Ana Lima",
        )
        self.mae = Responsavel.objects.create(
            escola=self.escola,
            nome="Maria Lima",
            email="maria@exemplo.com",
            cpf="52998224725",
        )
        ResponsavelAluno.objects.create(responsavel=self.mae, aluno=self.ana)
        self.plano = PlanoCobranca.objects.create(
            escola=self.escola,
            aluno=self.ana,
            pagador=self.mae,
            valor_mensalidade=Decimal("1000.00"),
            dia_vencimento=10,
            vigencia_inicio=date(2026, 1, 1),
        )
        self.fatura = Fatura.objects.create(
            escola=self.escola,
            plano=self.plano,
            aluno=self.ana,
            competencia=date(2026, 3, 1),
            valor=Decimal("1000.00"),
            vencimento=date(2026, 3, 10),
            id_externo="pay_080225913252",
        )


class ConciliarCobrancaTests(_Setup):
    """O serviço, sem webhook no caminho."""

    def test_paga_registra_pagamento_e_quita_a_fatura(self):
        pagamento = conciliar_cobranca(self.fatura, GatewayDublê(cobranca_paga()))

        self.assertIsNotNone(pagamento)
        self.fatura.refresh_from_db()
        self.assertEqual(self.fatura.status, Fatura.Status.PAGO)
        self.assertEqual(self.fatura.valor_pago, Decimal("1000.00"))
        self.assertEqual(pagamento.metodo, Pagamento.Metodo.PIX)
        self.assertEqual(pagamento.data, date(2026, 3, 15))

    def test_referencia_e_a_cobranca_nao_o_evento(self):
        """Um pagamento por cobrança: confirmação e recebimento convergem."""
        pagamento = conciliar_cobranca(self.fatura, GatewayDublê(cobranca_paga()))
        self.assertEqual(pagamento.referencia_externa, "pay_080225913252")

    def test_pendente_nao_concilia(self):
        cobranca = Cobranca(
            id_externo="pay_080225913252",
            situacao=SituacaoCobranca.PENDENTE,
            valor=Decimal("1000.00"),
            vencimento=date(2026, 3, 10),
        )
        self.assertIsNone(
            conciliar_cobranca(self.fatura, GatewayDublê(cobranca))
        )
        self.assertEqual(Pagamento.objects.count(), 0)

    def test_paga_com_juros_registra_o_valor_que_entrou(self):
        """Atraso com multa entra maior que o valor de face, e é o que vale."""
        pagamento = conciliar_cobranca(
            self.fatura, GatewayDublê(cobranca_paga(valor="1025.50"))
        )
        self.assertEqual(pagamento.valor, Decimal("1025.50"))
        self.fatura.refresh_from_db()
        self.assertEqual(self.fatura.status, Fatura.Status.PAGO)

    def test_sem_metodo_cai_em_outro(self):
        cobranca = replace(cobranca_paga(), metodo="")
        pagamento = conciliar_cobranca(self.fatura, GatewayDublê(cobranca))
        self.assertEqual(pagamento.metodo, Pagamento.Metodo.OUTRO)


@override_settings(ASAAS_WEBHOOK_TOKEN=TOKEN, ASAAS_API_KEY="$aact_chave")
class WebhookTokenTests(_Setup):
    def test_sem_token_responde_401(self):
        resposta = self.client.post(
            URL, corpo_evento(), content_type="application/json"
        )
        self.assertEqual(resposta.status_code, 401)
        self.assertEqual(EventoWebhook.objects.count(), 0)

    def test_token_errado_responde_401(self):
        resposta = self.client.post(
            URL,
            corpo_evento(),
            content_type="application/json",
            HTTP_ASAAS_ACCESS_TOKEN="outro",
        )
        self.assertEqual(resposta.status_code, 401)

    @override_settings(ASAAS_WEBHOOK_TOKEN="")
    def test_env_nao_configurada_recusa_em_vez_de_aceitar(self):
        """Instalação mal configurada não pode virar endpoint aberto."""
        resposta = self.client.post(
            URL,
            corpo_evento(),
            content_type="application/json",
            HTTP_ASAAS_ACCESS_TOKEN="qualquer",
        )
        self.assertEqual(resposta.status_code, 401)
        self.assertEqual(EventoWebhook.objects.count(), 0)


@override_settings(ASAAS_WEBHOOK_TOKEN=TOKEN, ASAAS_API_KEY="$aact_chave")
class WebhookProcessamentoTests(_Setup):
    def post(self, corpo=None, token=TOKEN):
        return self.client.post(
            URL,
            corpo if corpo is not None else corpo_evento(),
            content_type="application/json",
            HTTP_ASAAS_ACCESS_TOKEN=token,
        )

    def test_corpo_sem_id_de_evento_responde_400(self):
        corpo = corpo_evento()
        del corpo["id"]
        self.assertEqual(self.post(corpo).status_code, 400)

    def test_corpo_sem_cobranca_responde_400(self):
        corpo = corpo_evento()
        corpo["payment"] = {}
        self.assertEqual(self.post(corpo).status_code, 400)

    def test_evento_de_cobranca_desconhecida_e_registrado_sem_erro_fatal(self):
        """Conta compartilhada ou cobrança criada no painel deles."""
        resposta = self.post(corpo_evento(id_cobranca="pay_de_outro_sistema"))

        self.assertEqual(resposta.status_code, 200)
        registro = EventoWebhook.objects.get()
        self.assertIsNone(registro.fatura)
        self.assertIsNotNone(registro.processado_em)
        self.assertIn("não encontrada", registro.erro)
        self.assertEqual(Pagamento.objects.count(), 0)

    def test_guarda_o_payload_cru(self):
        self.post()
        registro = EventoWebhook.objects.get()
        self.assertEqual(registro.tipo, "PAYMENT_RECEIVED")
        self.assertEqual(registro.payload["payment"]["id"], "pay_080225913252")


@override_settings(ASAAS_WEBHOOK_TOKEN=TOKEN, ASAAS_API_KEY="$aact_chave")
class WebhookConciliacaoTests(_Setup):
    """O caminho completo, com o gateway trocado por dublê."""

    def setUp(self) -> None:
        super().setUp()
        self.gateway = GatewayDublê(cobranca_paga())
        patcher = self._patch_gateway(self.gateway)
        self.addCleanup(patcher)

    def _patch_gateway(self, gateway):
        """Troca a fábrica do gateway pelo dublê, nos dois pontos de uso."""
        from apps.financeiro import webhooks

        original = webhooks.gateway_configurado
        webhooks.gateway_configurado = lambda: gateway
        return lambda: setattr(webhooks, "gateway_configurado", original)

    def post(self, corpo=None):
        return self.client.post(
            URL,
            corpo if corpo is not None else corpo_evento(referencia=""),
            content_type="application/json",
            HTTP_ASAAS_ACCESS_TOKEN=TOKEN,
        )

    def test_concilia_e_marca_o_evento_como_processado(self):
        resposta = self.post()

        self.assertEqual(resposta.status_code, 200)
        self.fatura.refresh_from_db()
        self.assertEqual(self.fatura.status, Fatura.Status.PAGO)
        registro = EventoWebhook.objects.get()
        self.assertEqual(registro.fatura_id, self.fatura.pk)
        self.assertIsNotNone(registro.processado_em)
        self.assertEqual(registro.erro, "")

    def test_acha_a_fatura_pela_nossa_referencia(self):
        self.post(corpo_evento(referencia=str(self.fatura.pk)))
        self.fatura.refresh_from_db()
        self.assertEqual(self.fatura.status, Fatura.Status.PAGO)

    def test_valor_vem_da_reconsulta_nao_do_corpo(self):
        """O corpo diz 99,00; a reconsulta diz 1000,00. Vale a reconsulta."""
        self.post(corpo_evento(valor=99.0))

        pagamento = Pagamento.objects.get()
        self.assertEqual(pagamento.valor, Decimal("1000.00"))
        self.assertEqual(self.gateway.consultas, ["pay_080225913252"])

    def test_reentrega_do_mesmo_evento_nao_duplica_pagamento(self):
        self.post()
        self.post()

        self.assertEqual(Pagamento.objects.count(), 1)
        self.assertEqual(EventoWebhook.objects.count(), 1)

    def test_dois_eventos_do_mesmo_pagamento_nao_duplicam(self):
        """Confirmação e recebimento são eventos distintos, pagamento um só."""
        self.post(corpo_evento(id_evento="evt_1", tipo="PAYMENT_CONFIRMED"))
        self.post(corpo_evento(id_evento="evt_2", tipo="PAYMENT_RECEIVED"))

        self.assertEqual(EventoWebhook.objects.count(), 2)
        self.assertEqual(Pagamento.objects.count(), 1)

    def test_falha_de_processamento_responde_200_e_registra_o_erro(self):
        """15 falhas consecutivas pausam a fila deles — 200 protege a escola."""
        self.gateway.falha = ErroTemporario("Asaas caiu")

        resposta = self.post()

        self.assertEqual(resposta.status_code, 200)
        registro = EventoWebhook.objects.get()
        # Nulo de propósito: é o que distingue o que falhou do que foi
        # tratado, e o que permite reprocessar.
        self.assertIsNone(registro.processado_em)
        self.assertIn("Asaas caiu", registro.erro)

    def test_avisa_o_responsavel_vinculado(self):
        self.post()

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["maria@exemplo.com"])
        self.assertIn("Pagamento recebido", mail.outbox[0].subject)
        self.assertIn("Maria Lima", mail.outbox[0].body)
        self.assertIn("R$ 1.000,00", mail.outbox[0].body)

    def test_mae_e_pai_recebem_mensagens_individuais(self):
        """Endereço de um responsável não é dado do outro."""
        pai = Responsavel.objects.create(
            escola=self.escola, nome="João Lima", email="joao@exemplo.com"
        )
        ResponsavelAluno.objects.create(responsavel=pai, aluno=self.ana)

        self.post()

        self.assertEqual(len(mail.outbox), 2)
        destinos = sorted(sum((m.to for m in mail.outbox), []))
        self.assertEqual(destinos, ["joao@exemplo.com", "maria@exemplo.com"])
        for mensagem in mail.outbox:
            self.assertEqual(len(mensagem.to), 1)

    def test_opt_out_nao_recebe(self):
        self.mae.recebe_notificacao = False
        self.mae.save(update_fields=["recebe_notificacao"])

        self.post()

        self.assertEqual(len(mail.outbox), 0)
        # Mas o dinheiro foi conciliado: email é melhor-esforço.
        self.fatura.refresh_from_db()
        self.assertEqual(self.fatura.status, Fatura.Status.PAGO)

    def test_evento_sem_liquidacao_nao_manda_email(self):
        self.gateway.cobranca = Cobranca(
            id_externo="pay_080225913252",
            situacao=SituacaoCobranca.PENDENTE,
            valor=Decimal("1000.00"),
            vencimento=date(2026, 3, 10),
        )

        self.post()

        self.assertEqual(len(mail.outbox), 0)
        self.assertEqual(Pagamento.objects.count(), 0)
        registro = EventoWebhook.objects.get()
        self.assertIsNotNone(registro.processado_em)


@override_settings(ASAAS_WEBHOOK_TOKEN=TOKEN, ASAAS_API_KEY="$aact_chave")
class ResolucaoDaFaturaTests(_Setup):
    """A referência externa não pode casar com fatura de outro sistema."""

    def setUp(self) -> None:
        super().setUp()
        from apps.financeiro import webhooks

        original = webhooks.gateway_configurado
        webhooks.gateway_configurado = lambda: GatewayDublê(cobranca_paga())
        self.addCleanup(
            lambda: setattr(webhooks, "gateway_configurado", original)
        )

    def post(self, corpo):
        return self.client.post(
            URL,
            corpo,
            content_type="application/json",
            HTTP_ASAAS_ACCESS_TOKEN=TOKEN,
        )

    def test_referencia_de_outro_sistema_nao_concilia_nossa_fatura(self):
        """Conta compartilhada: o "42" deles não é a nossa fatura 42."""
        self.post(
            corpo_evento(
                id_cobranca="pay_de_outro_sistema",
                referencia=str(self.fatura.pk),
            )
        )

        self.fatura.refresh_from_db()
        # A fatura aponta pra pay_080225913252, não pra esta cobrança.
        self.assertEqual(self.fatura.status, Fatura.Status.PENDENTE)
        self.assertEqual(Pagamento.objects.count(), 0)
        self.assertIn("não encontrada", EventoWebhook.objects.get().erro)

    def test_referencia_recupera_fatura_sem_id_externo(self):
        """Emissão que criou a cobrança lá e falhou ao gravar o id aqui."""
        self.fatura.id_externo = ""
        self.fatura.save(update_fields=["id_externo"])

        self.post(
            corpo_evento(
                id_cobranca="pay_080225913252",
                referencia=str(self.fatura.pk),
            )
        )

        self.fatura.refresh_from_db()
        self.assertEqual(self.fatura.status, Fatura.Status.PAGO)
