"""Testes da notificação por email ao responsável ao criar ocorrência.

Em testes o EMAIL_BACKEND é o locmem (settings.TESTING), então os emails
ficam em `django.core.mail.outbox` em vez de serem enviados de verdade.
"""
from datetime import date

from django.core import mail
from django.test import TestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.accounts.models import Usuario
from apps.escola.models import Aluno, Escola, Professor, Turma
from apps.ocorrencias.views import OcorrenciaViewSet


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
