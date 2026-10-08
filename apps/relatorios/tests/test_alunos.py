"""Testes do relatório cadastral (`/alunos/relatorio/`).

O ponto sensível aqui é a permissão: ela não é declarada na action, vem
do `ReadWritePermissionMixin` por a action não ser `list`/`retrieve`.
Como é consequência de um mixin e não de uma linha local, os dois lados
estão fixados em teste.
"""
from datetime import date
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import Usuario
from apps.escola.models import Aluno, Escola, Turma


class RelatorioAlunosTests(TestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        cls.escola = Escola.objects.create(nome="Escola")
        cls.outra_escola = Escola.objects.create(nome="Outra")
        cls.turma_a = Turma.objects.create(
            escola=cls.escola,
            nome="1º A",
            turno=Turma.Turno.MATUTINO,
            ano_letivo=2026,
        )
        cls.turma_b = Turma.objects.create(
            escola=cls.escola,
            nome="1º B",
            turno=Turma.Turno.VESPERTINO,
            ano_letivo=2026,
        )
        cls.turma_alheia = Turma.objects.create(
            escola=cls.outra_escola,
            nome="Turma Secreta",
            turno=Turma.Turno.MATUTINO,
            ano_letivo=2026,
        )
        cls.ana = Aluno.objects.create(
            escola=cls.escola,
            matricula="A1",
            nome_completo="Ana",
            turma=cls.turma_a,
            data_nascimento=date(2012, 5, 3),
            nome_responsavel="Marta",
            email_responsavel="marta@example.com",
        )
        cls.bruno = Aluno.objects.create(
            escola=cls.escola,
            matricula="B1",
            nome_completo="Bruno",
            turma=cls.turma_b,
        )
        cls.inativo = Aluno.objects.create(
            escola=cls.escola,
            matricula="A2",
            nome_completo="Carla",
            turma=cls.turma_a,
            ativo=False,
        )
        Aluno.objects.create(
            escola=cls.outra_escola,
            matricula="Z9",
            nome_completo="Aluno de Fora",
            turma=cls.turma_alheia,
        )

        cls.diretor = Usuario.objects.create_user(
            username="dir",
            password="x",
            perfil=Usuario.Perfil.DIRETOR,
            escola=cls.escola,
        )
        cls.secretaria = Usuario.objects.create_user(
            username="sec",
            password="x",
            perfil=Usuario.Perfil.SECRETARIA,
            escola=cls.escola,
        )
        cls.professor = Usuario.objects.create_user(
            username="prof",
            password="x",
            perfil=Usuario.Perfil.PROFESSOR,
            escola=cls.escola,
        )

    def setUp(self) -> None:
        self.client = APIClient()

    def _auth(self, user) -> None:
        token = RefreshToken.for_user(user).access_token
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    @property
    def url(self) -> str:
        return reverse("api_v1:aluno-relatorio")

    def _csv(self, **params) -> list[str]:
        resp = self.client.get(self.url, {"formato": "csv", **params})
        self.assertEqual(resp.status_code, 200)
        return resp.content.decode("utf-8").strip().splitlines()

    def test_sem_token_401(self):
        self.assertEqual(self.client.get(self.url).status_code, 401)

    def test_professor_nao_baixa(self):
        """A planilha leva nome e email de responsável."""
        self._auth(self.professor)
        resp = self.client.get(self.url, {"formato": "csv"})
        self.assertEqual(resp.status_code, 403)

    def test_direcao_baixa(self):
        """Diretor e secretaria (alias) passam."""
        for user in (self.diretor, self.secretaria):
            self._auth(user)
            resp = self.client.get(self.url, {"formato": "csv"})
            self.assertEqual(resp.status_code, 200, user.username)

    def test_escopo_de_escola(self):
        self._auth(self.diretor)
        corpo = "\n".join(self._csv())
        self.assertIn("Ana", corpo)
        self.assertNotIn("Aluno de Fora", corpo)

    def test_colunas_trazem_nome_da_turma_e_responsavel(self):
        self._auth(self.diretor)
        linhas = self._csv(turma=self.turma_a.id)
        self.assertIn("email_responsavel", linhas[0])
        corpo = "\n".join(linhas[1:])
        self.assertIn("1º A", corpo)
        self.assertIn("marta@example.com", corpo)
        self.assertIn("2012-05-03", corpo)

    def test_data_de_nascimento_vazia_sai_em_branco(self):
        """A secretaria imprime isso pra alguém preencher à mão."""
        self._auth(self.diretor)
        linhas = self._csv(turma=self.turma_b.id)
        self.assertEqual(len(linhas), 2)
        self.assertNotIn("None", linhas[1])

    def test_filtro_de_ativo_vale_como_na_tela(self):
        self._auth(self.diretor)
        ativos = "\n".join(self._csv(ativo="true"))
        self.assertIn("Ana", ativos)
        self.assertNotIn("Carla", ativos)

        inativos = "\n".join(self._csv(ativo="false"))
        self.assertIn("Carla", inativos)
        self.assertNotIn("Ana", inativos)

    def test_formato_invalido_e_json_recusados(self):
        self._auth(self.diretor)
        for formato in ("docx", "json"):
            resp = self.client.get(self.url, {"formato": formato})
            self.assertEqual(resp.status_code, 400, formato)

    def test_xlsx_sai_como_planilha(self):
        self._auth(self.diretor)
        resp = self.client.get(self.url, {"formato": "xlsx"})
        self.assertEqual(resp.status_code, 200)
        self.assertIn("spreadsheetml", resp["Content-Type"])
        self.assertIn("alunos.xlsx", resp["Content-Disposition"])

    @patch("apps.escola.views._render_pdf", return_value=b"%PDF-1.4 fake")
    def test_pdf_separa_por_turma(self, render_mock):
        self._auth(self.diretor)
        resp = self.client.get(self.url, {"formato": "pdf"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp["Content-Type"], "application/pdf")

        html = render_mock.call_args[0][0]
        self.assertIn("1º A", html)
        self.assertIn("1º B", html)
        self.assertIn("Relatório de Alunos", html)
        # Inativo entra marcado quando o recorte não filtra por ativo.
        self.assertIn("[ inativo ]", html)
        # Sintaxe de template que sobra vira texto visível no PDF.
        self.assertNotIn("{#", html)
        self.assertNotIn("{%", html)

    @patch("apps.escola.views._render_pdf", return_value=b"%PDF")
    def test_pdf_nao_vaza_turma_de_outra_escola_no_cabecalho(self, render_mock):
        self._auth(self.diretor)
        resp = self.client.get(
            self.url, {"formato": "pdf", "turma": self.turma_alheia.id}
        )
        self.assertEqual(resp.status_code, 200)
        html = render_mock.call_args[0][0]
        self.assertNotIn("Turma Secreta", html)
        self.assertIn("Nenhum aluno no recorte", html)

    @patch("apps.escola.views.LIMITE_PDF_ALUNOS", 1)
    def test_pdf_recusa_recorte_grande_e_aponta_a_saida(self):
        self._auth(self.diretor)
        resp = self.client.get(self.url, {"formato": "pdf"})
        self.assertEqual(resp.status_code, 400)
        self.assertIn("CSV/XLSX", str(resp.data))
        # O mesmo recorte sai sem reclamação em planilha.
        self.assertEqual(len(self._csv()), 4)

    def test_export_de_migracao_segue_fechado_pra_direcao(self):
        """O `export/` do mixin continua sendo serviço admin-only.

        O cadastral existir pra direção não pode ter afrouxado o outro.
        """
        self._auth(self.diretor)
        resp = self.client.get(
            reverse("api_v1:aluno-export"), {"formato": "csv"}
        )
        self.assertEqual(resp.status_code, 403)
