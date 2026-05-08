"""Testes dos ViewSets da app escola.

Testes usam `APIRequestFactory` + `force_authenticate` (não `APIClient`),
chamando viewsets diretamente sem passar por roteamento de URL. Isso é
adequado pra testar lógica de view, permissões e querysets, mas não cobre
URL routing nem path params. Migrar pra `APIClient` (com `reverse()`) caso
testes precisem validar paths como `/turmas/<id>/`.
"""
from rest_framework.test import APIRequestFactory, force_authenticate

from django.test import TestCase

from apps.accounts.models import Usuario
from apps.escola.models import Aluno, Disciplina, Escola, Turma
from apps.escola.views import (
    AlunoViewSet,
    DisciplinaViewSet,
    EscolaViewSet,
    TurmaViewSet,
)


class _PermissionSetup(TestCase):
    """Setup compartilhado: uma escola principal e usuários vinculados a ela.

    Diretor/professor/secretaria/inspetor recebem `escola=escola` para que o
    `EscopoEscolaMixin` não retorne queryset vazio nos testes de leitura.
    Admin não recebe escola — bypass via `perfil="admin"`.
    """

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

    def _request(self, viewset_cls, action_method, perfil, payload=None):
        if action_method == "list":
            req = self.factory.get("/")
            view = viewset_cls.as_view({"get": "list"})
        elif action_method == "create":
            req = self.factory.post("/", payload or {}, format="json")
            view = viewset_cls.as_view({"post": "create"})
        else:
            raise ValueError(action_method)
        force_authenticate(req, user=self.usuarios[perfil])
        return view(req)


class EscolaPermissionTests(_PermissionSetup):
    """Escola: list/retrieve = admin/diretor; create/update/delete = só admin."""

    def test_list_admin_aceito(self):
        self.assertEqual(self._request(EscolaViewSet, "list", "admin").status_code, 200)

    def test_list_diretor_aceito(self):
        self.assertEqual(self._request(EscolaViewSet, "list", "diretor").status_code, 200)

    def test_list_professor_negado(self):
        self.assertEqual(self._request(EscolaViewSet, "list", "professor").status_code, 403)

    def test_create_admin_aceito(self):
        resp = self._request(EscolaViewSet, "create", "admin", {"nome": "Nova"})
        self.assertEqual(resp.status_code, 201)

    def test_create_diretor_negado(self):
        resp = self._request(EscolaViewSet, "create", "diretor", {"nome": "Nova"})
        self.assertEqual(resp.status_code, 403)


class TurmaPermissionTests(_PermissionSetup):
    def test_list_professor_aceito(self):
        self.assertEqual(self._request(TurmaViewSet, "list", "professor").status_code, 200)

    def test_list_secretaria_negado(self):
        self.assertEqual(self._request(TurmaViewSet, "list", "secretaria").status_code, 403)

    def test_create_diretor_aceito(self):
        payload = {
            "escola": self.escola.id,
            "nome": "2º B",
            "turno": Turma.Turno.MATUTINO,
            "ano_letivo": 2026,
        }
        self.assertEqual(
            self._request(TurmaViewSet, "create", "diretor", payload).status_code, 201
        )

    def test_create_professor_negado(self):
        payload = {
            "escola": self.escola.id,
            "nome": "2º B",
            "turno": Turma.Turno.MATUTINO,
            "ano_letivo": 2026,
        }
        self.assertEqual(
            self._request(TurmaViewSet, "create", "professor", payload).status_code, 403
        )


class DisciplinaPermissionTests(_PermissionSetup):
    def test_list_professor_aceito(self):
        self.assertEqual(
            self._request(DisciplinaViewSet, "list", "professor").status_code, 200
        )

    def test_create_professor_negado(self):
        payload = {"escola": self.escola.id, "nome": "Matemática"}
        self.assertEqual(
            self._request(DisciplinaViewSet, "create", "professor", payload).status_code, 403
        )

    def test_create_diretor_aceito(self):
        payload = {"escola": self.escola.id, "nome": "Matemática"}
        self.assertEqual(
            self._request(DisciplinaViewSet, "create", "diretor", payload).status_code, 201
        )


class AlunoPermissionAndFilterTests(_PermissionSetup):
    @classmethod
    def setUpTestData(cls) -> None:
        super().setUpTestData()
        cls.outra_turma = Turma.objects.create(
            escola=cls.escola,
            nome="2º B",
            turno=Turma.Turno.VESPERTINO,
            ano_letivo=2026,
        )
        cls.alunos_turma_a = [
            Aluno.objects.create(
                escola=cls.escola, matricula=f"A{i}",
                nome_completo=f"João {i}", turma=cls.turma,
            )
            for i in range(3)
        ]
        cls.alunos_outra = [
            Aluno.objects.create(
                escola=cls.escola, matricula=f"B{i}",
                nome_completo=f"Maria {i}", turma=cls.outra_turma,
            )
            for i in range(2)
        ]

    def test_list_professor_aceito(self):
        resp = self._request(AlunoViewSet, "list", "professor")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data), 5)

    def test_filtro_por_turma_funciona(self):
        req = self.factory.get(f"/?turma={self.turma.id}")
        force_authenticate(req, user=self.usuarios["professor"])
        view = AlunoViewSet.as_view({"get": "list"})
        resp = view(req)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data), 3)
        for item in resp.data:
            self.assertEqual(item["turma"], self.turma.id)

    def test_search_por_nome_funciona(self):
        req = self.factory.get("/?search=João")
        force_authenticate(req, user=self.usuarios["professor"])
        view = AlunoViewSet.as_view({"get": "list"})
        resp = view(req)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data), 3)
        for item in resp.data:
            self.assertIn("João", item["nome_completo"])

    def test_create_diretor_aceito_com_turma_consistente(self):
        payload = {
            "escola": self.escola.id,
            "matricula": "C001",
            "nome_completo": "Aluno Novo",
            "turma": self.turma.id,
        }
        self.assertEqual(
            self._request(AlunoViewSet, "create", "diretor", payload).status_code, 201
        )

    def test_create_professor_negado(self):
        payload = {
            "escola": self.escola.id,
            "matricula": "C002",
            "nome_completo": "Aluno X",
            "turma": self.turma.id,
        }
        self.assertEqual(
            self._request(AlunoViewSet, "create", "professor", payload).status_code, 403
        )

    def test_create_falha_quando_turma_de_outra_escola(self):
        outra_escola = Escola.objects.create(nome="Outra")
        outra_turma = Turma.objects.create(
            escola=outra_escola, nome="1º A",
            turno=Turma.Turno.MATUTINO, ano_letivo=2026,
        )
        payload = {
            "escola": self.escola.id,
            "matricula": "C003",
            "nome_completo": "Aluno Y",
            "turma": outra_turma.id,
        }
        resp = self._request(AlunoViewSet, "create", "diretor", payload)
        self.assertEqual(resp.status_code, 400)
        self.assertIn("turma", resp.data)


class EscopoQuerysetTests(TestCase):
    """Verifica que `EscopoEscolaMixin` isola dados entre escolas.

    Cobre o vazamento de leitura levantado no review do PR #4: um usuário
    de escola A nunca deve ver registros de escola B; admin/superuser veem
    tudo; usuário sem escola vinculada vê queryset vazio.
    """

    @classmethod
    def setUpTestData(cls) -> None:
        cls.factory = APIRequestFactory()
        cls.escola_a = Escola.objects.create(nome="Escola A")
        cls.escola_b = Escola.objects.create(nome="Escola B")
        cls.turma_a = Turma.objects.create(
            escola=cls.escola_a, nome="1A",
            turno=Turma.Turno.MATUTINO, ano_letivo=2026,
        )
        cls.turma_b = Turma.objects.create(
            escola=cls.escola_b, nome="1A",
            turno=Turma.Turno.MATUTINO, ano_letivo=2026,
        )
        cls.disc_a = Disciplina.objects.create(escola=cls.escola_a, nome="Mat")
        cls.disc_b = Disciplina.objects.create(escola=cls.escola_b, nome="Mat")
        cls.aluno_a = Aluno.objects.create(
            escola=cls.escola_a, matricula="A1",
            nome_completo="Aluno A", turma=cls.turma_a,
        )
        cls.aluno_b = Aluno.objects.create(
            escola=cls.escola_b, matricula="B1",
            nome_completo="Aluno B", turma=cls.turma_b,
        )
        cls.diretor_a = Usuario.objects.create_user(
            username="da", password="x",
            perfil=Usuario.Perfil.DIRETOR, escola=cls.escola_a,
        )
        cls.professor_a = Usuario.objects.create_user(
            username="pa", password="x",
            perfil=Usuario.Perfil.PROFESSOR, escola=cls.escola_a,
        )
        cls.admin = Usuario.objects.create_user(
            username="ad", password="x", perfil=Usuario.Perfil.ADMIN
        )
        cls.superuser = Usuario.objects.create_superuser(
            username="su", password="x", email="su@t.test"
        )
        cls.usuario_sem_escola = Usuario.objects.create_user(
            username="ne", password="x", perfil=Usuario.Perfil.PROFESSOR
        )

    def _list(self, viewset, user):
        req = self.factory.get("/")
        force_authenticate(req, user=user)
        return viewset.as_view({"get": "list"})(req)

    # -------- Escola --------

    def test_diretor_a_so_ve_sua_escola(self):
        resp = self._list(EscolaViewSet, self.diretor_a)
        ids = {item["id"] for item in resp.data}
        self.assertEqual(ids, {self.escola_a.id})

    def test_admin_ve_todas_as_escolas(self):
        resp = self._list(EscolaViewSet, self.admin)
        ids = {item["id"] for item in resp.data}
        self.assertEqual(ids, {self.escola_a.id, self.escola_b.id})

    def test_superuser_ve_todas_as_escolas(self):
        resp = self._list(EscolaViewSet, self.superuser)
        ids = {item["id"] for item in resp.data}
        self.assertEqual(ids, {self.escola_a.id, self.escola_b.id})

    # -------- Turma / Disciplina / Aluno --------

    def test_professor_a_so_ve_turmas_de_sua_escola(self):
        resp = self._list(TurmaViewSet, self.professor_a)
        ids = {item["id"] for item in resp.data}
        self.assertEqual(ids, {self.turma_a.id})

    def test_professor_a_so_ve_disciplinas_de_sua_escola(self):
        resp = self._list(DisciplinaViewSet, self.professor_a)
        ids = {item["id"] for item in resp.data}
        self.assertEqual(ids, {self.disc_a.id})

    def test_professor_a_so_ve_alunos_de_sua_escola(self):
        resp = self._list(AlunoViewSet, self.professor_a)
        matriculas = {item["matricula"] for item in resp.data}
        self.assertEqual(matriculas, {"A1"})

    def test_admin_ve_alunos_de_todas_escolas(self):
        resp = self._list(AlunoViewSet, self.admin)
        matriculas = {item["matricula"] for item in resp.data}
        self.assertEqual(matriculas, {"A1", "B1"})

    # -------- usuário sem escola --------

    def test_usuario_sem_escola_nao_ve_turmas(self):
        resp = self._list(TurmaViewSet, self.usuario_sem_escola)
        self.assertEqual(len(resp.data), 0)

    def test_usuario_sem_escola_nao_ve_disciplinas(self):
        resp = self._list(DisciplinaViewSet, self.usuario_sem_escola)
        self.assertEqual(len(resp.data), 0)

    def test_usuario_sem_escola_nao_ve_alunos(self):
        resp = self._list(AlunoViewSet, self.usuario_sem_escola)
        self.assertEqual(len(resp.data), 0)
