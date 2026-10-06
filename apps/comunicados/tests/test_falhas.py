"""Testes dos caminhos de falha do disparo.

Cenário real que motiva este arquivo: o free tier do Brevo entrega 300
emails/dia. Uma escola média estoura essa cota num único comunicado, e o
provedor passa a recusar. O sistema tem que registrar isso com o motivo
real — um "enviado" mentiroso faria a secretaria garantir aos pais uma
mensagem que nunca chegou.
"""
from unittest.mock import patch

from django.core import mail
from django.test import TestCase

from apps.accounts.models import Usuario
from apps.comunicados.models import Comunicado, ComunicadoDestinatario
from apps.comunicados.services import enviar_comunicado
from apps.escola.models import Aluno, Escola, Turma


class ComunicadoFalhaTests(TestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        cls.escola = Escola.objects.create(nome="Escola Teste")
        cls.turma = Turma.objects.create(
            escola=cls.escola,
            nome="1º A",
            turno=Turma.Turno.MATUTINO,
            ano_letivo=2026,
        )
        cls.diretor = Usuario.objects.create_user(
            username="dir",
            password="x",
            perfil=Usuario.Perfil.DIRETOR,
            escola=cls.escola,
        )

    def setUp(self) -> None:
        mail.outbox = []

    def _aluno(self, nome, email):
        return Aluno.objects.create(
            escola=self.escola,
            matricula=f"M{Aluno.objects.count() + 1}",
            nome_completo=nome,
            turma=self.turma,
            email_responsavel=email,
        )

    def _comunicado(self):
        return Comunicado.objects.create(
            escola=self.escola,
            titulo="Aviso",
            mensagem="Conteúdo.",
            destino=Comunicado.Destino.ESCOLA,
            criado_por=self.diretor,
        )

    def test_falha_ao_abrir_conexao_marca_todos_com_o_erro(self):
        """Provedor fora / cota estourada: ninguém fica em `pendente`."""
        self._aluno("Ana", "ana@example.com")
        self._aluno("Bruno", "bruno@example.com")
        comunicado = self._comunicado()

        with patch(
            "apps.comunicados.services.get_connection"
        ) as mock_conn:
            mock_conn.return_value.open.side_effect = Exception(
                "daily limit exceeded"
            )
            enviar_comunicado(comunicado, usuario=self.diretor)

        comunicado.refresh_from_db()
        self.assertEqual(comunicado.status, Comunicado.Status.FALHOU)
        self.assertEqual(comunicado.total_enviados, 0)
        self.assertEqual(comunicado.total_falhas, 2)
        self.assertEqual(
            comunicado.destinatarios.filter(
                status=ComunicadoDestinatario.Status.PENDENTE
            ).count(),
            0,
            "nenhuma linha pode ficar pendente após o disparo",
        )
        # O motivo real do provedor tem que ficar registrado.
        for linha in comunicado.destinatarios.all():
            self.assertIn("daily limit exceeded", linha.erro)

    def test_falha_de_um_destinatario_nao_aborta_o_lote(self):
        """Um email inválido não pode impedir os outros 140 de sair."""
        self._aluno("Ana", "ana@example.com")
        self._aluno("Invalido", "invalido@example.com")
        self._aluno("Bruno", "bruno@example.com")
        comunicado = self._comunicado()

        original = mail.EmailMultiAlternatives.send

        def send_falhando(self_msg, *args, **kwargs):
            if self_msg.to == ["invalido@example.com"]:
                raise Exception("recipient rejected")
            return original(self_msg, *args, **kwargs)

        with patch.object(
            mail.EmailMultiAlternatives, "send", send_falhando
        ):
            enviar_comunicado(comunicado, usuario=self.diretor)

        comunicado.refresh_from_db()
        # Os outros dois saíram.
        self.assertEqual(comunicado.total_enviados, 2)
        self.assertEqual(comunicado.total_falhas, 1)
        # Parcial não é `falhou`: houve entrega.
        self.assertEqual(comunicado.status, Comunicado.Status.ENVIADO)

        falha = comunicado.destinatarios.get(
            status=ComunicadoDestinatario.Status.FALHOU
        )
        self.assertEqual(falha.aluno.nome_completo, "Invalido")
        self.assertIn("recipient rejected", falha.erro)
        self.assertIsNone(falha.enviado_em)

    def test_erro_inesperado_tira_o_comunicado_de_enviando(self):
        """A UI não pode ficar presa em `enviando` pra sempre."""
        self._aluno("Ana", "ana@example.com")
        comunicado = self._comunicado()

        with patch(
            "apps.comunicados.services._agrupar_por_email",
            side_effect=Exception("boom"),
        ):
            enviar_comunicado(comunicado, usuario=self.diretor)

        comunicado.refresh_from_db()
        self.assertEqual(comunicado.status, Comunicado.Status.FALHOU)
