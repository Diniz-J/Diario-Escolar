"""Testes dos ViewSets `Tarefa` e `EntregaTarefa`."""
from datetime import date, timedelta
from decimal import Decimal

from rest_framework.test import APIRequestFactory, force_authenticate

from django.test import TestCase

from apps.accounts.models import Usuario
from apps.escola.models import Aluno, Disciplina, Escola, Turma
from apps.tarefas.models import EntregaTarefa, Tarefa
from apps.tarefas.views import EntregaTarefaViewSet, TarefaViewSet


class _Setup(TestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        cls.factory = APIRequestFactory()
        cls.escola = Escola.objects.create(nome="Escola Teste")
        cls.turma = Turma.objects.create(
            escola=cls.escola, nome="1º A",
            turno=Turma.Turno.MATUTINO, ano_letivo=2026,
        )
        cls.disc = Disciplina.objects.create(escola=cls.escola, nome="Mat")
        # Dois ativos + um inativo (este NÃO deve receber entrega).
        cls.aluno1 = Aluno.objects.create(
            escola=cls.escola, matricula="A1",
            nome_completo="Aluno Um", turma=cls.turma,
        )
        cls.aluno2 = Aluno.objects.create(
            escola=cls.escola, matricula="A2",
            nome_completo="Aluno Dois", turma=cls.turma,
        )
        cls.aluno_inativo = Aluno.objects.create(
            escola=cls.escola, matricula="A3",
            nome_completo="Aluno Três", turma=cls.turma, ativo=False,
        )
        cls.usuarios = {
            "admin": Usuario.objects.create_user(
                username="adm", password="x", perfil=Usuario.Perfil.ADMIN
            ),
            "diretor": Usuario.objects.create_user(
                username="dir", password="x",
                perfil=Usuario.Perfil.DIRETOR, escola=cls.escola,
            ),
            "professor": Usuario.objects.create_user(
                username="prof", password="x",
                perfil=Usuario.Perfil.PROFESSOR, escola=cls.escola,
            ),
            "inspetor": Usuario.objects.create_user(
                username="ins", password="x",
                perfil=Usuario.Perfil.INSPETOR, escola=cls.escola,
            ),
            "secretaria": Usuario.objects.create_user(
                username="sec", password="x",
                perfil=Usuario.Perfil.SECRETARIA, escola=cls.escola,
            ),
        }


class TarefaAutoGeracaoTests(_Setup):
    """Criar tarefa gera automaticamente uma entrega por aluno ativo."""

    def _payload(self, **overrides):
        payload = {
            "escola": self.escola.id,
            "turma": self.turma.id,
            "disciplina": self.disc.id,
            "titulo": "Lista 1",
        }
        payload.update(overrides)
        return payload

    def _create(self, perfil, payload):
        req = self.factory.post("/", payload, format="json")
        force_authenticate(req, user=self.usuarios[perfil])
        return TarefaViewSet.as_view({"post": "create"})(req)

    def test_create_gera_entrega_pra_cada_aluno_ativo(self):
        resp = self._create("professor", self._payload())
        self.assertEqual(resp.status_code, 201)
        tarefa = Tarefa.objects.get(pk=resp.data["id"])
        entregas = tarefa.entregas.all()
        self.assertEqual(entregas.count(), 2)
        ids = {e.aluno_id for e in entregas}
        self.assertEqual(ids, {self.aluno1.id, self.aluno2.id})

    def test_entregas_geradas_como_nao_entregues(self):
        resp = self._create("professor", self._payload())
        tarefa = Tarefa.objects.get(pk=resp.data["id"])
        statuses = {e.entregue for e in tarefa.entregas.all()}
        self.assertEqual(statuses, {False})


class TarefaValidationTests(_Setup):
    def _create(self, perfil, payload):
        req = self.factory.post("/", payload, format="json")
        force_authenticate(req, user=self.usuarios[perfil])
        return TarefaViewSet.as_view({"post": "create"})(req)

    def _payload(self, **overrides):
        payload = {
            "escola": self.escola.id,
            "turma": self.turma.id,
            "disciplina": self.disc.id,
            "titulo": "x",
        }
        payload.update(overrides)
        return payload

    def test_prazo_anterior_ao_lancamento_falha(self):
        payload = self._payload(
            data_lancamento=date.today().isoformat(),
            prazo=(date.today() - timedelta(days=1)).isoformat(),
        )
        resp = self._create("diretor", payload)
        self.assertEqual(resp.status_code, 400)
        self.assertIn("prazo", resp.data)

    def test_vale_nota_sem_nota_maxima_falha(self):
        payload = self._payload(vale_nota=True)
        resp = self._create("diretor", payload)
        self.assertEqual(resp.status_code, 400)
        self.assertIn("nota_maxima", resp.data)


class TarefaPermissionTests(_Setup):
    def _list(self, perfil):
        req = self.factory.get("/")
        force_authenticate(req, user=self.usuarios[perfil])
        return TarefaViewSet.as_view({"get": "list"})(req)

    def _create(self, perfil):
        req = self.factory.post("/", {
            "escola": self.escola.id,
            "turma": self.turma.id,
            "disciplina": self.disc.id,
            "titulo": "x",
        }, format="json")
        force_authenticate(req, user=self.usuarios[perfil])
        return TarefaViewSet.as_view({"post": "create"})(req)

    def test_inspetor_le(self):
        self.assertEqual(self._list("inspetor").status_code, 200)

    def test_inspetor_nao_escreve(self):
        self.assertEqual(self._create("inspetor").status_code, 403)

    def test_secretaria_negado_em_tudo(self):
        self.assertEqual(self._list("secretaria").status_code, 403)
        self.assertEqual(self._create("secretaria").status_code, 403)

    def test_professor_cria(self):
        self.assertEqual(self._create("professor").status_code, 201)


class EntregaTarefaViewSetTests(_Setup):
    def setUp(self) -> None:
        self.tarefa = Tarefa.objects.create(
            escola=self.escola, turma=self.turma, disciplina=self.disc,
            titulo="x", vale_nota=True, nota_maxima=Decimal("10.00"),
        )
        self.entrega = EntregaTarefa.objects.create(
            tarefa=self.tarefa, aluno=self.aluno1, escola=self.escola,
        )

    def _patch(self, perfil, payload):
        req = self.factory.patch("/", payload, format="json")
        force_authenticate(req, user=self.usuarios[perfil])
        return EntregaTarefaViewSet.as_view({"patch": "partial_update"})(
            req, pk=self.entrega.id
        )

    def test_marcar_entregue_auto_preenche_data(self):
        resp = self._patch("professor", {"entregue": True})
        self.assertEqual(resp.status_code, 200)
        self.entrega.refresh_from_db()
        self.assertTrue(self.entrega.entregue)
        self.assertEqual(self.entrega.data_entrega, date.today())

    def test_desmarcar_entregue_limpa_data_e_nota(self):
        self.entrega.entregue = True
        self.entrega.data_entrega = date.today()
        self.entrega.nota = Decimal("8.00")
        self.entrega.save()
        resp = self._patch("professor", {"entregue": False})
        self.assertEqual(resp.status_code, 200)
        self.entrega.refresh_from_db()
        self.assertFalse(self.entrega.entregue)
        self.assertIsNone(self.entrega.data_entrega)
        self.assertIsNone(self.entrega.nota)

    def test_nota_acima_da_maxima_falha(self):
        resp = self._patch(
            "professor", {"entregue": True, "nota": "11.00"}
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("nota", resp.data)

    def test_create_action_nao_existe(self):
        viewset = EntregaTarefaViewSet()
        self.assertFalse(hasattr(viewset, "create"))
        self.assertFalse(hasattr(viewset, "destroy"))


class CrossEscolaIDORTests(TestCase):
    """Diretor de escola A não pode lançar tarefa na escola B."""

    @classmethod
    def setUpTestData(cls) -> None:
        cls.factory = APIRequestFactory()
        cls.escola_a = Escola.objects.create(nome="A")
        cls.escola_b = Escola.objects.create(nome="B")
        cls.turma_b = Turma.objects.create(
            escola=cls.escola_b, nome="1B",
            turno=Turma.Turno.MATUTINO, ano_letivo=2026,
        )
        cls.disc_b = Disciplina.objects.create(escola=cls.escola_b, nome="Mat")
        cls.diretor_a = Usuario.objects.create_user(
            username="da", password="x",
            perfil=Usuario.Perfil.DIRETOR, escola=cls.escola_a,
        )

    def test_diretor_a_nao_cria_em_b(self):
        req = self.factory.post(
            "/",
            {
                "escola": self.escola_b.id,
                "turma": self.turma_b.id,
                "disciplina": self.disc_b.id,
                "titulo": "tentativa",
            },
            format="json",
        )
        force_authenticate(req, user=self.diretor_a)
        resp = TarefaViewSet.as_view({"post": "create"})(req)
        self.assertEqual(resp.status_code, 400)
        self.assertIn("escola", resp.data)
