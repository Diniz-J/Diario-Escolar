"""Testes da emissão de cobrança (fatia 4) — o serviço e a action.

Nenhum teste aqui conhece o Asaas: o gateway é um dublê do contrato de
`gateways/base.py`, que é justamente o que a interface promete permitir.
A tradução pro dialeto deles é testada em `test_gateway_asaas_adapter`.

O que precisa ficar travado:

- emissão é **idempotente** pelo `id_externo` (o command do lote repete e
  o botão da tela pode ser clicado duas vezes);
- o id do pagador é **reusado**, porque criar cliente no provedor não é
  idempotente e cada emissão abriria outro cadastro;
- cadastro incompleto (sem pagador, sem CPF) vira mensagem legível, não
  erro do provedor em inglês;
- cancelar a fatura cancela a cobrança lá, e falha do provedor **não**
  impede o cancelamento aqui.
"""
from datetime import date
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.models import Usuario
from apps.escola.models import Aluno, Escola, Turma
from apps.financeiro.gateways import (
    Cobranca,
    CobrancaGateway,
    DadosCobranca,
    DadosPagador,
    ErroPermanente,
    ErroTemporario,
    Pagador,
    SituacaoCobranca,
)
from apps.financeiro.models import Fatura, PlanoCobranca
from apps.financeiro.services import (
    EmissaoRecusadaError,
    cancelar_cobranca,
    emitir_cobranca,
)
from apps.portal.models import Responsavel, ResponsavelAluno


class GatewayFalso(CobrancaGateway):
    """Dublê que grava o que recebeu e devolve o que o teste pedir."""

    def __init__(self, falha: Exception | None = None) -> None:
        self.falha = falha
        self.pagadores: list[DadosPagador] = []
        self.cobrancas: list[DadosCobranca] = []
        self.cancelados: list[str] = []

    def criar_pagador(self, dados: DadosPagador) -> Pagador:
        if self.falha:
            raise self.falha
        self.pagadores.append(dados)
        return Pagador(id_externo=f"cus_{len(self.pagadores)}")

    def criar_cobranca(self, dados: DadosCobranca) -> Cobranca:
        if self.falha:
            raise self.falha
        self.cobrancas.append(dados)
        return Cobranca(
            id_externo=f"pay_{len(self.cobrancas)}",
            situacao=SituacaoCobranca.PENDENTE,
            valor=dados.valor,
            vencimento=dados.vencimento,
            link_pagamento=f"https://pay.exemplo/{len(self.cobrancas)}",
        )

    def consultar_cobranca(self, id_externo: str) -> Cobranca:
        return Cobranca(
            id_externo=id_externo,
            situacao=SituacaoCobranca.PENDENTE,
            valor=Decimal("1000.00"),
            vencimento=date(2026, 3, 10),
        )

    def cancelar_cobranca(self, id_externo: str) -> Cobranca:
        if self.falha:
            raise self.falha
        self.cancelados.append(id_externo)
        return Cobranca(
            id_externo=id_externo,
            situacao=SituacaoCobranca.CANCELADO,
            valor=Decimal("1000.00"),
            vencimento=date(2026, 3, 10),
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
            multa_percentual=Decimal("2.00"),
            juros_mes_percentual=Decimal("1.00"),
            vigencia_inicio=date(2026, 1, 1),
        )
        self.fatura = Fatura.objects.create(
            escola=self.escola,
            plano=self.plano,
            aluno=self.ana,
            competencia=date(2026, 3, 1),
            valor=Decimal("1000.00"),
            vencimento=date(2026, 3, 10),
        )


class EmitirCobrancaTests(_Setup):
    def test_grava_id_externo_e_link(self):
        gateway = GatewayFalso()
        emitir_cobranca(self.fatura, gateway)
        self.fatura.refresh_from_db()
        self.assertEqual(self.fatura.id_externo, "pay_1")
        self.assertEqual(self.fatura.link_pagamento, "https://pay.exemplo/1")

    def test_manda_a_referencia_da_fatura(self):
        """É o que permite achar a fatura a partir do evento do provedor."""
        gateway = GatewayFalso()
        emitir_cobranca(self.fatura, gateway)
        self.assertEqual(
            gateway.cobrancas[0].referencia_externa, str(self.fatura.pk)
        )

    def test_repassa_as_clausulas_do_contrato(self):
        gateway = GatewayFalso()
        emitir_cobranca(self.fatura, gateway)
        dados = gateway.cobrancas[0]
        self.assertEqual(dados.multa_percentual, Decimal("2.00"))
        self.assertEqual(dados.juros_mes_percentual, Decimal("1.00"))

    def test_cadastra_o_pagador_e_guarda_o_id(self):
        gateway = GatewayFalso()
        emitir_cobranca(self.fatura, gateway)
        self.mae.refresh_from_db()
        self.assertEqual(self.mae.id_externo_gateway, "cus_1")
        self.assertEqual(gateway.pagadores[0].documento, "52998224725")

    def test_reusa_o_pagador_ja_cadastrado(self):
        """Criar cliente lá não é idempotente: sem reuso, vira cadastro novo."""
        self.mae.id_externo_gateway = "cus_existente"
        self.mae.save(update_fields=["id_externo_gateway"])
        gateway = GatewayFalso()

        emitir_cobranca(self.fatura, gateway)

        self.assertEqual(gateway.pagadores, [])
        self.assertEqual(
            gateway.cobrancas[0].pagador.id_externo, "cus_existente"
        )

    def test_pagador_ja_cadastrado_nao_exige_cpf(self):
        """Quem já tem cadastro lá não precisa do CPF: o provedor não pede.

        Checar antes bloquearia a emissão de uma família já cadastrada por
        causa de um campo que ninguém mais vai usar.
        """
        self.mae.id_externo_gateway = "cus_existente"
        self.mae.cpf = ""
        self.mae.save(update_fields=["id_externo_gateway", "cpf"])

        emitir_cobranca(self.fatura, GatewayFalso())

        self.fatura.refresh_from_db()
        self.assertEqual(self.fatura.id_externo, "pay_1")

    def test_segunda_emissao_nao_cria_outra_cobranca(self):
        gateway = GatewayFalso()
        emitir_cobranca(self.fatura, gateway)
        emitir_cobranca(self.fatura, gateway)
        self.assertEqual(len(gateway.cobrancas), 1)

    def test_salvar_o_pagador_nao_mexe_na_senha(self):
        """`update_fields` enxuto: esta função não tem a ver com credencial."""
        self.mae.set_password("segredo")
        self.mae.save()
        hash_antes = Responsavel.objects.get(pk=self.mae.pk).password

        emitir_cobranca(self.fatura, GatewayFalso())

        self.assertEqual(
            Responsavel.objects.get(pk=self.mae.pk).password, hash_antes
        )

    def test_plano_sem_pagador(self):
        self.plano.pagador = None
        self.plano.save(update_fields=["pagador"])
        with self.assertRaises(EmissaoRecusadaError) as ctx:
            emitir_cobranca(self.fatura, GatewayFalso())
        self.assertIn("pagador", str(ctx.exception).lower())

    def test_pagador_sem_cpf(self):
        self.mae.cpf = ""
        self.mae.save(update_fields=["cpf"])
        with self.assertRaises(EmissaoRecusadaError) as ctx:
            emitir_cobranca(self.fatura, GatewayFalso())
        self.assertIn("CPF", str(ctx.exception))

    def test_fatura_cancelada_nao_vai_pro_gateway(self):
        self.fatura.status = Fatura.Status.CANCELADO
        self.fatura.save(update_fields=["status"])
        with self.assertRaises(EmissaoRecusadaError):
            emitir_cobranca(self.fatura, GatewayFalso())

    def test_fatura_paga_nao_vai_pro_gateway(self):
        """Emitir cobrança do que já foi recebido é cobrar duas vezes."""
        self.fatura.status = Fatura.Status.PAGO
        self.fatura.valor_pago = Decimal("1000.00")
        self.fatura.data_pagamento = date(2026, 3, 9)
        self.fatura.save()
        with self.assertRaises(EmissaoRecusadaError):
            emitir_cobranca(self.fatura, GatewayFalso())

    def test_falha_do_provedor_nao_deixa_a_fatura_meio_emitida(self):
        with self.assertRaises(ErroTemporario):
            emitir_cobranca(
                self.fatura, GatewayFalso(falha=ErroTemporario("caiu"))
            )
        self.fatura.refresh_from_db()
        self.assertEqual(self.fatura.id_externo, "")
        self.assertEqual(self.fatura.link_pagamento, "")


class CancelarCobrancaTests(_Setup):
    def test_cancela_lá_e_limpa_o_ponteiro_aqui(self):
        gateway = GatewayFalso()
        emitir_cobranca(self.fatura, gateway)

        self.assertTrue(cancelar_cobranca(self.fatura, gateway))

        self.fatura.refresh_from_db()
        self.assertEqual(gateway.cancelados, ["pay_1"])
        self.assertEqual(self.fatura.id_externo, "")
        self.assertEqual(self.fatura.link_pagamento, "")

    def test_fatura_nunca_emitida_nao_chama_o_provedor(self):
        gateway = GatewayFalso()
        self.assertFalse(cancelar_cobranca(self.fatura, gateway))
        self.assertEqual(gateway.cancelados, [])

    def test_falha_do_provedor_nao_propaga(self):
        """Cancelar aqui é decisão já tomada: indisponibilidade lá não manda."""
        gateway = GatewayFalso()
        emitir_cobranca(self.fatura, gateway)
        gateway.falha = ErroPermanente("recusou")

        self.assertFalse(cancelar_cobranca(self.fatura, gateway))

        self.fatura.refresh_from_db()
        # O ponteiro fica: a cobrança continua viva lá, e apagar o id aqui
        # perderia o único jeito de achá-la depois.
        self.assertEqual(self.fatura.id_externo, "pay_1")


class EmitirPelaApiTests(_Setup):
    """A action: permissão, gateway ausente e tradução de erro pra 400."""

    def setUp(self) -> None:
        super().setUp()
        self.client = APIClient()
        self.diretora = Usuario.objects.create_user(
            username="diretora",
            password="x",
            perfil=Usuario.Perfil.DIRETOR,
            escola=self.escola,
        )
        self.professor = Usuario.objects.create_user(
            username="professor",
            password="x",
            perfil=Usuario.Perfil.PROFESSOR,
            escola=self.escola,
        )

    def url(self) -> str:
        return reverse("api_v1:fatura-emitir-cobranca", args=[self.fatura.pk])

    def test_professor_leva_403(self):
        self.client.force_authenticate(user=self.professor)
        self.assertEqual(self.client.post(self.url()).status_code, 403)

    def test_sem_gateway_configurado_responde_400_explicando(self):
        """Sem chave, a instalação opera sem cobrança online — não é 500."""
        self.client.force_authenticate(user=self.diretora)
        with self.settings(ASAAS_API_KEY=""):
            resposta = self.client.post(self.url())
        self.assertEqual(resposta.status_code, 400)
        self.assertIn("não está configurada", resposta.data["detail"])
