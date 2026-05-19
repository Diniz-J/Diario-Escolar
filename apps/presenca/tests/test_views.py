"""Testes dos ViewSets `RegistroPresenca` e `ItemPresenca`."""
from datetime import date

from rest_framework.test import APIRequestFactory, force_authenticate

from django.test import TestCase

from apps.accounts.models import Usuario
from apps.escola.models import Aluno, Escola, Professor, Turma
from apps.presenca.models import ItemPresenca, RegistroPresenca
from apps.presenca.views import ItemPresencaViewSet, RegistroPresencaViewSet


class _PresencaSetup(TestCase):
    """Setup com escola, turma, 2 alunos ativos + 1 inativo, e os 5 perfis."""

    @classmethod
    def setUpTestData(cls) -> None:
        cls.factory = APIRequestFactory()
        cls.escola = Escola.objects.create(nome="Escola Teste")
        cls.turma = Turma.objects.create(
            escola=cls.escola, nome="1º A",
            turno=Turma.Turno.MATUTINO, ano_letivo=2026,
        )
        cls.aluno_1 = Aluno.objects.create(
            escola=cls.escola, matricula="A1",
            nome_completo="Aluno Um", turma=cls.turma,
        )
        cls.aluno_2 = Aluno.objects.create(
            escola=cls.escola, matricula="A2",
            nome_completo="Aluno Dois", turma=cls.turma,
        )
        # Inativo: não deve ganhar item na chamada.
        cls.aluno_inativo = Aluno.objects.create(
            escola=cls.escola, matricula="A3",
            nome_completo="Aluno Três", turma=cls.turma, ativo=False,
        )
        cls.usuario_docente = Usuario.objects.create_user(
            username="doc", password="x",
            perfil=Usuario.Perfil.PROFESSOR, escola=cls.escola,
        )
        cls.professor = Professor.objects.create(
            escola=cls.escola, usuario=cls.usuario_docente
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
            "secretaria": Usuario.objects.create_user(
                username="sec", password="x",
                perfil=Usuario.Perfil.SECRETARIA, escola=cls.escola,
            ),
            "inspetor": Usuario.objects.create_user(
                username="ins", password="x",
                perfil=Usuario.Perfil.INSPETOR, escola=cls.escola,
            ),
        }

    def _registro_payload(self, **overrides) -> dict:
        payload = {
            "escola": self.escola.id,
            "turma": self.turma.id,
            "professor": self.professor.id,
        }
        payload.update(overrides)
        return payload

    def _request_registro(self, action, perfil, payload=None, pk=None, query=""):
        if action == "list":
            req = self.factory.get(f"/{query}")
            view = RegistroPresencaViewSet.as_view({"get": "list"})
        elif action == "create":
            req = self.factory.post("/", payload or {}, format="json")
            view = RegistroPresencaViewSet.as_view({"post": "create"})
        elif action == "partial_update":
            req = self.factory.patch("/", payload or {}, format="json")
            view = RegistroPresencaViewSet.as_view({"patch": "partial_update"})
        elif action == "destroy":
            req = self.factory.delete("/")
            view = RegistroPresencaViewSet.as_view({"delete": "destroy"})
        else:
            raise ValueError(action)
        force_authenticate(req, user=self.usuarios[perfil])
        return view(req, pk=pk) if pk else view(req)


class RegistroAutoGeracaoTests(_PresencaSetup):
    """Caso de uso central: criar registro gera itens automaticamente."""

    def test_create_gera_item_pra_cada_aluno_ativo(self):
        resp = self._request_registro("create", "professor", self._registro_payload())
        self.assertEqual(resp.status_code, 201)

        registro = RegistroPresenca.objects.get(pk=resp.data["id"])
        itens = registro.itens.all()
        # Aluno inativo NÃO deve aparecer.
        self.assertEqual(itens.count(), 2)
        alunos_ids = {item.aluno_id for item in itens}
        self.assertEqual(alunos_ids, {self.aluno_1.id, self.aluno_2.id})

    def test_itens_gerados_com_status_presente(self):
        resp = self._request_registro("create", "professor", self._registro_payload())
        self.assertEqual(resp.status_code, 201)
        registro = RegistroPresenca.objects.get(pk=resp.data["id"])
        statuses = {item.status for item in registro.itens.all()}
        self.assertEqual(statuses, {ItemPresenca.Status.PRESENTE})

    def test_itens_herdam_escola_do_registro(self):
        resp = self._request_registro("create", "admin", self._registro_payload())
        registro = RegistroPresenca.objects.get(pk=resp.data["id"])
        for item in registro.itens.all():
            self.assertEqual(item.escola_id, registro.escola_id)


class RegistroPermissionTests(_PresencaSetup):
    """Leitura admin/diretor/professor/inspetor; escrita admin/diretor/professor."""

    def test_list_inspetor_aceito(self):
        """Inspetor lê pra monitorar — decisão consciente da app."""
        resp = self._request_registro("list", "inspetor")
        self.assertEqual(resp.status_code, 200)

    def test_list_professor_aceito(self):
        resp = self._request_registro("list", "professor")
        self.assertEqual(resp.status_code, 200)

    def test_list_secretaria_negado(self):
        resp = self._request_registro("list", "secretaria")
        self.assertEqual(resp.status_code, 403)

    def test_create_professor_aceito(self):
        resp = self._request_registro("create", "professor", self._registro_payload())
        self.assertEqual(resp.status_code, 201)

    def test_create_inspetor_negado(self):
        """Inspetor lê, mas não escreve."""
        resp = self._request_registro("create", "inspetor", self._registro_payload())
        self.assertEqual(resp.status_code, 403)

    def test_create_secretaria_negado(self):
        resp = self._request_registro(
            "create", "secretaria", self._registro_payload()
        )
        self.assertEqual(resp.status_code, 403)

    def test_destroy_inspetor_negado(self):
        registro = RegistroPresenca.objects.create(
            escola=self.escola, turma=self.turma
        )
        resp = self._request_registro("destroy", "inspetor", pk=registro.id)
        self.assertEqual(resp.status_code, 403)


class RegistroValidationTests(_PresencaSetup):
    """Replica em API as invariantes do `clean()` e o guard IDOR."""

    @classmethod
    def setUpTestData(cls) -> None:
        super().setUpTestData()
        cls.outra_escola = Escola.objects.create(nome="Outra")
        cls.outra_turma = Turma.objects.create(
            escola=cls.outra_escola, nome="1A",
            turno=Turma.Turno.MATUTINO, ano_letivo=2026,
        )

    def test_falha_turma_de_outra_escola(self):
        payload = self._registro_payload(turma=self.outra_turma.id)
        resp = self._request_registro("create", "admin", payload)
        self.assertEqual(resp.status_code, 400)
        self.assertIn("turma", resp.data)

    def test_falha_data_futura(self):
        payload = self._registro_payload(data="2099-01-01")
        resp = self._request_registro("create", "diretor", payload)
        self.assertEqual(resp.status_code, 400)
        self.assertIn("data", resp.data)

    def test_falha_duplicidade_no_mesmo_dia(self):
        RegistroPresenca.objects.create(
            escola=self.escola, turma=self.turma, data=date.today()
        )
        payload = self._registro_payload(data=date.today().isoformat())
        resp = self._request_registro("create", "diretor", payload)
        # Constraint do banco vira erro DRF 400 (unique violation no serializer).
        self.assertEqual(resp.status_code, 400)

    def test_diretor_nao_cria_em_outra_escola(self):
        """IDOR: diretor da Escola Teste não escreve na Outra."""
        outro_diretor = Usuario.objects.create_user(
            username="d2", password="x",
            perfil=Usuario.Perfil.DIRETOR, escola=self.escola,
        )
        outra_turma_da_outra = Turma.objects.create(
            escola=self.outra_escola, nome="2A",
            turno=Turma.Turno.MATUTINO, ano_letivo=2026,
        )
        req = self.factory.post(
            "/",
            {"escola": self.outra_escola.id, "turma": outra_turma_da_outra.id},
            format="json",
        )
        force_authenticate(req, user=outro_diretor)
        resp = RegistroPresencaViewSet.as_view({"post": "create"})(req)
        self.assertEqual(resp.status_code, 400)
        self.assertIn("escola", resp.data)


class RegistroEscopoTests(TestCase):
    """Isolamento entre escolas via `EscopoEscolaMixin`."""

    @classmethod
    def setUpTestData(cls) -> None:
        cls.factory = APIRequestFactory()
        cls.escola_a = Escola.objects.create(nome="A")
        cls.escola_b = Escola.objects.create(nome="B")
        cls.turma_a = Turma.objects.create(
            escola=cls.escola_a, nome="1A",
            turno=Turma.Turno.MATUTINO, ano_letivo=2026,
        )
        cls.turma_b = Turma.objects.create(
            escola=cls.escola_b, nome="1B",
            turno=Turma.Turno.MATUTINO, ano_letivo=2026,
        )
        cls.reg_a = RegistroPresenca.objects.create(
            escola=cls.escola_a, turma=cls.turma_a
        )
        cls.reg_b = RegistroPresenca.objects.create(
            escola=cls.escola_b, turma=cls.turma_b
        )
        cls.professor_a = Usuario.objects.create_user(
            username="pa", password="x",
            perfil=Usuario.Perfil.PROFESSOR, escola=cls.escola_a,
        )

    def test_professor_a_so_ve_registros_da_sua_escola(self):
        req = self.factory.get("/")
        force_authenticate(req, user=self.professor_a)
        resp = RegistroPresencaViewSet.as_view({"get": "list"})(req)
        ids = {item["id"] for item in resp.data}
        self.assertEqual(ids, {self.reg_a.id})


class ItemPresencaViewTests(_PresencaSetup):
    """Edição de itens via PATCH; criação direta proibida."""

    @classmethod
    def setUpTestData(cls) -> None:
        super().setUpTestData()
        cls.registro = RegistroPresenca.objects.create(
            escola=cls.escola, turma=cls.turma
        )
        cls.item = ItemPresenca.objects.create(
            registro=cls.registro, aluno=cls.aluno_1, escola=cls.escola,
        )

    def _patch(self, perfil, payload, pk):
        req = self.factory.patch("/", payload, format="json")
        force_authenticate(req, user=self.usuarios[perfil])
        return ItemPresencaViewSet.as_view({"patch": "partial_update"})(req, pk=pk)

    def test_professor_atualiza_status(self):
        resp = self._patch(
            "professor",
            {"status": ItemPresenca.Status.AUSENTE},
            self.item.id,
        )
        self.assertEqual(resp.status_code, 200)
        self.item.refresh_from_db()
        self.assertEqual(self.item.status, ItemPresenca.Status.AUSENTE)

    def test_marca_retardatario(self):
        resp = self._patch(
            "professor",
            {"status": ItemPresenca.Status.RETARDATARIO, "observacao": "5 min de atraso"},
            self.item.id,
        )
        self.assertEqual(resp.status_code, 200)
        self.item.refresh_from_db()
        self.assertEqual(self.item.status, ItemPresenca.Status.RETARDATARIO)
        self.assertEqual(self.item.observacao, "5 min de atraso")

    def test_inspetor_le_mas_nao_edita(self):
        # GET passa.
        req = self.factory.get("/")
        force_authenticate(req, user=self.usuarios["inspetor"])
        resp = ItemPresencaViewSet.as_view({"get": "list"})(req)
        self.assertEqual(resp.status_code, 200)
        # PATCH falha.
        resp = self._patch(
            "inspetor", {"status": ItemPresenca.Status.AUSENTE}, self.item.id
        )
        self.assertEqual(resp.status_code, 403)

    def test_create_e_destroy_acoes_nao_existem(self):
        """ItemPresencaViewSet não inclui Create/Destroy mixins de propósito.

        Testar a ausência dos métodos é o mais fiel à intenção: o ciclo de
        vida dos itens pertence ao registro pai. Roteamento (DefaultRouter)
        usa essa ausência pra não expor POST/DELETE nos endpoints.
        """
        viewset = ItemPresencaViewSet()
        self.assertFalse(hasattr(viewset, "create"))
        self.assertFalse(hasattr(viewset, "destroy"))

    def test_aluno_e_registro_sao_read_only(self):
        """PATCH tentando trocar aluno/registro é ignorado silenciosamente."""
        outro_aluno = self.aluno_2
        resp = self._patch(
            "admin",
            {"aluno": outro_aluno.id, "status": ItemPresenca.Status.AUSENTE},
            self.item.id,
        )
        self.assertEqual(resp.status_code, 200)
        self.item.refresh_from_db()
        # `aluno` ficou como estava — DRF descarta campos read_only no payload.
        self.assertEqual(self.item.aluno_id, self.aluno_1.id)
        # Mas `status` mudou.
        self.assertEqual(self.item.status, ItemPresenca.Status.AUSENTE)
