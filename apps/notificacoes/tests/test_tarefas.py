"""Testes do command de retentativa e da rota que o dispara.

A rota é a segunda sem autenticação de usuário do projeto e a primeira
que **executa** algo, então os testes de recusa valem tanto quanto os de
sucesso.
"""
from datetime import timedelta
from unittest import mock

from django.core import mail
from django.core.mail import EmailMultiAlternatives
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.escola.models import Escola
from apps.notificacoes.management.commands.notificacoes_reenviar import (
    TETO_TENTATIVAS,
    pendentes,
)
from apps.notificacoes.models import Mensagem

TOKEN = "token-de-teste-bem-comprido"


class _Base(TestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        cls.escola = Escola.objects.create(nome="Escola A")

    @classmethod
    def _mensagem(cls, **kwargs) -> Mensagem:
        campos = {
            "escola": cls.escola,
            "origem": Mensagem.Origem.OCORRENCIA,
            "destinatario": "mae@example.com",
            "assunto": "Assunto",
            "corpo_texto": "corpo",
            "status": Mensagem.Status.PENDENTE,
        }
        campos.update(kwargs)
        return Mensagem.objects.create(**campos)

    @classmethod
    def _envelhecer(cls, mensagem, minutos: int) -> Mensagem:
        """`criado_em` é `auto_now_add`, então envelhecer exige UPDATE."""
        Mensagem.objects.filter(pk=mensagem.pk).update(
            criado_em=timezone.now() - timedelta(minutes=minutos)
        )
        mensagem.refresh_from_db()
        return mensagem


class SelecaoParaReenvioTests(_Base):
    """Os quatro filtros, um teste por motivo."""

    def test_pega_pendente_antiga_o_bastante(self):
        mensagem = self._envelhecer(self._mensagem(), 30)
        self.assertIn(mensagem, pendentes())

    def test_ignora_recem_criada(self):
        """Pode estar sendo enviada pela thread viva — pegar duplicaria."""
        recente = self._envelhecer(self._mensagem(), 1)
        self.assertNotIn(recente, pendentes())

    def test_ignora_mais_velha_que_o_teto(self):
        """Aviso que chega uma semana depois confunde em vez de informar."""
        velha = self._envelhecer(self._mensagem(), 60 * 48)
        self.assertNotIn(velha, pendentes())

    def test_ignora_quem_estourou_as_tentativas(self):
        """Endereço inválido falha sempre, e insistir queima a cota."""
        teimosa = self._envelhecer(
            self._mensagem(
                status=Mensagem.Status.FALHOU, tentativas=TETO_TENTATIVAS
            ),
            30,
        )
        self.assertNotIn(teimosa, pendentes())

    def test_ignora_origem_nao_retentavel(self):
        """Link de senha reenviado depois de uma hora chega morto."""
        senha = self._envelhecer(
            self._mensagem(origem=Mensagem.Origem.SENHA), 30
        )
        self.assertNotIn(senha, pendentes())

    def test_ignora_o_que_ja_saiu(self):
        enviada = self._envelhecer(
            self._mensagem(status=Mensagem.Status.ENVIADO), 30
        )
        self.assertNotIn(enviada, pendentes())

    def test_pega_falhou_que_ainda_tem_tentativa(self):
        """Cota estourada é falha transitória: retentar é o ponto."""
        falhou = self._envelhecer(
            self._mensagem(status=Mensagem.Status.FALHOU, tentativas=1), 30
        )
        self.assertIn(falhou, pendentes())


@override_settings(TAREFAS_TOKEN=TOKEN)
class RotaDeTarefasTests(_Base):
    def setUp(self) -> None:
        self.client = APIClient()
        self.url = reverse("api_v1:tarefas-executar")

    def test_sem_token_recusa(self):
        self.assertEqual(self.client.post(self.url).status_code, 401)

    def test_token_errado_recusa(self):
        resposta = self.client.post(self.url, HTTP_X_TAREFAS_TOKEN="errado")
        self.assertEqual(resposta.status_code, 401)

    @override_settings(TAREFAS_TOKEN="")
    def test_sem_token_configurado_recusa_mesmo_com_header(self):
        """Instalação sem configuração não pode nascer com rota aberta."""
        resposta = self.client.post(self.url, HTTP_X_TAREFAS_TOKEN=TOKEN)
        self.assertEqual(resposta.status_code, 401)

    @override_settings(TAREFAS_TOKEN="")
    def test_env_vazia_e_header_vazio_tambem_recusa(self):
        """O caso que o guard de env vazia existe pra barrar.

        `compare_digest("", "")` é **verdadeiro**: sem a checagem de
        `esperado` vazio, instalação sem `TAREFAS_TOKEN` aceitaria
        qualquer request que simplesmente não manda o header — rota
        aberta pra executar command.

        O teste vizinho, que manda o token cheio, NÃO cobre isto:
        `compare_digest(token, "")` é falso de qualquer forma, então ele
        passava com e sem o guard. Teste de mutação pegou.
        """
        self.assertEqual(
            self.client.post(self.url, HTTP_X_TAREFAS_TOKEN="").status_code, 401
        )
        self.assertEqual(self.client.post(self.url).status_code, 401)

    def test_token_certo_executa_e_reenvia(self):
        mensagem = self._envelhecer(self._mensagem(), 30)
        resposta = self.client.post(
            f"{self.url}?tarefas=email", HTTP_X_TAREFAS_TOKEN=TOKEN
        )
        self.assertEqual(resposta.status_code, 200)
        self.assertTrue(resposta.json()["resultados"]["email"]["ok"])

        mensagem.refresh_from_db()
        self.assertEqual(mensagem.status, Mensagem.Status.ENVIADO)
        self.assertEqual(len(mail.outbox), 1)

    def test_tarefa_desconhecida_recusa_o_lote(self):
        """Workflow escrito errado precisa ver o erro, não rodar metade."""
        resposta = self.client.post(
            f"{self.url}?tarefas=email,inventada", HTTP_X_TAREFAS_TOKEN=TOKEN
        )
        self.assertEqual(resposta.status_code, 400)
        self.assertIn("email", resposta.json()["disponiveis"])

    def test_nome_de_command_do_corpo_nao_e_executado(self):
        """O ponto central de segurança: a lista de permissão.

        Aceitar o nome que vem na request seria `call_command` com
        entrada externa — inclusive os commands de dados de demonstração.
        """
        resposta = self.client.post(
            f"{self.url}?tarefas=popular_alunos_mock",
            HTTP_X_TAREFAS_TOKEN=TOKEN,
        )
        self.assertEqual(resposta.status_code, 400)

    def test_falha_de_uma_tarefa_nao_impede_as_outras(self):
        mensagem = self._envelhecer(self._mensagem(), 30)
        with mock.patch(
            "apps.notificacoes.tarefas.TAREFAS",
            {"email": "notificacoes_reenviar", "quebrada": "comando_que_nao_existe"},
        ):
            resposta = self.client.post(self.url, HTTP_X_TAREFAS_TOKEN=TOKEN)

        self.assertEqual(resposta.status_code, 200)
        resultados = resposta.json()["resultados"]
        self.assertTrue(resultados["email"]["ok"])
        self.assertFalse(resultados["quebrada"]["ok"])
        mensagem.refresh_from_db()
        self.assertEqual(mensagem.status, Mensagem.Status.ENVIADO)

    def test_nao_reenvia_duas_vezes(self):
        self._envelhecer(self._mensagem(), 30)
        self.client.post(f"{self.url}?tarefas=email", HTTP_X_TAREFAS_TOKEN=TOKEN)
        self.client.post(f"{self.url}?tarefas=email", HTTP_X_TAREFAS_TOKEN=TOKEN)
        self.assertEqual(len(mail.outbox), 1)

    def test_reenvio_que_falha_de_novo_conta_tentativa(self):
        mensagem = self._envelhecer(self._mensagem(), 30)
        with mock.patch.object(
            EmailMultiAlternatives,
            "send",
            side_effect=ConnectionError("ainda fora"),
        ):
            self.client.post(
                f"{self.url}?tarefas=email", HTTP_X_TAREFAS_TOKEN=TOKEN
            )
        mensagem.refresh_from_db()
        self.assertEqual(mensagem.status, Mensagem.Status.FALHOU)
        self.assertEqual(mensagem.tentativas, 1)
        self.assertIn("ainda fora", mensagem.erro)
