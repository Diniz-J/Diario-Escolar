"""Testes da exportação de ocorrências (`/ocorrencias/exportar/`).

A action mora no `OcorrenciaViewSet` justamente pra herdar o filtro e o
escopo da listagem; os testes abaixo checam que essa herança vale na
prática — o arquivo e a tela não podem divergir.
"""
from datetime import date
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import Usuario
from apps.escola.models import Aluno, Escola, Professor, Turma
from apps.ocorrencias.models import Ocorrencia


class ExportarOcorrenciasTests(TestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        cls.escola = Escola.objects.create(nome="Escola")
        cls.outra_escola = Escola.objects.create(nome="Outra")
        cls.turma = Turma.objects.create(
            escola=cls.escola,
            nome="3º C",
            turno=Turma.Turno.MATUTINO,
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
            matricula="M1",
            nome_completo="Ana",
            turma=cls.turma,
        )
        cls.bruno = Aluno.objects.create(
            escola=cls.escola,
            matricula="M2",
            nome_completo="Bruno",
            turma=cls.turma,
        )
        cls.aluno_alheio = Aluno.objects.create(
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
        usuario_professor = Usuario.objects.create_user(
            username="prof",
            password="x",
            first_name="Marta",
            last_name="Lima",
            perfil=Usuario.Perfil.PROFESSOR,
            escola=cls.escola,
        )
        cls.professor = Professor.objects.create(
            escola=cls.escola, usuario=usuario_professor
        )

        # Duas da Ana (uma aberta e uma resolvida) e uma do Bruno.
        cls.aberta = Ocorrencia.objects.create(
            escola=cls.escola,
            turma=cls.turma,
            aluno=cls.ana,
            professor=cls.professor,
            descricao="Conversa durante a prova.",
            data_ocorrencia=date(2026, 3, 10),
            status=Ocorrencia.Status.ABERTA,
        )
        cls.resolvida = Ocorrencia.objects.create(
            escola=cls.escola,
            turma=cls.turma,
            aluno=cls.ana,
            descricao="Atraso reiterado.",
            data_ocorrencia=date(2026, 4, 1),
            status=Ocorrencia.Status.RESOLVIDA,
        )
        cls.do_bruno = Ocorrencia.objects.create(
            escola=cls.escola,
            turma=cls.turma,
            aluno=cls.bruno,
            descricao="Saiu sem autorização.",
            data_ocorrencia=date(2026, 3, 20),
            status=Ocorrencia.Status.ABERTA,
        )
        cls.alheia = Ocorrencia.objects.create(
            escola=cls.outra_escola,
            turma=cls.turma_alheia,
            aluno=cls.aluno_alheio,
            descricao="Nada que seja da sua conta.",
            data_ocorrencia=date(2026, 3, 15),
            status=Ocorrencia.Status.ABERTA,
        )

    def setUp(self) -> None:
        self.client = APIClient()

    def _auth(self, user) -> None:
        token = RefreshToken.for_user(user).access_token
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    @property
    def url(self) -> str:
        return reverse("api_v1:ocorrencia-exportar")

    def _csv(self, **params) -> list[str]:
        resp = self.client.get(self.url, {"formato": "csv", **params})
        self.assertEqual(resp.status_code, 200)
        return resp.content.decode("utf-8").strip().splitlines()

    def test_sem_token_401(self):
        self.assertEqual(self.client.get(self.url).status_code, 401)

    def test_formato_invalido_e_json_recusados(self):
        """`json` não entra: pra isso existe a própria listagem."""
        self._auth(self.diretor)
        for formato in ("docx", "json"):
            resp = self.client.get(self.url, {"formato": formato})
            self.assertEqual(resp.status_code, 400, formato)
            self.assertIn("formato", resp.data)

    def test_escopo_de_escola(self):
        """Ocorrência de outra escola não entra no arquivo."""
        self._auth(self.diretor)
        corpo = "\n".join(self._csv())
        self.assertIn("Ana", corpo)
        self.assertNotIn("Aluno de Fora", corpo)
        self.assertNotIn("Nada que seja da sua conta", corpo)

    def test_mesmo_recorte_da_listagem(self):
        """O arquivo e a tela têm que mostrar o mesmo conjunto."""
        self._auth(self.diretor)
        filtros = {
            "status": Ocorrencia.Status.ABERTA,
            "data_inicio": "2026-03-01",
            "data_fim": "2026-03-31",
        }
        listagem = self.client.get(
            reverse("api_v1:ocorrencia-list"),
            {**filtros, "page_size": "all"},
        )
        self.assertEqual(listagem.status_code, 200)
        ids_da_tela = {item["id"] for item in listagem.data}

        linhas = self._csv(**filtros)
        # Cabeçalho + uma linha por ocorrência.
        self.assertEqual(len(linhas) - 1, len(ids_da_tela))
        self.assertEqual(ids_da_tela, {self.aberta.id, self.do_bruno.id})
        corpo = "\n".join(linhas)
        self.assertIn("Conversa durante a prova.", corpo)
        self.assertNotIn("Atraso reiterado.", corpo)

    def test_colunas_trazem_nome_e_nao_id(self):
        """A planilha é lida fora do sistema, onde `turma=7` não diz nada."""
        self._auth(self.diretor)
        linhas = self._csv(aluno=self.ana.id)
        self.assertIn("matricula", linhas[0])
        corpo = "\n".join(linhas[1:])
        self.assertIn("3º C", corpo)
        self.assertIn("Ana", corpo)
        self.assertIn("Marta Lima", corpo)

    def test_ocorrencia_sem_professor_nao_quebra(self):
        """`professor` é opcional no modelo: a coluna sai vazia."""
        self._auth(self.diretor)
        linhas = self._csv(status=Ocorrencia.Status.RESOLVIDA)
        self.assertEqual(len(linhas), 2)
        self.assertIn("Atraso reiterado.", linhas[1])

    def test_xlsx_sai_como_planilha(self):
        self._auth(self.diretor)
        resp = self.client.get(self.url, {"formato": "xlsx"})
        self.assertEqual(resp.status_code, 200)
        self.assertIn("spreadsheetml", resp["Content-Type"])
        self.assertIn("ocorrencias.xlsx", resp["Content-Disposition"])

    @patch(
        "apps.ocorrencias.views._render_pdf", return_value=b"%PDF-1.4 fake"
    )
    def test_pdf_agrupa_por_aluno(self, render_mock):
        self._auth(self.diretor)
        resp = self.client.get(self.url, {"formato": "pdf"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp["Content-Type"], "application/pdf")

        html = render_mock.call_args[0][0]
        # Ana tem duas ocorrências e aparece uma vez só, como cabeçalho
        # de bloco; as duas descrições estão dentro dele.
        self.assertEqual(html.count('class="aluno-nome">Ana<'), 1)
        self.assertIn("Conversa durante a prova.", html)
        self.assertIn("Atraso reiterado.", html)
        self.assertIn("Relatório de Ocorrências", html)
        # Sintaxe de template que sobra vira texto visível no PDF.
        self.assertNotIn("{#", html)
        self.assertNotIn("{%", html)

    @patch("apps.ocorrencias.views._render_pdf", return_value=b"%PDF")
    def test_pdf_nao_vaza_turma_de_outra_escola_no_cabecalho(self, render_mock):
        """Recorte vazio não pode imprimir o nome da turma pedida.

        O queryset é escopado, então `?turma=<id alheio>` devolve nada —
        mas resolver o rótulo pelo parâmetro colocaria o nome da turma de
        outra escola no cabeçalho do PDF.
        """
        self._auth(self.diretor)
        resp = self.client.get(
            self.url, {"formato": "pdf", "turma": self.turma_alheia.id}
        )
        self.assertEqual(resp.status_code, 200)
        html = render_mock.call_args[0][0]
        self.assertNotIn("Turma Secreta", html)
        self.assertIn("Nenhuma ocorrência no recorte", html)

    @patch("apps.ocorrencias.views.LIMITE_PDF_OCORRENCIAS", 2)
    def test_pdf_recusa_recorte_grande_e_aponta_a_saida(self):
        """WeasyPrint é síncrono: um PDF gigante derruba o worker."""
        self._auth(self.diretor)
        resp = self.client.get(self.url, {"formato": "pdf"})
        self.assertEqual(resp.status_code, 400)
        self.assertIn("CSV/XLSX", str(resp.data))

        # O mesmo recorte sai sem reclamação em planilha.
        self.assertEqual(len(self._csv()), 4)
