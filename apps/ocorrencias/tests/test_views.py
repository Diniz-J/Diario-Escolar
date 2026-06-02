"""Testes do `OcorrenciaViewSet` — permissões, validação via API e escopo.

Padrão idêntico ao `apps/escola/tests/test_views.py`: `APIRequestFactory` +
`force_authenticate`, chamando o ViewSet diretamente.
"""
from datetime import date, timedelta

from rest_framework.test import APIRequestFactory, force_authenticate

from django.test import TestCase

from apps.accounts.models import Usuario
from apps.escola.models import Aluno, Escola, Professor, Turma
from apps.ocorrencias.models import Ocorrencia
from apps.ocorrencias.views import OcorrenciaViewSet


class _OcorrenciaSetup(TestCase):
    """Setup com uma escola principal, turma, aluno, professor e os 5 perfis."""

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
        cls.aluno = Aluno.objects.create(
            escola=cls.escola,
            matricula="A1",
            nome_completo="Aluno Teste",
            turma=cls.turma,
        )
        cls.usuario_docente = Usuario.objects.create_user(
            username="doc",
            password="x",
            perfil=Usuario.Perfil.PROFESSOR,
            escola=cls.escola,
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

    def _request(self, action_method, perfil, payload=None, query="", pk=None):
        """Dispara request no ViewSet sem passar por URL routing.

        Suporta: list, create, partial_update, update, destroy. Para ações
        sobre objeto, `pk` é obrigatório.
        """
        if action_method == "list":
            req = self.factory.get(f"/{query}")
            view = OcorrenciaViewSet.as_view({"get": "list"})
        elif action_method == "create":
            req = self.factory.post("/", payload or {}, format="json")
            view = OcorrenciaViewSet.as_view({"post": "create"})
        elif action_method == "partial_update":
            req = self.factory.patch("/", payload or {}, format="json")
            view = OcorrenciaViewSet.as_view({"patch": "partial_update"})
        elif action_method == "update":
            req = self.factory.put("/", payload or {}, format="json")
            view = OcorrenciaViewSet.as_view({"put": "update"})
        elif action_method == "destroy":
            req = self.factory.delete("/")
            view = OcorrenciaViewSet.as_view({"delete": "destroy"})
        else:
            raise ValueError(action_method)
        force_authenticate(req, user=self.usuarios[perfil])
        if pk is not None:
            return view(req, pk=pk)
        return view(req)

    def _payload_valido(self) -> dict:
        return {
            "escola": self.escola.id,
            "turma": self.turma.id,
            "aluno": self.aluno.id,
            "professor": self.professor.id,
            "descricao": "Aluno conversando durante a aula",
        }


class OcorrenciaPermissionTests(_OcorrenciaSetup):
    """Admin/diretor/professor têm acesso total; secretaria/inspetor não."""

    def test_list_admin_aceito(self):
        self.assertEqual(self._request("list", "admin").status_code, 200)

    def test_list_diretor_aceito(self):
        self.assertEqual(self._request("list", "diretor").status_code, 200)

    def test_list_professor_aceito(self):
        self.assertEqual(self._request("list", "professor").status_code, 200)

    def test_list_secretaria_aceito(self):
        """Alias de diretor — lê ocorrências."""
        self.assertEqual(self._request("list", "secretaria").status_code, 200)

    def test_list_inspetor_aceito(self):
        """Alias de professor — lê ocorrências."""
        self.assertEqual(self._request("list", "inspetor").status_code, 200)

    def test_create_professor_aceito(self):
        """Professor é o caso de uso principal — precisa conseguir abrir ocorrência."""
        resp = self._request("create", "professor", self._payload_valido())
        self.assertEqual(resp.status_code, 201)

    def test_create_diretor_aceito(self):
        resp = self._request("create", "diretor", self._payload_valido())
        self.assertEqual(resp.status_code, 201)

    def test_create_admin_aceito(self):
        resp = self._request("create", "admin", self._payload_valido())
        self.assertEqual(resp.status_code, 201)

    def test_create_secretaria_aceito(self):
        """Alias de diretor — abre ocorrência."""
        resp = self._request("create", "secretaria", self._payload_valido())
        self.assertEqual(resp.status_code, 201)


class OcorrenciaValidationTests(_OcorrenciaSetup):
    """Replica em testes de API as invariantes do `clean()`."""

    @classmethod
    def setUpTestData(cls) -> None:
        super().setUpTestData()
        # Recursos de outra escola para os cenários de mismatch.
        cls.outra_escola = Escola.objects.create(nome="Outra")
        cls.outra_turma = Turma.objects.create(
            escola=cls.outra_escola, nome="1º A",
            turno=Turma.Turno.MATUTINO, ano_letivo=2026,
        )
        cls.outro_aluno = Aluno.objects.create(
            escola=cls.outra_escola, matricula="O1",
            nome_completo="Outro Aluno", turma=cls.outra_turma,
        )
        cls.outro_docente = Usuario.objects.create_user(
            username="doc_outro", password="x",
            perfil=Usuario.Perfil.PROFESSOR, escola=cls.outra_escola,
        )
        cls.outro_professor = Professor.objects.create(
            escola=cls.outra_escola, usuario=cls.outro_docente
        )
        # Segunda turma da mesma escola — pra testar mismatch turma/aluno.
        cls.turma_outra_aluno = Turma.objects.create(
            escola=cls.escola, nome="2º B",
            turno=Turma.Turno.VESPERTINO, ano_letivo=2026,
        )

    def test_falha_quando_aluno_de_outra_escola(self):
        payload = self._payload_valido() | {"aluno": self.outro_aluno.id}
        resp = self._request("create", "diretor", payload)
        self.assertEqual(resp.status_code, 400)
        self.assertIn("aluno", resp.data)

    def test_falha_quando_turma_nao_e_do_aluno(self):
        payload = self._payload_valido() | {"turma": self.turma_outra_aluno.id}
        resp = self._request("create", "diretor", payload)
        self.assertEqual(resp.status_code, 400)
        self.assertIn("turma", resp.data)

    def test_falha_quando_professor_de_outra_escola(self):
        payload = self._payload_valido() | {"professor": self.outro_professor.id}
        resp = self._request("create", "diretor", payload)
        self.assertEqual(resp.status_code, 400)
        self.assertIn("professor", resp.data)

    def test_falha_quando_data_no_futuro(self):
        amanha = (date.today() + timedelta(days=1)).isoformat()
        payload = self._payload_valido() | {"data_ocorrencia": amanha}
        resp = self._request("create", "diretor", payload)
        self.assertEqual(resp.status_code, 400)
        self.assertIn("data_ocorrencia", resp.data)


class OcorrenciaFilterAndSearchTests(_OcorrenciaSetup):
    """Filtros declarativos e search em `descricao`."""

    @classmethod
    def setUpTestData(cls) -> None:
        super().setUpTestData()
        cls.outro_aluno = Aluno.objects.create(
            escola=cls.escola, matricula="A2",
            nome_completo="Outro Aluno", turma=cls.turma,
        )
        cls.oc_aberta = Ocorrencia.objects.create(
            escola=cls.escola, turma=cls.turma, aluno=cls.aluno,
            professor=cls.professor, descricao="conversava em sala",
        )
        cls.oc_resolvida = Ocorrencia.objects.create(
            escola=cls.escola, turma=cls.turma, aluno=cls.outro_aluno,
            professor=cls.professor, descricao="atraso reincidente",
            status=Ocorrencia.Status.RESOLVIDA,
        )

    def test_filtro_por_status(self):
        resp = self._request("list", "professor", query="?status=aberta")
        self.assertEqual(resp.status_code, 200)
        ids = {item["id"] for item in resp.data}
        self.assertEqual(ids, {self.oc_aberta.id})

    def test_filtro_por_aluno(self):
        resp = self._request("list", "professor", query=f"?aluno={self.outro_aluno.id}")
        self.assertEqual(resp.status_code, 200)
        ids = {item["id"] for item in resp.data}
        self.assertEqual(ids, {self.oc_resolvida.id})

    def test_search_por_descricao(self):
        resp = self._request("list", "professor", query="?search=atraso")
        self.assertEqual(resp.status_code, 200)
        ids = {item["id"] for item in resp.data}
        self.assertEqual(ids, {self.oc_resolvida.id})


class OcorrenciaEscopoTests(TestCase):
    """Verifica isolamento entre escolas via `EscopoEscolaMixin`."""

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
            escola=cls.escola_b, nome="1A",
            turno=Turma.Turno.MATUTINO, ano_letivo=2026,
        )
        cls.aluno_a = Aluno.objects.create(
            escola=cls.escola_a, matricula="A1",
            nome_completo="Aluno A", turma=cls.turma_a,
        )
        cls.aluno_b = Aluno.objects.create(
            escola=cls.escola_b, matricula="B1",
            nome_completo="Aluno B", turma=cls.turma_b,
        )
        cls.oc_a = Ocorrencia.objects.create(
            escola=cls.escola_a, turma=cls.turma_a, aluno=cls.aluno_a,
            descricao="ocorrência da escola A",
        )
        cls.oc_b = Ocorrencia.objects.create(
            escola=cls.escola_b, turma=cls.turma_b, aluno=cls.aluno_b,
            descricao="ocorrência da escola B",
        )

        cls.professor_a = Usuario.objects.create_user(
            username="pa", password="x",
            perfil=Usuario.Perfil.PROFESSOR, escola=cls.escola_a,
        )
        cls.admin = Usuario.objects.create_user(
            username="ad", password="x", perfil=Usuario.Perfil.ADMIN
        )
        cls.usuario_sem_escola = Usuario.objects.create_user(
            username="ne", password="x", perfil=Usuario.Perfil.PROFESSOR
        )

    def _list(self, user):
        req = self.factory.get("/")
        force_authenticate(req, user=user)
        return OcorrenciaViewSet.as_view({"get": "list"})(req)

    def test_professor_a_so_ve_ocorrencias_da_sua_escola(self):
        resp = self._list(self.professor_a)
        ids = {item["id"] for item in resp.data}
        self.assertEqual(ids, {self.oc_a.id})

    def test_admin_ve_todas_as_ocorrencias(self):
        resp = self._list(self.admin)
        ids = {item["id"] for item in resp.data}
        self.assertEqual(ids, {self.oc_a.id, self.oc_b.id})

    def test_usuario_sem_escola_nao_ve_nada(self):
        resp = self._list(self.usuario_sem_escola)
        self.assertEqual(len(resp.data), 0)


class OcorrenciaWritePermissionTests(_OcorrenciaSetup):
    """Cobre PATCH/PUT/DELETE: admin/diretor/professor escrevem; outros não.

    Inclui o caso de uso documentado: um professor pode atualizar o status
    de ocorrência aberta por outro professor (colegas se ajudam a resolver).
    """

    @classmethod
    def setUpTestData(cls) -> None:
        super().setUpTestData()
        # Usuário Professor distinto do que abre a ocorrência — pra simular
        # "outro professor da mesma escola edita o status".
        cls.outro_docente_usuario = Usuario.objects.create_user(
            username="doc2", password="x",
            perfil=Usuario.Perfil.PROFESSOR, escola=cls.escola,
        )
        cls.outro_professor_obj = Professor.objects.create(
            escola=cls.escola, usuario=cls.outro_docente_usuario
        )
        cls.ocorrencia = Ocorrencia.objects.create(
            escola=cls.escola, turma=cls.turma, aluno=cls.aluno,
            professor=cls.outro_professor_obj,  # aberta por OUTRO professor
            descricao="aluno conversando",
        )

    def test_professor_atualiza_status_de_ocorrencia_de_colega(self):
        """Caso de uso central: professor B resolve ocorrência aberta por A."""
        resp = self._request(
            "partial_update", "professor",
            payload={"status": Ocorrencia.Status.RESOLVIDA},
            pk=self.ocorrencia.id,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["status"], Ocorrencia.Status.RESOLVIDA)

    def test_diretor_atualiza_aceito(self):
        resp = self._request(
            "partial_update", "diretor",
            payload={"status": Ocorrencia.Status.ARQUIVADA},
            pk=self.ocorrencia.id,
        )
        self.assertEqual(resp.status_code, 200)

    def test_admin_atualiza_aceito(self):
        resp = self._request(
            "partial_update", "admin",
            payload={"status": Ocorrencia.Status.EM_ANDAMENTO},
            pk=self.ocorrencia.id,
        )
        self.assertEqual(resp.status_code, 200)

    def test_secretaria_update_aceito(self):
        """Alias de diretor."""
        resp = self._request(
            "partial_update", "secretaria",
            payload={"status": Ocorrencia.Status.RESOLVIDA},
            pk=self.ocorrencia.id,
        )
        self.assertEqual(resp.status_code, 200)

    def test_inspetor_update_aceito(self):
        """Alias de professor."""
        resp = self._request(
            "partial_update", "inspetor",
            payload={"status": Ocorrencia.Status.RESOLVIDA},
            pk=self.ocorrencia.id,
        )
        self.assertEqual(resp.status_code, 200)

    def test_professor_destroy_aceito(self):
        resp = self._request("destroy", "professor", pk=self.ocorrencia.id)
        self.assertEqual(resp.status_code, 204)

    def test_secretaria_destroy_aceito(self):
        """Alias de diretor."""
        resp = self._request("destroy", "secretaria", pk=self.ocorrencia.id)
        self.assertEqual(resp.status_code, 204)


class OcorrenciaPatchPartialTests(_OcorrenciaSetup):
    """Cobre o tratamento especial de PATCH parcial no `OcorrenciaSerializer`.

    O serializer precisa diferenciar três casos para `professor`:
    1. Campo ausente do payload → mantém o atual.
    2. Campo enviado como null → limpa o professor.
    3. Campo enviado com id válido → troca.

    Sem esses testes a lógica em `serializers.py:46-51` não tem rede de proteção.
    """

    @classmethod
    def setUpTestData(cls) -> None:
        super().setUpTestData()
        cls.ocorrencia = Ocorrencia.objects.create(
            escola=cls.escola, turma=cls.turma, aluno=cls.aluno,
            professor=cls.professor, descricao="texto original",
        )

    def test_patch_so_descricao_mantem_professor(self):
        """PATCH sem mandar `professor` não pode derrubar o vínculo existente."""
        resp = self._request(
            "partial_update", "professor",
            payload={"descricao": "texto novo"},
            pk=self.ocorrencia.id,
        )
        self.assertEqual(resp.status_code, 200)
        self.ocorrencia.refresh_from_db()
        self.assertEqual(self.ocorrencia.descricao, "texto novo")
        self.assertEqual(self.ocorrencia.professor_id, self.professor.id)

    def test_patch_professor_null_limpa_vinculo(self):
        """`professor=null` é como admin/diretor "anonimiza" a autoria."""
        resp = self._request(
            "partial_update", "diretor",
            payload={"professor": None},
            pk=self.ocorrencia.id,
        )
        self.assertEqual(resp.status_code, 200)
        self.ocorrencia.refresh_from_db()
        self.assertIsNone(self.ocorrencia.professor_id)

    def test_patch_aluno_de_outra_escola_falha(self):
        """Invariante de escola é revalidada mesmo em PATCH."""
        outra_escola = Escola.objects.create(nome="Outra")
        outra_turma = Turma.objects.create(
            escola=outra_escola, nome="1A",
            turno=Turma.Turno.MATUTINO, ano_letivo=2026,
        )
        outro_aluno = Aluno.objects.create(
            escola=outra_escola, matricula="X1",
            nome_completo="Aluno Externo", turma=outra_turma,
        )
        resp = self._request(
            "partial_update", "diretor",
            payload={"aluno": outro_aluno.id},
            pk=self.ocorrencia.id,
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("aluno", resp.data)


class OcorrenciaCrossEscolaWriteTests(TestCase):
    """Guard contra IDOR: usuário não-admin não escreve em escola alheia.

    Mesmo que `EscopoEscolaMixin` esconda leitura cross-escola, sem este
    guard um diretor da Escola A poderia gravar registros na Escola B
    enviando `escola=B_id` no payload. Admin/superuser legitimamente operam
    em qualquer escola e devem passar.
    """

    @classmethod
    def setUpTestData(cls) -> None:
        cls.factory = APIRequestFactory()
        cls.escola_a = Escola.objects.create(nome="A")
        cls.escola_b = Escola.objects.create(nome="B")
        cls.turma_b = Turma.objects.create(
            escola=cls.escola_b, nome="1B",
            turno=Turma.Turno.MATUTINO, ano_letivo=2026,
        )
        cls.aluno_b = Aluno.objects.create(
            escola=cls.escola_b, matricula="B1",
            nome_completo="Aluno B", turma=cls.turma_b,
        )
        cls.diretor_a = Usuario.objects.create_user(
            username="da", password="x",
            perfil=Usuario.Perfil.DIRETOR, escola=cls.escola_a,
        )
        cls.admin = Usuario.objects.create_user(
            username="ad", password="x", perfil=Usuario.Perfil.ADMIN
        )

    def _post(self, user, payload):
        req = self.factory.post("/", payload, format="json")
        force_authenticate(req, user=user)
        return OcorrenciaViewSet.as_view({"post": "create"})(req)

    def test_diretor_a_nao_cria_em_escola_b(self):
        """Diretor da Escola A tentando gravar com `escola=B_id` deve receber 400."""
        payload = {
            "escola": self.escola_b.id,
            "turma": self.turma_b.id,
            "aluno": self.aluno_b.id,
            "descricao": "tentativa cross-escola",
        }
        resp = self._post(self.diretor_a, payload)
        self.assertEqual(resp.status_code, 400)
        self.assertIn("escola", resp.data)

    def test_admin_cria_em_qualquer_escola(self):
        """Admin tem bypass legítimo — opera em todas as escolas."""
        payload = {
            "escola": self.escola_b.id,
            "turma": self.turma_b.id,
            "aluno": self.aluno_b.id,
            "descricao": "admin operando cross-escola",
        }
        resp = self._post(self.admin, payload)
        self.assertEqual(resp.status_code, 201)
