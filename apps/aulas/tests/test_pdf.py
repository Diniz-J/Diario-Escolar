"""Testes do endpoint de PDF do diário (`RegistroAulaViewSet.pdf`).

WeasyPrint só roda no container Linux (libs do SO), então mockamos o
`_render_pdf`. O `render_to_string` roda de verdade — valida o template.
"""
from datetime import date, timedelta
from unittest import mock

from rest_framework.test import force_authenticate

from apps.aulas.models import RegistroAula
from apps.aulas.tests.test_views import _AulasSetup
from apps.aulas.views import RegistroAulaViewSet


class RegistroAulaPdfTests(_AulasSetup):
    def _get_pdf(self, user, query=""):
        req = self.factory.get(f"/registros-aula/pdf/{query}")
        force_authenticate(req, user=user)
        return RegistroAulaViewSet.as_view({"get": "pdf"})(req)

    @mock.patch("apps.aulas.views._render_pdf", return_value=b"%PDF-1.4 fake")
    def test_diretor_exporta_pdf_attachment(self, mock_render):
        self._criar_registro()
        resp = self._get_pdf(self.diretor, f"?professor={self.professor.id}")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp["Content-Type"], "application/pdf")
        self.assertIn("attachment", resp["Content-Disposition"])
        self.assertIn("diario_", resp["Content-Disposition"])
        mock_render.assert_called_once()

    @mock.patch("apps.aulas.views._render_pdf", return_value=b"%PDF")
    def test_professor_exporta_o_proprio(self, _mock):
        self._criar_registro()
        resp = self._get_pdf(self.usuario_docente)
        self.assertEqual(resp.status_code, 200)

    @mock.patch("apps.aulas.views._render_pdf", return_value=b"%PDF")
    def test_filtro_de_status_recorta(self, mock_render):
        """O recorte da tela (filterset) vale pro PDF: só passa o que casa."""
        self._criar_registro(
            status=RegistroAula.Status.LANCADO, data=date.today()
        )
        self._criar_registro(
            status=RegistroAula.Status.RASCUNHO,
            data=date.today() - timedelta(days=1),
        )
        with mock.patch(
            "apps.aulas.views.render_to_string", return_value="<html></html>"
        ) as mock_render_html:
            resp = self._get_pdf(self.diretor, "?status=lancado")
        self.assertEqual(resp.status_code, 200)
        contexto = mock_render_html.call_args.args[1]
        total_aulas = sum(len(g["aulas"]) for g in contexto["grupos"])
        self.assertEqual(total_aulas, 1)
        self.assertEqual(contexto["total"], 1)
