"""Testes do `AutoEscopoEscolaMixin`.

Verifica o cross-cutting:
- Usuário com escola vinculada (diretor/professor/secretaria/inspetor)
  cria sem enviar `escola` no payload → vai pra escola dele.
- Tentar enviar `escola` de OUTRA escola é bloqueado pelo guard IDOR
  (`validate_escola`).
- Admin sem escola vinculada precisa enviar `escola` explicitamente —
  caso contrário recebe 400 claro.
- Admin com escola vinculada pode criar em qualquer escola (validate
  permite e mixin não força).

Usa `Turma` como modelo de prova porque o padrão se aplica a todos os
modelos com FK `escola` (Aluno, Disciplina, Ocorrencia, etc.).
"""
from rest_framework.test import APIClient
from django.test import TestCase

from apps.accounts.models import Usuario
from apps.escola.models import Escola, Turma


class AutoEscopoEscolaMixinTests(TestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        cls.escola_a = Escola.objects.create(nome="Escola A")
        cls.escola_b = Escola.objects.create(nome="Escola B")
        cls.diretor = Usuario.objects.create_user(
            username="diretor_a",
            password="x",
            perfil=Usuario.Perfil.DIRETOR,
            escola=cls.escola_a,
        )
        cls.admin_global = Usuario.objects.create_user(
            username="admin_global",
            password="x",
            perfil=Usuario.Perfil.ADMIN,
            escola=None,
        )

    def setUp(self) -> None:
        self.client = APIClient()

    def _payload_turma(self, **overrides):
        # Não passa `escola` por padrão — o ponto do teste.
        payload = {
            "nome": "1º A",
            "turno": "matutino",
            "ano_letivo": 2026,
        }
        payload.update(overrides)
        return payload

    def test_diretor_cria_sem_escola_e_resolvida_pela_sua(self) -> None:
        self.client.force_authenticate(user=self.diretor)
        resp = self.client.post(
            "/api/v1/turmas/", self._payload_turma(), format="json"
        )
        self.assertEqual(resp.status_code, 201, msg=resp.content)
        turma = Turma.objects.get(pk=resp.data["id"])
        self.assertEqual(turma.escola_id, self.escola_a.id)

    def test_diretor_passando_escola_propria_funciona(self) -> None:
        self.client.force_authenticate(user=self.diretor)
        resp = self.client.post(
            "/api/v1/turmas/",
            self._payload_turma(escola=self.escola_a.id),
            format="json",
        )
        self.assertEqual(resp.status_code, 201, msg=resp.content)

    def test_diretor_tentando_escola_alheia_e_bloqueado(self) -> None:
        # IDOR guard: `validate_escola` recusa cross-tenant pra não-admin.
        self.client.force_authenticate(user=self.diretor)
        resp = self.client.post(
            "/api/v1/turmas/",
            self._payload_turma(escola=self.escola_b.id),
            format="json",
        )
        self.assertEqual(resp.status_code, 400, msg=resp.content)
        # Erro vem no campo `escola`.
        self.assertIn("escola", resp.data)

    def test_admin_global_sem_escola_no_payload_recebe_400(self) -> None:
        # Sem escola no perfil E sem escola no payload, o mixin levanta
        # ValidationError explícito em vez de IntegrityError.
        self.client.force_authenticate(user=self.admin_global)
        resp = self.client.post(
            "/api/v1/turmas/", self._payload_turma(), format="json"
        )
        self.assertEqual(resp.status_code, 400, msg=resp.content)
        self.assertIn("escola", resp.data)

    def test_admin_global_passando_escola_explicita_funciona(self) -> None:
        self.client.force_authenticate(user=self.admin_global)
        resp = self.client.post(
            "/api/v1/turmas/",
            self._payload_turma(escola=self.escola_b.id),
            format="json",
        )
        self.assertEqual(resp.status_code, 201, msg=resp.content)
        turma = Turma.objects.get(pk=resp.data["id"])
        self.assertEqual(turma.escola_id, self.escola_b.id)
