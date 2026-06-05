"""Smoke tests dos endpoints /api/v1/boletins/aluno/{id}/."""
from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import Usuario
from apps.avaliacao.models import (
    Avaliacao,
    NotaAvaliacao,
    PeriodoAvaliativo,
)
from apps.escola.models import Aluno, Disciplina, Escola, Turma


class BoletimEndpointTests(TestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        cls.escola = Escola.objects.create(nome="Escola")
        cls.outra_escola = Escola.objects.create(nome="Outra")
        cls.turma = Turma.objects.create(
            escola=cls.escola, nome="1º A",
            turno=Turma.Turno.MATUTINO, ano_letivo=2026,
        )
        cls.outra_turma = Turma.objects.create(
            escola=cls.outra_escola, nome="1º A",
            turno=Turma.Turno.MATUTINO, ano_letivo=2026,
        )
        cls.aluno = Aluno.objects.create(
            escola=cls.escola, matricula="A1",
            nome_completo="Aluno Um", turma=cls.turma,
        )
        cls.aluno_outra_escola = Aluno.objects.create(
            escola=cls.outra_escola, matricula="B1",
            nome_completo="Aluno B", turma=cls.outra_turma,
        )
        cls.diretor = Usuario.objects.create_user(
            username="dir", password="x",
            perfil=Usuario.Perfil.DIRETOR, escola=cls.escola,
        )
        cls.secretaria = Usuario.objects.create_user(
            username="sec", password="x",
            perfil=Usuario.Perfil.SECRETARIA, escola=cls.escola,
        )
        cls.admin = Usuario.objects.create_user(
            username="adm", password="x", perfil=Usuario.Perfil.ADMIN
        )

    def setUp(self) -> None:
        self.client = APIClient()

    def _auth(self, user) -> None:
        token = RefreshToken.for_user(user).access_token
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def _url(self, aluno_id):
        return reverse("api_v1:boletim-aluno", kwargs={"aluno_id": aluno_id})

    def test_sem_token_401(self):
        resp = self.client.get(self._url(self.aluno.id))
        self.assertEqual(resp.status_code, 401)

    def test_secretaria_acessa_como_diretor(self):
        """Alias de diretor — acessa aluno da própria escola."""
        self._auth(self.secretaria)
        resp = self.client.get(self._url(self.aluno.id))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["aluno"]["id"], self.aluno.id)

    def test_diretor_acessa_aluno_da_propria_escola(self):
        self._auth(self.diretor)
        resp = self.client.get(self._url(self.aluno.id))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["aluno"]["id"], self.aluno.id)

    def test_diretor_nao_acessa_aluno_de_outra_escola(self):
        self._auth(self.diretor)
        resp = self.client.get(self._url(self.aluno_outra_escola.id))
        self.assertEqual(resp.status_code, 403)

    def test_admin_acessa_qualquer_aluno(self):
        self._auth(self.admin)
        resp = self.client.get(self._url(self.aluno_outra_escola.id))
        self.assertEqual(resp.status_code, 200)

    def test_aluno_inexistente_404(self):
        self._auth(self.admin)
        resp = self.client.get(self._url(999999))
        self.assertEqual(resp.status_code, 404)

    def test_data_inicio_invalida_400(self):
        self._auth(self.diretor)
        resp = self.client.get(
            self._url(self.aluno.id) + "?data_inicio=banana"
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("data_inicio", resp.data)


class BoletimPDFEndpointTests(TestCase):
    """Endpoint `/pdf/` — testa o pipeline sem renderizar PDF real.

    WeasyPrint só funciona no container Linux (libs do sistema), então
    aqui mockamos a chamada do WeasyPrint. O importante é validar que
    o template renderiza com o contexto certo e que o response carrega
    o content-type e o Content-Disposition esperados.
    """

    @classmethod
    def setUpTestData(cls) -> None:
        cls.escola = Escola.objects.create(nome="Escola")
        cls.turma = Turma.objects.create(
            escola=cls.escola, nome="1º A",
            turno=Turma.Turno.MATUTINO, ano_letivo=2026,
        )
        cls.aluno = Aluno.objects.create(
            escola=cls.escola, matricula="A1",
            nome_completo="Aluno Um", turma=cls.turma,
        )
        cls.periodo = PeriodoAvaliativo.objects.create(
            escola=cls.escola, nome="1º Bim", ordem=1, ano_letivo=2026,
            data_inicio=date(2026, 2, 1), data_fim=date(2026, 4, 30),
        )
        cls.admin = Usuario.objects.create_user(
            username="adm", password="x", perfil=Usuario.Perfil.ADMIN,
        )

    def setUp(self) -> None:
        self.client = APIClient()
        token = RefreshToken.for_user(self.admin).access_token
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def _url(self, aluno_id, query=""):
        base = reverse(
            "api_v1:boletim-aluno-pdf", kwargs={"aluno_id": aluno_id}
        )
        return f"{base}?{query}" if query else base

    @patch("apps.boletins.views._render_pdf")
    def test_pdf_endpoint_retorna_attachment(self, mock_render):
        # Mock do WeasyPrint via helper module-level pra não depender
        # da lib no host de teste (Windows sem GTK runtime).
        mock_render.return_value = b"%PDF-fake"
        resp = self.client.get(self._url(self.aluno.id))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp["Content-Type"], "application/pdf")
        self.assertIn("attachment", resp["Content-Disposition"])
        self.assertIn("A1", resp["Content-Disposition"])
        self.assertIn("_anual", resp["Content-Disposition"])
        mock_render.assert_called_once()

    @patch("apps.boletins.views._render_pdf")
    def test_pdf_endpoint_com_periodo(self, mock_render):
        mock_render.return_value = b"%PDF-fake"
        resp = self.client.get(
            self._url(self.aluno.id, f"periodo={self.periodo.id}")
        )
        self.assertEqual(resp.status_code, 200)
        # Nome do arquivo contém o nome do período.
        self.assertIn("1", resp["Content-Disposition"])
        self.assertIn("bim", resp["Content-Disposition"].lower())


class BoletimAvaliacoesEndpointTests(TestCase):
    """Endpoint `/avaliacoes/` — export CSV/XLSX plano do aluno."""

    @classmethod
    def setUpTestData(cls) -> None:
        cls.escola = Escola.objects.create(nome="Escola")
        cls.turma = Turma.objects.create(
            escola=cls.escola, nome="1º A",
            turno=Turma.Turno.MATUTINO, ano_letivo=2026,
        )
        cls.disciplina = Disciplina.objects.create(
            escola=cls.escola, nome="Matemática",
        )
        cls.aluno = Aluno.objects.create(
            escola=cls.escola, matricula="A1",
            nome_completo="Aluno Um", turma=cls.turma,
        )
        cls.avaliacao = Avaliacao.objects.create(
            escola=cls.escola, turma=cls.turma, disciplina=cls.disciplina,
            titulo="Prova 1", data=date(2026, 3, 15),
            nota_maxima=Decimal("10"), peso=Decimal("1"),
        )
        NotaAvaliacao.objects.create(
            escola=cls.escola, avaliacao=cls.avaliacao,
            aluno=cls.aluno, nota=Decimal("8.50"),
        )
        cls.admin = Usuario.objects.create_user(
            username="adm", password="x", perfil=Usuario.Perfil.ADMIN,
        )

    def setUp(self) -> None:
        self.client = APIClient()
        token = RefreshToken.for_user(self.admin).access_token
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def _url(self, aluno_id, query=""):
        base = reverse(
            "api_v1:boletim-aluno-avaliacoes",
            kwargs={"aluno_id": aluno_id},
        )
        return f"{base}?{query}" if query else base

    def test_csv_default_retorna_arquivo_com_headers_certos(self):
        resp = self.client.get(self._url(self.aluno.id))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp["Content-Type"], "text/csv")
        self.assertIn("attachment", resp["Content-Disposition"])
        conteudo = resp.content.decode("utf-8")
        # Headers do CSV em ordem fixa.
        primeira = conteudo.splitlines()[0]
        for col in (
            "disciplina",
            "periodo",
            "data",
            "tipo",
            "titulo",
            "nota_maxima",
            "nota_obtida",
            "peso",
        ):
            self.assertIn(col, primeira)
        # Linha do dado: Matemática + 8.50.
        self.assertIn("Matem", conteudo)
        self.assertIn("8.50", conteudo)

    def test_xlsx_retorna_binario(self):
        resp = self.client.get(
            self._url(self.aluno.id, "formato=xlsx")
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn(
            "spreadsheetml.sheet",
            resp["Content-Type"],
        )
        # Sanity: XLSX sempre começa com 'PK' (zip header).
        self.assertEqual(resp.content[:2], b"PK")

    def test_formato_invalido_400(self):
        resp = self.client.get(
            self._url(self.aluno.id, "formato=pdf")
        )
        self.assertEqual(resp.status_code, 400)
