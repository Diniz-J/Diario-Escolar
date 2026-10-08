"""Testes da notificação por email ao responsável ao criar ocorrência.

Em testes o EMAIL_BACKEND é o locmem (settings.TESTING), então os emails
ficam em `django.core.mail.outbox` em vez de serem enviados de verdade.
"""
from datetime import date
from smtplib import SMTPException
from unittest.mock import patch

from django.core import mail
from django.core.mail import EmailMultiAlternatives
from django.test import TestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.accounts.models import Usuario
from apps.escola.models import Aluno, Escola, Professor, Turma
from apps.ocorrencias.views import OcorrenciaViewSet
from apps.portal.models import Responsavel, ResponsavelAluno


class OcorrenciaEmailTests(TestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        cls.factory = APIRequestFactory()
        cls.escola = Escola.objects.create(nome="Escola Teste")
        cls.turma = Turma.objects.create(
            escola=cls.escola,
            nome="1º A",
            turno=Turma.Turno.MATUTINO,
            ano_letivo=2026,
        )
        cls.admin = Usuario.objects.create_user(
            username="adm", password="x", perfil=Usuario.Perfil.ADMIN
        )

    def setUp(self) -> None:
        mail.outbox = []

    def _criar_ocorrencia(self, aluno) -> int:
        payload = {
            "escola": self.escola.id,
            "turma": self.turma.id,
            "aluno": aluno.id,
            "descricao": "Conversa excessiva durante a aula.",
            "data_ocorrencia": date.today().isoformat(),
            "status": "aberta",
        }
        req = self.factory.post("/", payload, format="json")
        force_authenticate(req, user=self.admin)
        view = OcorrenciaViewSet.as_view({"post": "create"})
        resp = view(req)
        return resp.status_code

    def test_ocorrencia_envia_email_ao_responsavel(self):
        aluno = Aluno.objects.create(
            escola=self.escola,
            matricula="A1",
            nome_completo="Ana Silva",
            turma=self.turma,
            nome_responsavel="Maria Silva",
            email_responsavel="maria@example.com",
        )
        status_code = self._criar_ocorrencia(aluno)
        self.assertEqual(status_code, 201)
        self.assertEqual(len(mail.outbox), 1)
        email = mail.outbox[0]
        self.assertEqual(email.to, ["maria@example.com"])
        self.assertIn("Ana Silva", email.subject)
        self.assertIn("Conversa excessiva", email.body)
        self.assertIn("1º A", email.body)

    def test_html_do_email_nao_vaza_comentario_do_template(self):
        # Regressão: `{# #}` multilinha não é comentário no Django e
        # aparecia como texto no corpo do email.
        aluno = Aluno.objects.create(
            escola=self.escola,
            matricula="A3",
            nome_completo="Carla Souza",
            turma=self.turma,
            nome_responsavel="Paula Souza",
            email_responsavel="paula@example.com",
        )
        self._criar_ocorrencia(aluno)
        html, _mimetype = mail.outbox[0].alternatives[0]
        self.assertNotIn("{#", html)
        self.assertNotIn("Template HTML do email", html)

    def test_aluno_sem_email_nao_quebra_e_nao_envia(self):
        aluno = Aluno.objects.create(
            escola=self.escola,
            matricula="A2",
            nome_completo="Bruno Costa",
            turma=self.turma,
            # sem nome_responsavel / email_responsavel (aluno antigo)
        )
        status_code = self._criar_ocorrencia(aluno)
        # A ocorrência é criada normalmente...
        self.assertEqual(status_code, 201)
        # ...mas nenhum email é enviado (sem responsável cadastrado).
        self.assertEqual(len(mail.outbox), 0)

    def test_dois_responsaveis_vinculados_recebem_mensagens_individuais(self):
        """Mãe e pai cadastrados: dois emails, cada um saudado pelo nome.

        Individuais de propósito — endereço de um responsável não é dado
        do outro, então nada de dois no mesmo `to`.
        """
        aluno = Aluno.objects.create(
            escola=self.escola,
            matricula="A4",
            nome_completo="Davi Lima",
            turma=self.turma,
            nome_responsavel="Cadastro Antigo",
            email_responsavel="antigo@example.com",
        )
        mae = Responsavel.objects.create(
            escola=self.escola, nome="Marta Lima", email="marta@example.com"
        )
        pai = Responsavel.objects.create(
            escola=self.escola, nome="Jorge Lima", email="jorge@example.com"
        )
        ResponsavelAluno.objects.create(responsavel=mae, aluno=aluno)
        ResponsavelAluno.objects.create(responsavel=pai, aluno=aluno)

        self.assertEqual(self._criar_ocorrencia(aluno), 201)

        self.assertEqual(len(mail.outbox), 2)
        for email in mail.outbox:
            self.assertEqual(len(email.to), 1)
        por_destino = {email.to[0]: email for email in mail.outbox}
        self.assertEqual(
            sorted(por_destino), ["jorge@example.com", "marta@example.com"]
        )
        self.assertIn("Marta Lima", por_destino["marta@example.com"].body)
        self.assertIn("Jorge Lima", por_destino["jorge@example.com"].body)
        # O campo de texto do aluno não entra junto com os vínculos.
        self.assertNotIn("antigo@example.com", por_destino)

    def test_responsavel_desativado_silencia_sem_cair_no_campo_antigo(self):
        """§4.1 do RESPONSAVEIS.md: vínculo existe, logo não há fallback.

        Cair no campo do aluno aqui mandaria email pro mesmo endereço que
        a escola acabou de desativar.
        """
        aluno = Aluno.objects.create(
            escola=self.escola,
            matricula="A5",
            nome_completo="Eva Rocha",
            turma=self.turma,
            nome_responsavel="Rita Rocha",
            email_responsavel="rita@example.com",
        )
        desligada = Responsavel.objects.create(
            escola=self.escola,
            nome="Rita Rocha",
            email="rita@example.com",
            ativo=False,
        )
        ResponsavelAluno.objects.create(responsavel=desligada, aluno=aluno)

        self.assertEqual(self._criar_ocorrencia(aluno), 201)

        self.assertEqual(len(mail.outbox), 0)

    def test_falha_em_um_destinatario_nao_impede_o_outro(self):
        """Email inválido da mãe não pode calar o do pai."""
        aluno = Aluno.objects.create(
            escola=self.escola,
            matricula="A6",
            nome_completo="Felipe Dias",
            turma=self.turma,
        )
        for nome, email in (("Ruim", "ruim@example.com"), ("Bom", "bom@example.com")):
            responsavel = Responsavel.objects.create(
                escola=self.escola, nome=nome, email=email
            )
            ResponsavelAluno.objects.create(responsavel=responsavel, aluno=aluno)

        original = EmailMultiAlternatives.send

        def send_falhando(self, *args, **kwargs):
            if self.to == ["ruim@example.com"]:
                raise SMTPException("endereço recusado pelo provedor")
            return original(self, *args, **kwargs)

        with patch.object(EmailMultiAlternatives, "send", send_falhando):
            with self.assertLogs("apps.ocorrencias.services", level="ERROR"):
                self.assertEqual(self._criar_ocorrencia(aluno), 201)

        self.assertEqual([email.to for email in mail.outbox], [["bom@example.com"]])
