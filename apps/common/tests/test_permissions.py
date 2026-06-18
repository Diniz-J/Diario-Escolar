"""Testes das classes de permissão definidas em apps.common.permissions.

Cobrem a matriz completa de (tipo de usuário) x (classe de permissão), além de
um teste de consistência que falha caso alguém renomeie valores do enum
`Usuario.Perfil` sem atualizar as constantes em `permissions.py`.
"""
from django.contrib.auth.models import AnonymousUser
from django.test import TestCase
from rest_framework.test import APIRequestFactory

from apps.accounts.models import Usuario
from apps.common import permissions
from apps.common.permissions import (
    IsAdmin,
    IsAdminOrDiretor,
    IsAdminOrDiretorOrProfessor,
)


class _PermissionMatrixTests(TestCase):
    """Helpers compartilhados — não roda direto (nome com underscore)."""

    @classmethod
    def setUpTestData(cls) -> None:
        cls.factory = APIRequestFactory()
        cls.superuser = Usuario.objects.create_superuser(
            username="su", password="x", email="su@t.test"
        )
        cls.admin = Usuario.objects.create_user(
            username="adm", password="x", perfil=Usuario.Perfil.ADMIN
        )
        cls.diretor = Usuario.objects.create_user(
            username="dir", password="x", perfil=Usuario.Perfil.DIRETOR
        )
        cls.professor = Usuario.objects.create_user(
            username="prof", password="x", perfil=Usuario.Perfil.PROFESSOR
        )
        cls.secretaria = Usuario.objects.create_user(
            username="sec", password="x", perfil=Usuario.Perfil.SECRETARIA
        )
        cls.coordenador = Usuario.objects.create_user(
            username="coord", password="x", perfil=Usuario.Perfil.COORDENADOR
        )
        cls.inspetor = Usuario.objects.create_user(
            username="ins", password="x", perfil=Usuario.Perfil.INSPETOR
        )
        cls.anon = AnonymousUser()

    def _check(self, permission_class, user) -> bool:
        request = self.factory.get("/")
        request.user = user
        return permission_class().has_permission(request, view=None)


class IsAdminTests(_PermissionMatrixTests):
    def test_anon_negado(self):
        self.assertFalse(self._check(IsAdmin, self.anon))

    def test_superuser_aceito(self):
        self.assertTrue(self._check(IsAdmin, self.superuser))

    def test_admin_aceito(self):
        self.assertTrue(self._check(IsAdmin, self.admin))

    def test_diretor_negado(self):
        self.assertFalse(self._check(IsAdmin, self.diretor))

    def test_professor_negado(self):
        self.assertFalse(self._check(IsAdmin, self.professor))

    def test_secretaria_negado(self):
        self.assertFalse(self._check(IsAdmin, self.secretaria))

    def test_coordenador_negado(self):
        self.assertFalse(self._check(IsAdmin, self.coordenador))

    def test_inspetor_negado(self):
        self.assertFalse(self._check(IsAdmin, self.inspetor))


class IsAdminOrDiretorTests(_PermissionMatrixTests):
    def test_anon_negado(self):
        self.assertFalse(self._check(IsAdminOrDiretor, self.anon))

    def test_superuser_aceito(self):
        self.assertTrue(self._check(IsAdminOrDiretor, self.superuser))

    def test_admin_aceito(self):
        self.assertTrue(self._check(IsAdminOrDiretor, self.admin))

    def test_diretor_aceito(self):
        self.assertTrue(self._check(IsAdminOrDiretor, self.diretor))

    def test_professor_negado(self):
        self.assertFalse(self._check(IsAdminOrDiretor, self.professor))

    def test_secretaria_aceito(self):
        """Alias de diretor — passa em IsAdminOrDiretor."""
        self.assertTrue(self._check(IsAdminOrDiretor, self.secretaria))

    def test_coordenador_aceito(self):
        """Alias de diretor — passa em IsAdminOrDiretor."""
        self.assertTrue(self._check(IsAdminOrDiretor, self.coordenador))

    def test_inspetor_negado(self):
        """Inspetor não tem cadastro — fica fora de IsAdminOrDiretor."""
        self.assertFalse(self._check(IsAdminOrDiretor, self.inspetor))


class IsAdminOrDiretorOrProfessorTests(_PermissionMatrixTests):
    def test_anon_negado(self):
        self.assertFalse(self._check(IsAdminOrDiretorOrProfessor, self.anon))

    def test_superuser_aceito(self):
        self.assertTrue(self._check(IsAdminOrDiretorOrProfessor, self.superuser))

    def test_admin_aceito(self):
        self.assertTrue(self._check(IsAdminOrDiretorOrProfessor, self.admin))

    def test_diretor_aceito(self):
        self.assertTrue(self._check(IsAdminOrDiretorOrProfessor, self.diretor))

    def test_professor_aceito(self):
        self.assertTrue(self._check(IsAdminOrDiretorOrProfessor, self.professor))

    def test_secretaria_aceito(self):
        """Alias de diretor."""
        self.assertTrue(self._check(IsAdminOrDiretorOrProfessor, self.secretaria))

    def test_coordenador_aceito(self):
        """Alias de diretor."""
        self.assertTrue(
            self._check(IsAdminOrDiretorOrProfessor, self.coordenador)
        )

    def test_inspetor_aceito(self):
        """Alias de professor."""
        self.assertTrue(self._check(IsAdminOrDiretorOrProfessor, self.inspetor))


class PerfilConstantsConsistencyTests(TestCase):
    """Garante que as constantes hardcoded em permissions correspondem ao enum
    `Usuario.Perfil`. Falha se alguém renomear um valor do enum sem atualizar
    o módulo de permissões — evita a falha silenciosa apontada na revisão."""

    def test_constantes_existem_no_enum(self):
        valores_enum = set(Usuario.Perfil.values)
        self.assertIn(permissions._PERFIL_ADMIN, valores_enum)
        self.assertIn(permissions._PERFIL_DIRETOR, valores_enum)
        self.assertIn(permissions._PERFIL_SECRETARIA, valores_enum)
        self.assertIn(permissions._PERFIL_COORDENADOR, valores_enum)
        self.assertIn(permissions._PERFIL_PROFESSOR, valores_enum)
        self.assertIn(permissions._PERFIL_INSPETOR, valores_enum)

    def test_admin_bypass_corresponde_ao_enum(self):
        """A constante de bypass deve ser exatamente Usuario.Perfil.ADMIN."""
        self.assertEqual(permissions._PERFIL_ADMIN, Usuario.Perfil.ADMIN.value)
