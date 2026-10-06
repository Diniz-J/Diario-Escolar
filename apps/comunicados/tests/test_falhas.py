"""Testes dos caminhos de falha do disparo.

Cenário real que motiva este arquivo: o free tier do Brevo entrega 300
emails/dia. Uma escola média estoura essa cota num único comunicado, e o
provedor passa a recusar. O sistema tem que registrar isso com o motivo
real — um "enviado" mentiroso faria a secretaria garantir aos pais uma
mensagem que nunca chegou.
"""
from datetime import timedelta
from io import StringIO
from unittest.mock import patch

from django.core import mail
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.accounts.models import Usuario
from apps.comunicados.models import Comunicado, ComunicadoDestinatario
from apps.comunicados.services import _disparar, enviar_comunicado
from apps.escola.models import Aluno, Escola, Turma


class _ComunicadoFalhaSetup(TestCase):
    """Setup e helpers compartilhados — sem testes próprios.

    Separado de propósito: herdar de uma classe que TEM testes faz as
    subclasses re-executarem esses testes com a configuração delas, e
    `ComunicadoCaminhoAssincronoTests` (que roda com `TESTING=False`)
    quebraria os testes síncronos herdados.
    """

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


class ComunicadoFalhaTests(_ComunicadoFalhaSetup):
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


class ComunicadoBecoSemSaidaTests(_ComunicadoFalhaSetup):
    """Regressão: nenhuma falha pode deixar o comunicado irrecuperável.

    `enviando` não é editável nem reenviável pela API (o `enviar` devolve
    409 por não estar em rascunho). Um comunicado que entra nesse estado e
    não sai só se resolvia com UPDATE manual no banco — e os responsáveis
    que faltavam nunca receberiam a mensagem.
    """

    def test_falha_ao_materializar_volta_pro_rascunho(self):
        self._aluno("Ana", "ana@example.com")
        comunicado = self._comunicado()

        with patch(
            "apps.comunicados.services._materializar_destinatarios",
            side_effect=Exception("db caiu"),
        ):
            with self.assertRaises(Exception):
                enviar_comunicado(comunicado, usuario=self.diretor)

        comunicado.refresh_from_db()
        # Nada foi enviado, então o rascunho é o estado correto.
        self.assertEqual(comunicado.status, Comunicado.Status.RASCUNHO)
        self.assertTrue(comunicado.editavel)
        self.assertIsNone(comunicado.enviado_por)
        self.assertEqual(len(mail.outbox), 0)
        # E o diretor consegue simplesmente tentar de novo.
        self.assertTrue(enviar_comunicado(comunicado, usuario=self.diretor))
        self.assertEqual(len(mail.outbox), 1)

    def test_reversao_limpa_linhas_parcialmente_criadas(self):
        """Sem ATOMIC_REQUESTS, um bulk_create pode commitar parte dos lotes.

        A próxima tentativa tem que partir do zero, senão `total_destinatarios`
        contaria linhas órfãs da tentativa que falhou.
        """
        aluno = self._aluno("Ana", "ana@example.com")
        comunicado = self._comunicado()

        def materializa_e_falha(com):
            ComunicadoDestinatario.objects.create(
                comunicado=com,
                aluno=aluno,
                email="ana@example.com",
                status=ComunicadoDestinatario.Status.PENDENTE,
            )
            raise Exception("falhou depois de inserir")

        with patch(
            "apps.comunicados.services._materializar_destinatarios",
            side_effect=materializa_e_falha,
        ):
            with self.assertRaises(Exception):
                enviar_comunicado(comunicado, usuario=self.diretor)

        self.assertEqual(comunicado.destinatarios.count(), 0)


class ComunicadoRetomadaTests(_ComunicadoFalhaSetup):
    """O lote interrompido (deploy/restart) tem que ser retomável."""

    def _simular_processo_morto(self, comunicado):
        """Deixa o comunicado como um processo morto no meio do lote deixaria.

        Materializa o público e marca só parte como enviada, mantendo o
        comunicado em `enviando` — exatamente o rastro de uma thread
        daemon que morreu junto com o container.
        """
        from apps.comunicados.services import _materializar_destinatarios

        Comunicado.objects.filter(pk=comunicado.pk).update(
            status=Comunicado.Status.ENVIANDO
        )
        comunicado.refresh_from_db()
        _materializar_destinatarios(comunicado)
        primeira = comunicado.destinatarios.first()
        comunicado.destinatarios.filter(pk=primeira.pk).update(
            status=ComunicadoDestinatario.Status.ENVIADO
        )
        return primeira

    def test_comando_retoma_apenas_os_pendentes(self):
        """Quem já recebeu NÃO recebe de novo."""
        self._aluno("Ja recebeu", "ja@example.com")
        self._aluno("Faltou", "faltou@example.com")
        comunicado = self._comunicado()
        ja_enviada = self._simular_processo_morto(comunicado)

        call_command(
            "comunicados_retomar", "--id", str(comunicado.pk), stdout=StringIO()
        )

        # Só o pendente recebeu email.
        self.assertEqual(len(mail.outbox), 1)
        destinatarios = [m.to[0] for m in mail.outbox]
        self.assertNotIn(ja_enviada.email, destinatarios)

        comunicado.refresh_from_db()
        self.assertEqual(comunicado.status, Comunicado.Status.ENVIADO)
        self.assertEqual(comunicado.total_enviados, 2)
        self.assertEqual(
            comunicado.destinatarios.filter(
                status=ComunicadoDestinatario.Status.PENDENTE
            ).count(),
            0,
        )

    def test_comando_ignora_lote_com_progresso_recente(self):
        """Lote grande em curso não pode ser retomado em paralelo.

        O heartbeat de `_disparar` mantém `atualizado_em` fresco; o comando
        só pega quem está em silêncio há mais que o limite.
        """
        self._aluno("Ana", "ana@example.com")
        comunicado = self._comunicado()
        self._simular_processo_morto(comunicado)
        # `atualizado_em` acabou de ser tocado → progresso recente.
        Comunicado.objects.filter(pk=comunicado.pk).update(
            atualizado_em=timezone.now()
        )

        call_command(
            "comunicados_retomar", "--minutos", "15", stdout=StringIO()
        )

        self.assertEqual(len(mail.outbox), 0, "não devia tocar num lote vivo")
        comunicado.refresh_from_db()
        self.assertEqual(comunicado.status, Comunicado.Status.ENVIANDO)

    def test_comando_pega_lote_em_silencio(self):
        self._aluno("Ana", "ana@example.com")
        comunicado = self._comunicado()
        self._simular_processo_morto(comunicado)
        Comunicado.objects.filter(pk=comunicado.pk).update(
            atualizado_em=timezone.now() - timedelta(minutes=30)
        )

        call_command(
            "comunicados_retomar", "--minutos", "15", stdout=StringIO()
        )

        comunicado.refresh_from_db()
        self.assertEqual(comunicado.status, Comunicado.Status.ENVIADO)

    def test_dry_run_nao_envia_nem_muda_status(self):
        self._aluno("Ana", "ana@example.com")
        comunicado = self._comunicado()
        self._simular_processo_morto(comunicado)
        Comunicado.objects.filter(pk=comunicado.pk).update(
            atualizado_em=timezone.now() - timedelta(minutes=30)
        )

        call_command("comunicados_retomar", "--dry-run", stdout=StringIO())

        self.assertEqual(len(mail.outbox), 0)
        comunicado.refresh_from_db()
        self.assertEqual(comunicado.status, Comunicado.Status.ENVIANDO)

    def test_comando_nao_toca_em_rascunho_nem_enviado(self):
        """Só `enviando` é candidato — nunca disparar um rascunho por acidente."""
        self._aluno("Ana", "ana@example.com")
        rascunho = self._comunicado()
        enviado = self._comunicado()
        Comunicado.objects.filter(pk=enviado.pk).update(
            status=Comunicado.Status.ENVIADO,
            atualizado_em=timezone.now() - timedelta(days=1),
        )
        Comunicado.objects.filter(pk=rascunho.pk).update(
            atualizado_em=timezone.now() - timedelta(days=1)
        )

        call_command("comunicados_retomar", stdout=StringIO())

        self.assertEqual(len(mail.outbox), 0)
        rascunho.refresh_from_db()
        self.assertEqual(rascunho.status, Comunicado.Status.RASCUNHO)


@override_settings(TESTING=False)
class ComunicadoCaminhoAssincronoTests(_ComunicadoFalhaSetup):
    """Cobre o caminho que roda em PRODUÇÃO.

    Todos os outros testes rodam com `settings.TESTING=True`, que força o
    envio síncrono — ou seja, o status `enviando`, o `transaction.on_commit`
    e a thread daemon não eram exercitados em lugar nenhum. O que a suíte
    cobria não era o que roda no servidor.
    """

    def test_thread_so_e_disparada_apos_o_commit(self):
        """Antes do commit a thread não pode existir.

        Ela lê o comunicado e os destinatários do banco; disparada antes do
        commit, poderia não encontrar as linhas que a request acabou de
        criar.
        """
        self._aluno("Ana", "ana@example.com")
        comunicado = self._comunicado()

        with patch("apps.comunicados.services.threading.Thread") as mock_thread:
            with self.captureOnCommitCallbacks(execute=False) as callbacks:
                self.assertTrue(
                    enviar_comunicado(comunicado, usuario=self.diretor)
                )
                mock_thread.assert_not_called()

            self.assertEqual(len(callbacks), 1)
            for cb in callbacks:
                cb()

            mock_thread.assert_called_once()
            # Daemon: não pode segurar o shutdown do processo.
            self.assertTrue(mock_thread.call_args.kwargs["daemon"])
            mock_thread.return_value.start.assert_called_once()

    def test_resposta_imediata_mostra_enviando_com_publico_ja_contado(self):
        """É o payload do 202 que o frontend recebe em produção.

        O lote ainda não rodou, então `total_enviados` é 0 — e é por isso
        que a tela precisa continuar buscando até sair de `enviando`.
        """
        self._aluno("Ana", "ana@example.com")
        self._aluno("Bruno", "bruno@example.com")
        comunicado = self._comunicado()

        with patch("apps.comunicados.services.threading.Thread"):
            with self.captureOnCommitCallbacks(execute=False):
                enviar_comunicado(comunicado, usuario=self.diretor)

        comunicado.refresh_from_db()
        self.assertEqual(comunicado.status, Comunicado.Status.ENVIANDO)
        self.assertEqual(comunicado.total_destinatarios, 2)
        self.assertEqual(comunicado.total_enviados, 0)
        self.assertFalse(comunicado.editavel)
        self.assertEqual(len(mail.outbox), 0)


class ComunicadoClaimPorGrupoTests(_ComunicadoFalhaSetup):
    """O claim por grupo é a garantia real contra duplo envio em massa.

    `_disparar` monta os grupos uma vez em memória e depois itera. Sem
    lock, a thread original e o `comunicados_retomar` podem iterar
    conjuntos sobrepostos — e o resultado seria exatamente o duplo envio
    que a feature inteira existe pra evitar. O heartbeat tornava isso
    improvável; o claim torna impossível.
    """

    def _preparar_lote(self):
        """Deixa o comunicado em `enviando` com o público materializado."""
        from apps.comunicados.services import _materializar_destinatarios

        comunicado = self._comunicado()
        Comunicado.objects.filter(pk=comunicado.pk).update(
            status=Comunicado.Status.ENVIANDO
        )
        comunicado.refresh_from_db()
        _materializar_destinatarios(comunicado)
        return comunicado

    def test_dois_executores_simultaneos_nao_duplicam_email(self):
        """Simula a thread original e a retomada rodando ao mesmo tempo.

        O segundo `_disparar` roda de dentro do primeiro (no meio do
        envio), que é o pior caso: ambos já têm o snapshot dos grupos em
        memória.
        """
        self._aluno("Ana", "ana@example.com")
        self._aluno("Bruno", "bruno@example.com")
        comunicado = self._preparar_lote()

        original = mail.EmailMultiAlternatives.send
        reentrou = []

        def send_reentrante(self_msg, *args, **kwargs):
            resultado = original(self_msg, *args, **kwargs)
            # No primeiro envio, dispara um executor concorrente.
            if not reentrou:
                reentrou.append(True)
                _disparar(comunicado.pk, comunicado.escola_id)
            return resultado

        with patch.object(
            mail.EmailMultiAlternatives, "send", send_reentrante
        ):
            _disparar(comunicado.pk, comunicado.escola_id)

        self.assertTrue(reentrou, "o executor concorrente não rodou")
        # Dois responsáveis, dois emails — nunca quatro.
        destinos = sorted(m.to[0] for m in mail.outbox)
        self.assertEqual(destinos, ["ana@example.com", "bruno@example.com"])
        self.assertEqual(len(mail.outbox), 2)

        comunicado.refresh_from_db()
        self.assertEqual(comunicado.total_enviados, 2)
        self.assertEqual(comunicado.total_falhas, 0)

    def test_grupo_ja_reivindicado_e_pulado(self):
        """Linha fora de `pendente` não é reenviada."""
        self._aluno("Ana", "ana@example.com")
        comunicado = self._preparar_lote()
        # Outro executor reivindicou e ainda não confirmou.
        comunicado.destinatarios.update(
            status=ComunicadoDestinatario.Status.ENVIANDO
        )

        _disparar(comunicado.pk, comunicado.escola_id)

        self.assertEqual(len(mail.outbox), 0)

    def test_linha_indeterminada_nao_e_reenviada_nem_vira_falha(self):
        """Processo morto entre o claim e a confirmação.

        Não sabemos se o email saiu. Para comunicado em massa, duplicar é
        pior que faltar — então a linha fica visível como não confirmada e
        nenhuma retomada a reenvia.
        """
        self._aluno("Ana", "ana@example.com")
        self._aluno("Bruno", "bruno@example.com")
        comunicado = self._preparar_lote()

        ana = comunicado.destinatarios.get(aluno__nome_completo="Ana")
        comunicado.destinatarios.filter(pk=ana.pk).update(
            status=ComunicadoDestinatario.Status.ENVIANDO
        )

        call_command(
            "comunicados_retomar", "--id", str(comunicado.pk), stdout=StringIO()
        )

        # Só o Bruno (que estava `pendente`) recebeu.
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["bruno@example.com"])

        ana.refresh_from_db()
        self.assertEqual(ana.status, ComunicadoDestinatario.Status.ENVIANDO)

    def test_lote_todo_indeterminado_nao_e_marcado_como_falha(self):
        """`falhou` significa 'não entregou nada' — aqui pode ter entregado."""
        self._aluno("Ana", "ana@example.com")
        comunicado = self._preparar_lote()
        comunicado.destinatarios.update(
            status=ComunicadoDestinatario.Status.ENVIANDO
        )

        _disparar(comunicado.pk, comunicado.escola_id)

        comunicado.refresh_from_db()
        self.assertEqual(comunicado.total_enviados, 0)
        self.assertNotEqual(
            comunicado.status,
            Comunicado.Status.FALHOU,
            "lote indeterminado não pode ser reportado como falha total",
        )

    def test_claim_parcial_devolve_as_linhas_e_pula(self):
        """Guarda de invariante: grupo reivindicado só em parte não é enviado."""
        from apps.comunicados.services import _reivindicar

        self._aluno("Irmão 1", "familia@example.com")
        self._aluno("Irmão 2", "familia@example.com")
        comunicado = self._preparar_lote()

        linhas = list(comunicado.destinatarios.values_list("id", flat=True))
        # Uma das duas já foi levada por outro executor.
        ComunicadoDestinatario.objects.filter(id=linhas[0]).update(
            status=ComunicadoDestinatario.Status.ENVIADO
        )

        self.assertFalse(
            _reivindicar(linhas, "familia@example.com", comunicado.pk)
        )
        # A que foi pega no claim parcial volta pra `pendente`.
        devolvida = ComunicadoDestinatario.objects.get(id=linhas[1])
        self.assertEqual(
            devolvida.status, ComunicadoDestinatario.Status.PENDENTE
        )
