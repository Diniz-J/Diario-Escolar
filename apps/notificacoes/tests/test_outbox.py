"""Testes do outbox de email.

O que importa aqui é a ordem: **grava, depois tenta**. É essa ordem que
faz a mensagem sobreviver ao processo que morre no meio do envio, que é
rotina no Render (deploy, restart, hibernação).
"""
from unittest import mock

from django.core import mail
from django.core.mail import EmailMultiAlternatives
from django.test import TestCase

from apps.escola.models import Escola
from apps.notificacoes.models import ORIGENS_RETENTAVEIS, Mensagem
from apps.notificacoes.services import despachar, enviar, registrar

UMA = ("Assunto", "corpo em texto", "<p>corpo em html</p>", "mae@example.com")


class RegistroTests(TestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        cls.escola = Escola.objects.create(nome="Escola A")

    def test_grava_pendente_antes_de_qualquer_tentativa(self):
        """A invariante central: a linha existe ANTES do envio.

        Sem ela, processo que morre no meio leva a mensagem junto e não
        sobra o que retomar — que era o estado anterior ao outbox.
        """
        linhas = registrar(
            [UMA], origem=Mensagem.Origem.OCORRENCIA, escola_id=self.escola.pk
        )
        self.assertEqual(len(linhas), 1)
        gravada = Mensagem.objects.get()
        self.assertEqual(gravada.status, Mensagem.Status.PENDENTE)
        self.assertEqual(gravada.tentativas, 0)
        self.assertIsNone(gravada.enviado_em)
        # Nada saiu: `registrar` não envia.
        self.assertEqual(mail.outbox, [])

    def test_sem_escola_e_aceito(self):
        """Reset de senha do admin global não tem escola.

        É por isso que o modelo não herda `BaseModelEscopado`, onde o
        campo é obrigatório — exigir escola deixaria justamente o
        caminho de recuperação de conta sem rastro.
        """
        registrar([UMA], origem=Mensagem.Origem.SENHA, escola_id=None)
        self.assertIsNone(Mensagem.objects.get().escola_id)


class DespachoTests(TestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        cls.escola = Escola.objects.create(nome="Escola A")

    def _uma_pendente(self, **kwargs) -> Mensagem:
        return registrar(
            [UMA],
            origem=kwargs.pop("origem", Mensagem.Origem.OCORRENCIA),
            escola_id=self.escola.pk,
            **kwargs,
        )[0]

    def test_sucesso_carimba_enviado(self):
        linha = self._uma_pendente()
        self.assertEqual(despachar([linha.pk]), 1)

        linha.refresh_from_db()
        self.assertEqual(linha.status, Mensagem.Status.ENVIADO)
        self.assertEqual(linha.tentativas, 1)
        self.assertIsNotNone(linha.enviado_em)
        self.assertEqual(linha.erro, "")
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["mae@example.com"])

    def test_falha_carimba_o_erro_do_provedor(self):
        linha = self._uma_pendente()
        with mock.patch.object(
            EmailMultiAlternatives,
            "send",
            side_effect=ConnectionError("cota estourada"),
        ):
            self.assertEqual(despachar([linha.pk]), 0)

        linha.refresh_from_db()
        self.assertEqual(linha.status, Mensagem.Status.FALHOU)
        self.assertEqual(linha.tentativas, 1)
        # É este texto que distingue "endereço inválido" de "cota
        # estourada" — sem ele a secretaria não sabe se adianta retentar.
        self.assertIn("cota estourada", linha.erro)

    def test_nao_reenvia_o_que_ja_saiu(self):
        """Releitura do banco é o que impede o envio duplicado.

        O command de retentativa e a thread podem alcançar a mesma linha;
        quem já está `enviado` fica de fora do queryset.
        """
        linha = self._uma_pendente()
        despachar([linha.pk])
        self.assertEqual(despachar([linha.pk]), 0)
        self.assertEqual(len(mail.outbox), 1)

    def test_uma_falha_nao_cala_as_outras(self):
        linhas = registrar(
            [
                ("A", "t", "<p>h</p>", "ruim@example.com"),
                ("B", "t", "<p>h</p>", "bom@example.com"),
            ],
            origem=Mensagem.Origem.OCORRENCIA,
            escola_id=self.escola.pk,
        )
        original = EmailMultiAlternatives.send

        def send_falhando(self, *args, **kwargs):
            if self.to == ["ruim@example.com"]:
                raise ConnectionError("endereço recusado")
            return original(self, *args, **kwargs)

        with mock.patch.object(EmailMultiAlternatives, "send", send_falhando):
            self.assertEqual(despachar([l.pk for l in linhas]), 1)

        self.assertEqual([m.to for m in mail.outbox], [["bom@example.com"]])

    def test_propagar_levanta_a_excecao_original(self):
        """O caminho all-or-nothing precisa do erro de verdade.

        O `emitir_link` do portal apaga o convite quando o envio falha, e
        quem chama distingue o tipo da exceção — uma genérica cegaria o
        Sentry.
        """
        linha = self._uma_pendente(origem=Mensagem.Origem.CONVITE_PORTAL)
        with mock.patch.object(
            EmailMultiAlternatives,
            "send",
            side_effect=ConnectionError("provedor fora"),
        ):
            with self.assertRaises(ConnectionError):
                despachar([linha.pk], propagar=True)

        # Mesmo propagando, a linha fica carimbada: é o rastro.
        linha.refresh_from_db()
        self.assertEqual(linha.status, Mensagem.Status.FALHOU)
        self.assertIn("provedor fora", linha.erro)


class EnvioCompletoTests(TestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        cls.escola = Escola.objects.create(nome="Escola A")

    def test_enviar_grava_e_despacha(self):
        self.assertEqual(
            enviar(
                [UMA],
                origem=Mensagem.Origem.OCORRENCIA,
                escola_id=self.escola.pk,
                referencia_id=7,
            ),
            1,
        )
        linha = Mensagem.objects.get()
        self.assertEqual(linha.status, Mensagem.Status.ENVIADO)
        self.assertEqual(linha.referencia_id, 7)

    def test_lista_vazia_nao_grava_nada(self):
        self.assertEqual(
            enviar([], origem=Mensagem.Origem.OCORRENCIA, escola_id=self.escola.pk),
            0,
        )
        self.assertFalse(Mensagem.objects.exists())


class OrigensRetentaveisTests(TestCase):
    def test_so_avisos_sao_retentaveis(self):
        """Link com token fica de fora, e o motivo é o prazo dele.

        Convite reenviado carrega token já apagado pelo `emitir_link`;
        link de senha reenviado depois de uma hora chega morto. Os dois
        continuam **gravados** — o rastro vale mesmo sem o reenvio.
        """
        self.assertIn(Mensagem.Origem.OCORRENCIA, ORIGENS_RETENTAVEIS)
        self.assertIn(Mensagem.Origem.PAGAMENTO, ORIGENS_RETENTAVEIS)
        self.assertNotIn(Mensagem.Origem.CONVITE_PORTAL, ORIGENS_RETENTAVEIS)
        self.assertNotIn(Mensagem.Origem.SENHA, ORIGENS_RETENTAVEIS)
