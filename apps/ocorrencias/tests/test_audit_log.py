"""Testes do audit log via django-simple-history.

Verifica o cross-cutting:
- Operações via API geram entradas históricas com `history_user` correto.
- O diff entre versões captura as mudanças de campo.
- O soft delete do Aluno é registrado como mudança (não como exclusão real).

Usa `APIClient` (não `APIRequestFactory`) porque o `HistoryRequestMiddleware`
do simple-history precisa do stack completo de middleware pra capturar
`request.user` — e `APIRequestFactory` pula middleware.

A app `ocorrencias` foi escolhida pra carregar estes testes porque é o
modelo onde o audit log tem maior valor de produto (disputa com pais).
"""
from datetime import date

from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import Usuario
from apps.escola.models import Aluno, Escola, Turma
from apps.ocorrencias.models import Ocorrencia


class AuditLogTests(TestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        cls.escola = Escola.objects.create(nome="Escola Teste")
        cls.turma = Turma.objects.create(
            escola=cls.escola,
            nome="1º A",
            turno=Turma.Turno.MATUTINO,
            ano_letivo=2026,
        )
        cls.admin = Usuario.objects.create_user(
            username="adm",
            password="x",
            perfil=Usuario.Perfil.ADMIN,
            escola=cls.escola,
        )

    def setUp(self) -> None:
        self.client = APIClient()
        self.client.force_authenticate(user=self.admin)
        # Cria o aluno DIRETO no banco (não via API) pra que o teste de
        # soft delete tenha um estado inicial conhecido sem poluir o
        # histórico de Ocorrencia com efeitos colaterais.
        self.aluno = Aluno.objects.create(
            escola=self.escola,
            matricula="A1",
            nome_completo="Ana Silva",
            turma=self.turma,
            nome_responsavel="Maria Silva",
            email_responsavel="maria@example.com",
        )

    def _criar_ocorrencia(self, **overrides) -> int:
        """Cria uma ocorrência via API e devolve o id do recurso criado."""
        payload = {
            "escola": self.escola.id,
            "turma": self.turma.id,
            "aluno": self.aluno.id,
            "descricao": "Conversa excessiva durante a aula.",
            "data_ocorrencia": date.today().isoformat(),
            "status": "aberta",
            **overrides,
        }
        resp = self.client.post(
            "/api/v1/ocorrencias/", payload, format="json"
        )
        self.assertEqual(
            resp.status_code, 201, msg=f"Falhou ao criar: {resp.content!r}"
        )
        return resp.data["id"]

    def test_criar_ocorrencia_via_api_registra_history_user(self) -> None:
        oc_id = self._criar_ocorrencia()
        oc = Ocorrencia.objects.get(pk=oc_id)
        self.assertEqual(oc.history.count(), 1)
        entry = oc.history.first()
        self.assertEqual(entry.history_type, "+")
        self.assertEqual(entry.history_user_id, self.admin.id)

    def test_editar_ocorrencia_registra_diff_de_status(self) -> None:
        oc_id = self._criar_ocorrencia()
        resp = self.client.patch(
            f"/api/v1/ocorrencias/{oc_id}/",
            {"status": "resolvida"},
            format="json",
        )
        self.assertEqual(resp.status_code, 200, msg=resp.content)

        oc = Ocorrencia.objects.get(pk=oc_id)
        self.assertEqual(oc.history.count(), 2)
        # history.all() é ordenado por -history_date — primeiro é o mais recente.
        novo, antigo = oc.history.all()
        self.assertEqual(novo.history_type, "~")
        self.assertEqual(antigo.history_type, "+")
        delta = novo.diff_against(antigo)
        campos_alterados = {change.field for change in delta.changes}
        self.assertIn("status", campos_alterados)
        # E o history_user da mudança é o admin que fez o PATCH.
        self.assertEqual(novo.history_user_id, self.admin.id)

    def test_soft_delete_aluno_e_registrado(self) -> None:
        # Snapshot inicial do histórico do aluno (criado direto no setUp,
        # pode não ter entry se HistoricalRecords ainda não tava lá; aqui
        # ele já está, então há 1 entrada `+`).
        contagem_inicial = self.aluno.history.count()

        resp = self.client.delete(f"/api/v1/alunos/{self.aluno.id}/")
        self.assertIn(resp.status_code, (200, 204), msg=resp.content)

        self.aluno.refresh_from_db()
        self.assertFalse(self.aluno.ativo, "DELETE deveria ter feito soft delete")

        entradas = self.aluno.history.all()
        self.assertEqual(entradas.count(), contagem_inicial + 1)
        # A entrada mais recente é a do soft delete: tipo `~`, ativo=False,
        # atribuída ao admin que disparou o DELETE.
        ultima = entradas.first()
        self.assertEqual(ultima.history_type, "~")
        self.assertFalse(ultima.ativo)
        self.assertEqual(ultima.history_user_id, self.admin.id)
