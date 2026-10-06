"""Testes do mural de materiais no lado do staff (fatia 5 do `PORTAL.md`).

Verificação da fatia: professor não publica em turma que não leciona. Mais:
não publica em nome de outro, não vê o material alheio, outra escola dá 404,
link só http/https e excluir desativa.
"""
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.models import Usuario
from apps.escola.models import Disciplina, Escola, Lecionamento, Professor, Turma
from apps.materiais.models import Material

URL_LISTA = reverse("api_v1:material-list")


def url_item(pk) -> str:
    return reverse("api_v1:material-detail", args=[pk])


class _MateriaisSetup(TestCase):
    """Helpers sem testes, pra subclasse não herdar teste do pai."""

    @classmethod
    def setUpTestData(cls) -> None:
        cls.escola = Escola.objects.create(nome="Escola A")
        cls.outra_escola = Escola.objects.create(nome="Escola B")
        cls.turma1 = cls._turma(cls.escola, "1º A")
        cls.turma2 = cls._turma(cls.escola, "2º A")
        cls.matematica = Disciplina.objects.create(escola=cls.escola, nome="Matemática")
        cls.portugues = Disciplina.objects.create(escola=cls.escola, nome="Português")

        cls.prof1 = cls._professor("prof1", cls.escola)
        cls.prof2 = cls._professor("prof2", cls.escola)
        cls._lecionar(cls.prof1, cls.turma1, cls.matematica)
        cls._lecionar(cls.prof2, cls.turma2, cls.portugues)

        cls.diretora = Usuario.objects.create_user(
            username="diretora", password="x", perfil=Usuario.Perfil.DIRETOR,
            escola=cls.escola,
        )

        cls.turma_b = cls._turma(cls.outra_escola, "1º A")
        cls.disciplina_b = Disciplina.objects.create(escola=cls.outra_escola, nome="Matemática")
        cls.prof_b = cls._professor("prof_b", cls.outra_escola)
        cls._lecionar(cls.prof_b, cls.turma_b, cls.disciplina_b)

        cls.material_prof2 = Material.objects.create(
            escola=cls.escola, turma=cls.turma2, disciplina=cls.portugues,
            professor=cls.prof2, titulo="Lista do prof2",
        )
        cls.material_b = Material.objects.create(
            escola=cls.outra_escola, turma=cls.turma_b, disciplina=cls.disciplina_b,
            professor=cls.prof_b, titulo="Material da escola B",
        )

    @staticmethod
    def _turma(escola, nome):
        return Turma.objects.create(
            escola=escola, nome=nome, turno=Turma.Turno.MATUTINO, ano_letivo=2026
        )

    @staticmethod
    def _professor(username, escola):
        usuario = Usuario.objects.create_user(
            username=username, password="x", perfil=Usuario.Perfil.PROFESSOR,
            escola=escola, first_name=username.capitalize(),
        )
        return Professor.objects.create(usuario=usuario, escola=escola)

    @staticmethod
    def _lecionar(professor, turma, disciplina):
        return Lecionamento.objects.create(
            escola=turma.escola, professor=professor, turma=turma, disciplina=disciplina
        )

    def setUp(self) -> None:
        self.client = APIClient()

    def _como(self, usuario):
        self.client.force_authenticate(user=usuario)

    def _payload(self, **extra):
        dados = {
            "turma": self.turma1.pk,
            "disciplina": self.matematica.pk,
            "professor": self.prof1.pk,
            "titulo": "Lista de exercícios",
            "link": "https://example.com/lista.pdf",
        }
        dados.update(extra)
        return dados

    def _publicar(self, **extra):
        return self.client.post(URL_LISTA, self._payload(**extra), format="json")


class PublicarTests(_MateriaisSetup):
    def test_professor_publica_na_turma_que_leciona(self):
        self._como(self.prof1.usuario)
        resp = self._publicar()
        self.assertEqual(resp.status_code, 201, resp.data)
        material = Material.objects.get(pk=resp.data["id"])
        self.assertEqual(material.escola, self.escola)
        self.assertEqual(resp.data["professor_nome"], "Prof1")

    def test_professor_nao_publica_em_turma_que_nao_leciona(self):
        self._como(self.prof1.usuario)
        resp = self._publicar(turma=self.turma2.pk)
        self.assertEqual(resp.status_code, 400)
        self.assertIn("professor", resp.data)

    def test_professor_nao_publica_em_nome_de_outro(self):
        self._como(self.prof1.usuario)
        resp = self._publicar(
            turma=self.turma2.pk, disciplina=self.portugues.pk, professor=self.prof2.pk
        )
        self.assertEqual(resp.status_code, 403)

    def test_direcao_publica_escolhendo_o_professor(self):
        self._como(self.diretora)
        resp = self._publicar(
            turma=self.turma2.pk, disciplina=self.portugues.pk, professor=self.prof2.pk
        )
        self.assertEqual(resp.status_code, 201, resp.data)

    def test_direcao_tambem_exige_lecionamento(self):
        self._como(self.diretora)
        self.assertEqual(self._publicar(professor=self.prof2.pk).status_code, 400)

    def test_turma_de_outra_escola_e_recusada(self):
        self._como(self.prof1.usuario)
        resp = self._publicar(turma=self.turma_b.pk)
        self.assertEqual(resp.status_code, 400)

    def test_link_so_http_ou_https(self):
        self._como(self.prof1.usuario)
        for link in ("javascript:alert(1)", "ftp://example.com/x", "data:text/html,oi"):
            with self.subTest(link):
                self.assertEqual(self._publicar(link=link).status_code, 400)
        self.assertEqual(self._publicar(link="").status_code, 201)

    def test_professor_nao_move_o_proprio_material_pra_outro(self):
        self._como(self.prof1.usuario)
        pk = self._publicar().data["id"]
        resp = self.client.patch(
            url_item(pk),
            {"turma": self.turma2.pk, "disciplina": self.portugues.pk, "professor": self.prof2.pk},
            format="json",
        )
        self.assertEqual(resp.status_code, 403)


class EscopoTests(_MateriaisSetup):
    def test_professor_so_ve_os_proprios(self):
        self._como(self.prof1.usuario)
        self._publicar()
        titulos = [m["titulo"] for m in self.client.get(URL_LISTA).data]
        self.assertEqual(titulos, ["Lista de exercícios"])

    def test_material_de_outro_professor_da_404(self):
        self._como(self.prof1.usuario)
        self.assertEqual(self.client.get(url_item(self.material_prof2.pk)).status_code, 404)
        resp = self.client.patch(url_item(self.material_prof2.pk), {"titulo": "x"}, format="json")
        self.assertEqual(resp.status_code, 404)

    def test_direcao_ve_a_escola_toda_e_nao_a_outra(self):
        self._como(self.diretora)
        ids = {m["id"] for m in self.client.get(URL_LISTA).data}
        self.assertIn(self.material_prof2.pk, ids)
        self.assertNotIn(self.material_b.pk, ids)
        self.assertEqual(self.client.get(url_item(self.material_b.pk)).status_code, 404)


class ExcluirTests(_MateriaisSetup):
    def test_excluir_desativa_em_vez_de_apagar(self):
        self._como(self.prof2.usuario)
        resp = self.client.delete(url_item(self.material_prof2.pk))
        self.assertEqual(resp.status_code, 204)
        self.material_prof2.refresh_from_db()
        self.assertFalse(self.material_prof2.ativo)


class CleanTests(_MateriaisSetup):
    def test_clean_exige_lecionamento(self):
        """O `clean()` cobre admin e shell, que não passam pelo serializer."""
        material = Material(
            escola=self.escola, turma=self.turma2, disciplina=self.matematica,
            professor=self.prof1, titulo="Sem lecionamento",
        )
        with self.assertRaises(ValidationError) as ctx:
            material.full_clean()
        self.assertIn("professor", ctx.exception.message_dict)

    def test_clean_recusa_link_inseguro(self):
        material = Material(
            escola=self.escola, turma=self.turma1, disciplina=self.matematica,
            professor=self.prof1, titulo="Link ruim", link="javascript:alert(1)",
        )
        with self.assertRaises(ValidationError) as ctx:
            material.full_clean()
        self.assertIn("link", ctx.exception.message_dict)
