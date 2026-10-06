"""Testes do disparo de comunicados — o núcleo de risco da feature.

Em testes o EMAIL_BACKEND é o locmem (`settings.TESTING`) e o envio roda
síncrono (ver `services.enviar_comunicado`), então `mail.outbox` reflete
exatamente o lote.
"""
from django.core import mail
from django.test import TestCase

from apps.accounts.models import Usuario
from apps.comunicados.models import Comunicado, ComunicadoDestinatario
from apps.comunicados.services import contar_previa, enviar_comunicado
from apps.escola.models import Aluno, Escola, Turma


class ComunicadoEnvioTests(TestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        cls.escola = Escola.objects.create(nome="Escola Teste")
        cls.outra_escola = Escola.objects.create(nome="Outra Escola")
        cls.turma_a = Turma.objects.create(
            escola=cls.escola,
            nome="1º A",
            turno=Turma.Turno.MATUTINO,
            ano_letivo=2026,
        )
        cls.turma_b = Turma.objects.create(
            escola=cls.escola,
            nome="2º B",
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

    def _aluno(self, nome, turma, email="", responsavel="", ativo=True, escola=None):
        return Aluno.objects.create(
            escola=escola or self.escola,
            matricula=f"M{Aluno.objects.count() + 1}",
            nome_completo=nome,
            turma=turma,
            ativo=ativo,
            nome_responsavel=responsavel,
            email_responsavel=email,
        )

    def _comunicado(self, destino=Comunicado.Destino.ESCOLA, turmas=()):
        c = Comunicado.objects.create(
            escola=self.escola,
            titulo="Reunião de pais",
            mensagem="Será dia 20/10 às 19h no auditório.",
            destino=destino,
            criado_por=self.diretor,
        )
        if turmas:
            c.turmas.set(turmas)
        return c

    # ------------------------------------------------------------------
    # Privacidade e deduplicação — os dois requisitos mais sensíveis.
    # ------------------------------------------------------------------

    def test_cada_responsavel_recebe_email_individual(self):
        """Nenhuma mensagem pode conter mais de um destinatário.

        Regressão de privacidade (LGPD): um To/CC coletivo vazaria a lista
        de emails de todos os pais da escola pra todos os pais da escola.
        """
        self._aluno("Ana", self.turma_a, "ana.mae@example.com", "Mãe da Ana")
        self._aluno("Bruno", self.turma_a, "bruno.pai@example.com", "Pai do Bruno")
        self._aluno("Carla", self.turma_b, "carla.mae@example.com", "Mãe da Carla")

        enviar_comunicado(self._comunicado(), usuario=self.diretor)

        self.assertEqual(len(mail.outbox), 3)
        for msg in mail.outbox:
            self.assertEqual(len(msg.to), 1, "email com mais de um destinatário")
            self.assertEqual(msg.cc, [])
            self.assertEqual(msg.bcc, [])

    def test_irmaos_com_mesmo_responsavel_geram_um_unico_email(self):
        """Dedup por endereço: pai de dois filhos recebe uma mensagem.

        As duas linhas de log continuam existindo (uma por aluno) e ambas
        ficam `enviado` — é o que permite consultar por aluno.
        """
        self._aluno("Irmão 1", self.turma_a, "familia@example.com", "Pai")
        self._aluno("Irmão 2", self.turma_b, "familia@example.com", "Pai")

        comunicado = self._comunicado()
        enviar_comunicado(comunicado, usuario=self.diretor)

        self.assertEqual(len(mail.outbox), 1)
        comunicado.refresh_from_db()
        self.assertEqual(comunicado.total_destinatarios, 2)
        self.assertEqual(comunicado.total_enviados, 2)
        self.assertEqual(
            comunicado.destinatarios.filter(
                status=ComunicadoDestinatario.Status.ENVIADO
            ).count(),
            2,
        )

    def test_dedup_normaliza_caixa_e_espaco(self):
        """`Familia@Example.com ` e `familia@example.com` são o mesmo pai."""
        self._aluno("Irmão 1", self.turma_a, "Familia@Example.com ", "Pai")
        self._aluno("Irmão 2", self.turma_b, "familia@example.com", "Pai")

        enviar_comunicado(self._comunicado(), usuario=self.diretor)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["familia@example.com"])

    # ------------------------------------------------------------------
    # Resolução de público
    # ------------------------------------------------------------------

    def test_destino_turmas_atinge_so_as_turmas_escolhidas(self):
        self._aluno("Da turma A", self.turma_a, "a@example.com")
        self._aluno("Da turma B", self.turma_b, "b@example.com")

        comunicado = self._comunicado(
            destino=Comunicado.Destino.TURMAS, turmas=[self.turma_a]
        )
        enviar_comunicado(comunicado, usuario=self.diretor)

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["a@example.com"])

    def test_aluno_inativo_nao_recebe(self):
        """Aluno transferido/desmatriculado não recebe aviso da escola."""
        self._aluno("Ativo", self.turma_a, "ativo@example.com")
        self._aluno("Inativo", self.turma_a, "inativo@example.com", ativo=False)

        enviar_comunicado(self._comunicado(), usuario=self.diretor)

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["ativo@example.com"])

    def test_aluno_de_outra_escola_nao_recebe(self):
        """Rede de segurança contra vazamento entre escolas."""
        turma_outra = Turma.objects.create(
            escola=self.outra_escola,
            nome="1º A",
            turno=Turma.Turno.MATUTINO,
            ano_letivo=2026,
        )
        self._aluno("Da minha escola", self.turma_a, "meu@example.com")
        self._aluno(
            "De outra escola",
            turma_outra,
            "outro@example.com",
            escola=self.outra_escola,
        )

        enviar_comunicado(self._comunicado(), usuario=self.diretor)

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["meu@example.com"])

    def test_aluno_sem_email_fica_registrado_como_sem_email(self):
        """Cadastro incompleto tem que ficar visível, não sumir calado."""
        self._aluno("Com email", self.turma_a, "tem@example.com")
        sem = self._aluno("Sem email", self.turma_a, "")

        comunicado = self._comunicado()
        enviar_comunicado(comunicado, usuario=self.diretor)

        self.assertEqual(len(mail.outbox), 1)
        comunicado.refresh_from_db()
        self.assertEqual(comunicado.total_sem_email, 1)
        self.assertEqual(comunicado.total_enviados, 1)
        linha = comunicado.destinatarios.get(aluno=sem)
        self.assertEqual(linha.status, ComunicadoDestinatario.Status.SEM_EMAIL)
        self.assertIsNone(linha.enviado_em)

    # ------------------------------------------------------------------
    # Conteúdo da mensagem
    # ------------------------------------------------------------------

    def test_email_tem_titulo_mensagem_e_alternativa_html(self):
        self._aluno("Ana", self.turma_a, "mae@example.com", "Maria Silva")
        enviar_comunicado(self._comunicado(), usuario=self.diretor)

        msg = mail.outbox[0]
        self.assertIn("Reunião de pais", msg.subject)
        self.assertIn("Maria Silva", msg.body)
        self.assertIn("auditório", msg.body)
        # Fallback em texto + alternativa HTML (multipart).
        self.assertEqual(len(msg.alternatives), 1)
        html, mimetype = msg.alternatives[0]
        self.assertEqual(mimetype, "text/html")
        self.assertIn("Reunião de pais", html)
        self.assertIn("auditório", html)
        # Regressão: `{# #}` multilinha não é comentário no Django e
        # vazaria como texto visível no corpo do email.
        self.assertNotIn("{% comment %}", html)
        self.assertNotIn("Estilos inline", html)

    def test_saudacao_generica_quando_responsavel_sem_nome(self):
        self._aluno("Ana", self.turma_a, "mae@example.com", "")
        enviar_comunicado(self._comunicado(), usuario=self.diretor)
        self.assertIn("Prezado(a) responsável", mail.outbox[0].body)

    def test_mensagem_com_html_e_escapada_no_corpo_html(self):
        """`linebreaksbr` escapa antes de converter \\n — sem injeção de HTML."""
        self._aluno("Ana", self.turma_a, "mae@example.com", "Maria")
        comunicado = self._comunicado()
        comunicado.mensagem = "Atenção <script>alert(1)</script>\nSegunda linha"
        comunicado.save()

        enviar_comunicado(comunicado, usuario=self.diretor)

        html = mail.outbox[0].alternatives[0][0]
        self.assertNotIn("<script>", html)
        self.assertIn("&lt;script&gt;", html)
        # A quebra de linha digitada virou <br>.
        self.assertIn("<br>", html)

    # ------------------------------------------------------------------
    # Estado e idempotência
    # ------------------------------------------------------------------

    def test_envio_marca_status_contadores_e_autoria(self):
        self._aluno("Ana", self.turma_a, "a@example.com")
        self._aluno("Bruno", self.turma_a, "b@example.com")

        comunicado = self._comunicado()
        self.assertTrue(enviar_comunicado(comunicado, usuario=self.diretor))

        comunicado.refresh_from_db()
        self.assertEqual(comunicado.status, Comunicado.Status.ENVIADO)
        self.assertEqual(comunicado.total_destinatarios, 2)
        self.assertEqual(comunicado.total_enviados, 2)
        self.assertEqual(comunicado.total_falhas, 0)
        self.assertIsNotNone(comunicado.enviado_em)
        self.assertEqual(comunicado.enviado_por, self.diretor)
        self.assertFalse(comunicado.editavel)

    def test_segundo_envio_nao_reenvia(self):
        """Trava anti-duplo-clique: email duplicado não tem desfazer."""
        self._aluno("Ana", self.turma_a, "a@example.com")
        comunicado = self._comunicado()

        self.assertTrue(enviar_comunicado(comunicado, usuario=self.diretor))
        self.assertEqual(len(mail.outbox), 1)

        self.assertFalse(enviar_comunicado(comunicado, usuario=self.diretor))
        self.assertEqual(len(mail.outbox), 1)

    def test_comunicado_sem_publico_fica_enviado_sem_mensagens(self):
        """Escola sem aluno ativo: conclui como enviado, não como falha.

        Não houve erro — simplesmente não havia ninguém pra receber. Marcar
        `falhou` aqui faria o diretor caçar um problema que não existe.
        """
        comunicado = self._comunicado()
        self.assertTrue(enviar_comunicado(comunicado, usuario=self.diretor))

        comunicado.refresh_from_db()
        self.assertEqual(len(mail.outbox), 0)
        self.assertEqual(comunicado.status, Comunicado.Status.ENVIADO)
        self.assertEqual(comunicado.total_destinatarios, 0)

    def test_todos_sem_email_nao_e_falha(self):
        """Ninguém com email ≠ provedor com erro."""
        self._aluno("Sem email", self.turma_a, "")
        comunicado = self._comunicado()
        enviar_comunicado(comunicado, usuario=self.diretor)

        comunicado.refresh_from_db()
        self.assertEqual(comunicado.status, Comunicado.Status.ENVIADO)
        self.assertEqual(comunicado.total_sem_email, 1)

    # ------------------------------------------------------------------
    # Prévia
    # ------------------------------------------------------------------

    def test_previa_conta_sem_enviar_e_deduplica(self):
        self._aluno("Irmão 1", self.turma_a, "familia@example.com")
        self._aluno("Irmão 2", self.turma_a, "familia@example.com")
        self._aluno("Sozinho", self.turma_b, "outro@example.com")
        self._aluno("Sem email", self.turma_b, "")

        previa = contar_previa(self._comunicado())

        self.assertEqual(previa["total_alunos"], 4)
        # 2 endereços únicos (familia + outro); o sem email não conta.
        self.assertEqual(previa["total_emails"], 2)
        self.assertEqual(previa["total_sem_email"], 1)
        self.assertEqual(len(mail.outbox), 0, "prévia não pode enviar nada")
