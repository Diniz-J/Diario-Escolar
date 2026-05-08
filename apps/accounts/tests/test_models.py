"""Testes do modelo Usuario — vínculo opcional com Escola."""
from django.test import TestCase

from apps.accounts.models import Usuario
from apps.escola.models import Escola


class UsuarioEscolaTests(TestCase):
    def test_usuario_pode_existir_sem_escola(self):
        """Cenário do superusuário inicial / contas globais."""
        u = Usuario.objects.create_user(username="su", password="x")
        self.assertIsNone(u.escola)

    def test_usuario_pode_ter_escola_vinculada(self):
        escola = Escola.objects.create(nome="Escola X")
        u = Usuario.objects.create_user(
            username="prof", password="x", perfil=Usuario.Perfil.PROFESSOR, escola=escola
        )
        self.assertEqual(u.escola_id, escola.id)
        # related_name="usuarios" funcional
        self.assertIn(u, escola.usuarios.all())
