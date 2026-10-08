"""Testes do disparo de comunicados — o núcleo de risco da feature.

Em testes o EMAIL_BACKEND é o locmem (`settings.TESTING`) e o envio roda
síncrono (ver `services.enviar_comunicado`), então `mail.outbox` reflete
exatamente o lote.
"""
from smtplib import SMTPException
from unittest.mock import patch

from django.core import mail
from django.core.mail import EmailMultiAlternatives
from django.db import IntegrityError, transaction
from django.test import TestCase

from apps.accounts.models import Usuario
from apps.comunicados.models import Comunicado, ComunicadoDestinatario
from apps.comunicados.services import (
    _materializar_destinatarios,
    contar_previa,
    enviar_comunicado,
)
from apps.escola.models import Aluno, Escola, Turma
from apps.portal.models import Responsavel, ResponsavelAluno


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


class ComunicadoMultiplosResponsaveisTests(ComunicadoEnvioTests):
    """Log por responsável — `RESPONSAVEIS.md` fatia 3.

    Herda as fixtures de `ComunicadoEnvioTests`; os testes do pai rodam de
    novo aqui, o que é barato e não incomoda.
    """

    def _responsavel(self, nome, email, aluno, **kwargs):
        responsavel = Responsavel.objects.create(
            escola=self.escola, nome=nome, email=email, **kwargs
        )
        ResponsavelAluno.objects.create(responsavel=responsavel, aluno=aluno)
        return responsavel

    def test_dois_responsaveis_geram_duas_linhas_e_dois_emails(self):
        aluno = self._aluno("Davi", self.turma_a, "antigo@example.com", "Antigo")
        mae = self._responsavel("Marta", "marta@example.com", aluno)
        pai = self._responsavel("Jorge", "jorge@example.com", aluno)

        comunicado = self._comunicado()
        enviar_comunicado(comunicado, usuario=self.diretor)

        self.assertEqual(
            sorted(msg.to[0] for msg in mail.outbox),
            ["jorge@example.com", "marta@example.com"],
        )
        linhas = comunicado.destinatarios.all()
        self.assertEqual(linhas.count(), 2)
        self.assertEqual(
            sorted(linha.responsavel_id for linha in linhas),
            sorted([mae.id, pai.id]),
        )
        # O campo de texto do aluno não entra junto com os vínculos.
        self.assertNotIn("antigo@example.com", [msg.to[0] for msg in mail.outbox])

    def test_falha_de_um_responsavel_nao_contamina_o_outro(self):
        """O ganho da fatia: dois resultados de entrega para o mesmo aluno."""
        aluno = self._aluno("Eva", self.turma_a)
        self._responsavel("Ruim", "ruim@example.com", aluno)
        boa = self._responsavel("Boa", "boa@example.com", aluno)

        original = EmailMultiAlternatives.send

        def send_falhando(self, *args, **kwargs):
            if self.to == ["ruim@example.com"]:
                raise SMTPException("endereço recusado pelo provedor")
            return original(self, *args, **kwargs)

        comunicado = self._comunicado()
        with patch.object(EmailMultiAlternatives, "send", send_falhando):
            enviar_comunicado(comunicado, usuario=self.diretor)

        comunicado.refresh_from_db()
        self.assertEqual(comunicado.total_enviados, 1)
        self.assertEqual(comunicado.total_falhas, 1)
        # Mesmo aluno, resultados independentes.
        por_responsavel = {
            linha.responsavel_id: linha.status
            for linha in comunicado.destinatarios.all()
        }
        self.assertEqual(
            por_responsavel[boa.id], ComunicadoDestinatario.Status.ENVIADO
        )
        self.assertEqual(
            {linha.aluno_id for linha in comunicado.destinatarios.all()},
            {aluno.id},
        )

    def test_aluno_sem_destino_gera_uma_linha_sem_email(self):
        """A unidade do aviso de cadastro incompleto é o aluno."""
        self._aluno("Sem ninguém", self.turma_a)

        comunicado = self._comunicado()
        enviar_comunicado(comunicado, usuario=self.diretor)

        comunicado.refresh_from_db()
        self.assertEqual(len(mail.outbox), 0)
        self.assertEqual(comunicado.total_sem_email, 1)
        linha = comunicado.destinatarios.get()
        self.assertIsNone(linha.responsavel_id)
        self.assertEqual(linha.email, "")

    def test_responsavel_desativado_nao_cai_no_campo_antigo(self):
        """§4.1: vínculo existe, logo sem fallback — e aluno vira sem_email."""
        aluno = self._aluno("Fabio", self.turma_a, "rita@example.com", "Rita")
        self._responsavel("Rita", "rita@example.com", aluno, ativo=False)

        comunicado = self._comunicado()
        enviar_comunicado(comunicado, usuario=self.diretor)

        comunicado.refresh_from_db()
        self.assertEqual(len(mail.outbox), 0)
        self.assertEqual(comunicado.total_sem_email, 1)

    def test_opt_out_nao_recebe_comunicado(self):
        aluno = self._aluno("Gabi", self.turma_a)
        self._responsavel(
            "Recusou", "recusou@example.com", aluno, recebe_notificacao=False
        )
        self._responsavel("Aceita", "aceita@example.com", aluno)

        comunicado = self._comunicado()
        enviar_comunicado(comunicado, usuario=self.diretor)

        self.assertEqual([msg.to[0] for msg in mail.outbox], ["aceita@example.com"])

    def test_previa_bate_com_o_que_sai(self):
        """A prévia alimenta o botão "Enviar N emails": tem que ser honesta.

        Com múltiplos responsáveis `total_emails` passa de `total_alunos`,
        e é `total_emails` que corresponde ao que o provedor recebe.
        """
        com_dois = self._aluno("Hugo", self.turma_a)
        self._responsavel("Mãe do Hugo", "mae.hugo@example.com", com_dois)
        self._responsavel("Pai do Hugo", "pai.hugo@example.com", com_dois)
        # Irmãos pelo mesmo responsável: contam como uma mensagem.
        irmao = self._aluno("Ivo", self.turma_a)
        irma = self._aluno("Iara", self.turma_b)
        compartilhado = Responsavel.objects.create(
            escola=self.escola, nome="Pai dos I", email="pai.i@example.com"
        )
        ResponsavelAluno.objects.create(responsavel=compartilhado, aluno=irmao)
        ResponsavelAluno.objects.create(responsavel=compartilhado, aluno=irma)
        # Sem vínculo: entra pelo campo de texto.
        self._aluno("Joana", self.turma_a, "joana.mae@example.com", "Mãe")
        # Sem nada.
        self._aluno("Lia", self.turma_b)

        comunicado = self._comunicado()
        previa = contar_previa(comunicado)

        self.assertEqual(previa["total_alunos"], 5)
        self.assertEqual(previa["total_emails"], 4)
        self.assertEqual(previa["total_sem_email"], 1)

        enviar_comunicado(comunicado, usuario=self.diretor)

        self.assertEqual(len(mail.outbox), previa["total_emails"])
        comunicado.refresh_from_db()
        self.assertEqual(comunicado.total_sem_email, previa["total_sem_email"])

    def test_materializar_duas_vezes_nao_duplica_linha(self):
        """Idempotência do `ignore_conflicts` nos dois caminhos.

        O do fallback depende de `nulls_distinct=False` no unique: sem
        isso, `(comunicado, aluno, NULL)` passaria duas vezes e o pai
        receberia o comunicado em dobro.
        """
        com_vinculo = self._aluno("Marta", self.turma_a)
        self._responsavel("Resp", "resp@example.com", com_vinculo)
        self._aluno("Nina", self.turma_b, "nina.mae@example.com", "Mãe")
        self._aluno("Otto", self.turma_b)

        comunicado = self._comunicado()
        self.assertEqual(_materializar_destinatarios(comunicado), 3)
        self.assertEqual(_materializar_destinatarios(comunicado), 3)

        self.assertEqual(comunicado.destinatarios.count(), 3)

    def test_previa_nao_cresce_com_o_numero_de_alunos(self):
        """O comunicado alcança a escola toda: N+1 aqui é inaceitável.

        Duas consultas fixas — os alunos e os vínculos do lote. O `.only()`
        de `_alunos_para_envio` precisa trazer os campos do fallback, senão
        o acesso diferido viraria um SELECT por aluno sem vínculo.
        """
        for i in range(10):
            aluno = self._aluno(f"Aluno {i}", self.turma_a, f"a{i}@example.com", "R")
            if i % 2 == 0:
                self._responsavel(f"Resp {i}", f"r{i}@example.com", aluno)

        comunicado = self._comunicado()
        with self.assertNumQueries(2):
            previa = contar_previa(comunicado)

        self.assertEqual(previa["total_alunos"], 10)

    def test_unique_trata_responsavel_nulo_como_valor(self):
        """Prova direta do `nulls_distinct=False`.

        No padrão do Postgres, NULL é distinto de NULL num unique — então
        `(comunicado, aluno, NULL)` passaria duas vezes e o pai da escola
        sem vínculo receberia o comunicado em dobro. É a única garantia
        que o caminho do fallback tem.
        """
        aluno = self._aluno("Quim", self.turma_a, "quim.mae@example.com", "Mãe")
        comunicado = self._comunicado()
        ComunicadoDestinatario.objects.create(
            comunicado=comunicado, aluno=aluno, email="quim.mae@example.com"
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                ComunicadoDestinatario.objects.create(
                    comunicado=comunicado,
                    aluno=aluno,
                    email="quim.mae@example.com",
                )

    def test_linha_antiga_sem_responsavel_continua_respondendo(self):
        """§4.4: o log de comunicado já enviado não perde histórico.

        A migration deixa as linhas antigas com `responsavel=NULL` — elas
        têm que continuar respondendo "o responsável do João recebeu?" pelo
        snapshot de email/nome.
        """
        aluno = self._aluno("Pedro", self.turma_a, "pedro.mae@example.com", "Mãe")
        comunicado = self._comunicado()
        antiga = ComunicadoDestinatario.objects.create(
            comunicado=comunicado,
            aluno=aluno,
            email="pedro.mae@example.com",
            nome_responsavel="Mãe",
            status=ComunicadoDestinatario.Status.ENVIADO,
        )

        encontrada = comunicado.destinatarios.get(aluno=aluno)

        self.assertEqual(encontrada.pk, antiga.pk)
        self.assertIsNone(encontrada.responsavel_id)
        self.assertEqual(encontrada.email, "pedro.mae@example.com")
        self.assertEqual(encontrada.nome_responsavel, "Mãe")
