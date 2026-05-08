"""Testes dos ViewSets da app escola — matriz de permissões e filtros."""
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
                username="dir", password="x", perfil=Usuario.Perfil.DIRETOR
            ),
            "professor": Usuario.objects.create_user(
                username="prof", password="x", perfil=Usuario.Perfil.PROFESSOR
            ),
            "secretaria": Usuario.objects.create_user(
                username="sec", password="x", perfil=Usuario.Perfil.SECRETARIA
            ),
            "inspetor": Usuario.objects.create_user(
                username="ins", password="x", perfil=Usuario.Perfil.INSPETOR
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
    """Turma: leitura = admin/diretor/professor; escrita = admin/diretor."""

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
        resp = self._request(TurmaViewSet, "create", "diretor", payload)
        self.assertEqual(resp.status_code, 201)

    def test_create_professor_negado(self):
        payload = {
            "escola": self.escola.id,
            "nome": "2º B",
            "turno": Turma.Turno.MATUTINO,
            "ano_letivo": 2026,
        }
        resp = self._request(TurmaViewSet, "create", "professor", payload)
        self.assertEqual(resp.status_code, 403)


class DisciplinaPermissionTests(_PermissionSetup):
    """Disciplina: mesmo padrão de Turma."""

    def test_list_professor_aceito(self):
        self.assertEqual(
            self._request(DisciplinaViewSet, "list", "professor").status_code, 200
        )

    def test_create_professor_negado(self):
        payload = {"escola": self.escola.id, "nome": "Matemática"}
        self.assertEqual(
            self._request(DisciplinaViewSet, "create", "professor", payload).status_code,
            403,
        )

    def test_create_diretor_aceito(self):
        payload = {"escola": self.escola.id, "nome": "Matemática"}
        self.assertEqual(
            self._request(DisciplinaViewSet, "create", "diretor", payload).status_code,
            201,
        )


class AlunoPermissionAndFilterTests(_PermissionSetup):
    """Aluno: leitura ampla, escrita restrita; filtro por turma e search."""

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
                escola=cls.escola,
                matricula=f"A{i}",
                nome_completo=f"João {i}",
                turma=cls.turma,
            )
            for i in range(3)
        ]
        cls.alunos_outra = [
            Aluno.objects.create(
                escola=cls.escola,
                matricula=f"B{i}",
                nome_completo=f"Maria {i}",
                turma=cls.outra_turma,
            )
            for i in range(2)
        ]

    def test_list_professor_aceito(self):
        resp = self._request(AlunoViewSet, "list", "professor")
        self.assertEqual(resp.status_code, 200)
        # 3 + 2 = 5 alunos no total
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
        resp = self._request(AlunoViewSet, "create", "diretor", payload)
        self.assertEqual(resp.status_code, 201)

    def test_create_professor_negado(self):
        payload = {
            "escola": self.escola.id,
            "matricula": "C002",
            "nome_completo": "Aluno X",
            "turma": self.turma.id,
        }
        resp = self._request(AlunoViewSet, "create", "professor", payload)
        self.assertEqual(resp.status_code, 403)

    def test_create_falha_quando_turma_de_outra_escola(self):
        outra_escola = Escola.objects.create(nome="Outra")
        outra_turma = Turma.objects.create(
            escola=outra_escola,
            nome="1º A",
            turno=Turma.Turno.MATUTINO,
            ano_letivo=2026,
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
