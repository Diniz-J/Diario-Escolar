"""Testes das actions de import/export plugadas nos ViewSets da app escola.

Padrão dos testes:
- `APIRequestFactory` + `force_authenticate` (sem URL routing — chama
  as actions diretamente, idêntico ao restante da suíte).
- Uploads simulados via `SimpleUploadedFile` com CSV gerado em memória.

Cobre: export escopado por escola, template, dedup ("pular existentes"),
criação automática de turma no import de Aluno, IDOR e a integração
Professor → Usuario (sem disparar email de verdade — backend `locmem`
inspeciona via `mail.outbox`).
"""
from __future__ import annotations

import io
from unittest.mock import patch

from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.accounts.models import Usuario
from apps.escola.models import (
    Aluno,
    Disciplina,
    Escola,
    Lecionamento,
    Professor,
    Turma,
)
from apps.escola.views import (
    AlunoViewSet,
    DisciplinaViewSet,
    LecionamentoViewSet,
    ProfessorViewSet,
    TurmaViewSet,
)


def _csv_bytes(linhas: list[str]) -> bytes:
    """Concatena linhas com `\n` e devolve bytes UTF-8 (com BOM)."""
    return ("﻿" + "\n".join(linhas)).encode("utf-8")


def _arquivo(nome: str, conteudo: bytes, content_type: str = "text/csv") -> SimpleUploadedFile:
    return SimpleUploadedFile(nome, conteudo, content_type=content_type)


class _Base(TestCase):
    """Setup compartilhado: 2 escolas pra cobrir escopo + IDOR."""

    @classmethod
    def setUpTestData(cls) -> None:
        cls.factory = APIRequestFactory()

        cls.escola_a = Escola.objects.create(nome="Escola A")
        cls.escola_b = Escola.objects.create(nome="Escola B")

        cls.turma_a = Turma.objects.create(
            escola=cls.escola_a,
            nome="1º A",
            turno=Turma.Turno.MATUTINO,
            ano_letivo=2026,
        )
        cls.turma_b = Turma.objects.create(
            escola=cls.escola_b,
            nome="1º A",
            turno=Turma.Turno.MATUTINO,
            ano_letivo=2026,
        )

        cls.diretor_a = Usuario.objects.create_user(
            username="dir_a",
            password="x",
            perfil=Usuario.Perfil.DIRETOR,
            escola=cls.escola_a,
        )
        cls.diretor_b = Usuario.objects.create_user(
            username="dir_b",
            password="x",
            perfil=Usuario.Perfil.DIRETOR,
            escola=cls.escola_b,
        )
        cls.professor_a = Usuario.objects.create_user(
            username="prof_a",
            password="x",
            perfil=Usuario.Perfil.PROFESSOR,
            escola=cls.escola_a,
        )

        # Aluno existente na Escola A pra testar dedup.
        Aluno.objects.create(
            escola=cls.escola_a,
            turma=cls.turma_a,
            matricula="2026001",
            nome_completo="Aluno Existente",
            nome_responsavel="Resp Um",
            email_responsavel="resp1@example.com",
        )

    def _get(self, viewset_cls, action_method, query="", user=None):
        req = self.factory.get(f"/?{query}")
        view = viewset_cls.as_view({"get": action_method})
        force_authenticate(req, user=user or self.diretor_a)
        return view(req)

    def _post_upload(
        self,
        viewset_cls,
        arquivo,
        *,
        confirmar: bool = False,
        user=None,
        extras: dict | None = None,
    ):
        data = {"arquivo": arquivo, **(extras or {})}
        query = "?confirmar=true" if confirmar else ""
        req = self.factory.post(f"/{query}", data, format="multipart")
        view = viewset_cls.as_view({"post": "importar"})
        force_authenticate(req, user=user or self.diretor_a)
        return view(req)


# ===================================================================== #
# Export                                                                 #
# ===================================================================== #


class ExportTests(_Base):
    def test_export_aluno_csv_filtra_por_escola(self):
        # Aluno na escola B não pode aparecer no export do diretor da A.
        Aluno.objects.create(
            escola=self.escola_b,
            turma=self.turma_b,
            matricula="2026999",
            nome_completo="Aluno B",
            nome_responsavel="Resp B",
            email_responsavel="b@example.com",
        )
        resp = self._get(AlunoViewSet, "export", query="formato=csv")
        self.assertEqual(resp.status_code, 200)
        conteudo = resp.content.decode("utf-8-sig")
        self.assertIn("Aluno Existente", conteudo)
        self.assertNotIn("Aluno B", conteudo)

    def test_export_aluno_tem_coluna_turma_nome(self):
        resp = self._get(AlunoViewSet, "export", query="formato=csv")
        conteudo = resp.content.decode("utf-8-sig")
        # Coluna numérica `turma` (id) foi substituída por `turma_nome`.
        primeira_linha = conteudo.splitlines()[0]
        self.assertIn("turma_nome", primeira_linha)
        self.assertIn("ano_letivo", primeira_linha)

    def test_export_xlsx_devolve_attachment(self):
        resp = self._get(AlunoViewSet, "export", query="formato=xlsx")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("attachment", resp["Content-Disposition"])
        self.assertTrue(resp["Content-Disposition"].endswith('alunos.xlsx"'))

    def test_export_formato_invalido_retorna_400(self):
        resp = self._get(AlunoViewSet, "export", query="formato=pdf")
        self.assertEqual(resp.status_code, 400)

    def test_template_retorna_so_cabecalhos(self):
        resp = self._get(AlunoViewSet, "template", query="formato=csv")
        self.assertEqual(resp.status_code, 200)
        conteudo = resp.content.decode("utf-8-sig").strip()
        # Template tem 1 linha (header) e mais nada.
        self.assertEqual(len(conteudo.splitlines()), 1)
        self.assertIn("matricula", conteudo)


# ===================================================================== #
# Import: dedup + criação de turma                                       #
# ===================================================================== #


class ImportAlunoTests(_Base):
    def test_import_dry_run_nao_persiste(self):
        csv = _csv_bytes(
            [
                "matricula,nome_completo,turma_nome,ano_letivo,nome_responsavel,email_responsavel",
                "2026002,Novo Aluno,1º A,2026,Resp Dois,resp2@example.com",
            ]
        )
        resp = self._post_upload(AlunoViewSet, _arquivo("alunos.csv", csv))
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.data["persistido"])
        self.assertEqual(resp.data["criados"], 1)
        # Confere que nada foi salvo (só o aluno do setUpTestData persiste).
        self.assertEqual(Aluno.objects.filter(escola=self.escola_a).count(), 1)

    def test_import_confirmado_persiste(self):
        csv = _csv_bytes(
            [
                "matricula,nome_completo,turma_nome,ano_letivo,nome_responsavel,email_responsavel",
                "2026002,Novo Aluno,1º A,2026,Resp Dois,resp2@example.com",
            ]
        )
        resp = self._post_upload(
            AlunoViewSet, _arquivo("alunos.csv", csv), confirmar=True
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data["persistido"])
        self.assertEqual(resp.data["criados"], 1)
        self.assertTrue(
            Aluno.objects.filter(
                escola=self.escola_a, matricula="2026002"
            ).exists()
        )

    def test_import_pula_duplicados(self):
        csv = _csv_bytes(
            [
                "matricula,nome_completo,turma_nome,ano_letivo,nome_responsavel,email_responsavel",
                # Matricula 2026001 já existe (setUpTestData).
                "2026001,Aluno Repetido,1º A,2026,X,x@x.com",
                "2026002,Aluno Novo,1º A,2026,Y,y@y.com",
            ]
        )
        resp = self._post_upload(
            AlunoViewSet, _arquivo("alunos.csv", csv), confirmar=True
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["criados"], 1)
        self.assertEqual(len(resp.data["pulados"]), 1)
        self.assertIn("Aluno Repetido", resp.data["pulados"][0]["linha"])

    def test_import_cria_turma_faltante_com_defaults(self):
        csv = _csv_bytes(
            [
                "matricula,nome_completo,turma_nome,ano_letivo,nome_responsavel,email_responsavel",
                "2026003,Aluno Turma Nova,2º B,2026,Z,z@z.com",
            ]
        )
        resp = self._post_upload(
            AlunoViewSet,
            _arquivo("alunos.csv", csv),
            confirmar=True,
            extras={"turno_padrao": "vespertino", "ano_letivo_padrao": "2026"},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["criados"], 1)
        nova_turma = Turma.objects.get(
            escola=self.escola_a, nome="2º B", ano_letivo=2026
        )
        self.assertEqual(nova_turma.turno, "vespertino")

    def test_import_sem_turno_padrao_falha_quando_turma_nao_existe(self):
        csv = _csv_bytes(
            [
                "matricula,nome_completo,turma_nome,ano_letivo,nome_responsavel,email_responsavel",
                "2026003,Aluno Turma Nova,2º B,2026,Z,z@z.com",
            ]
        )
        resp = self._post_upload(
            AlunoViewSet,
            _arquivo("alunos.csv", csv),
            confirmar=True,
        )
        # Sem turno_padrao + turma inexistente → erro na linha, não persiste.
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.data["persistido"])
        self.assertTrue(len(resp.data["erros"]) >= 1)

    def test_import_arquivo_invalido_400(self):
        resp = self._post_upload(
            AlunoViewSet, _arquivo("ruim.txt", b"qualquer coisa")
        )
        self.assertEqual(resp.status_code, 400)


# ===================================================================== #
# Permissões + IDOR                                                      #
# ===================================================================== #


class ImportExportPermissionTests(_Base):
    def test_professor_pode_exportar(self):
        resp = self._get(
            AlunoViewSet,
            "export",
            query="formato=csv",
            user=self.professor_a,
        )
        self.assertEqual(resp.status_code, 200)

    def test_professor_nao_pode_importar(self):
        csv = _csv_bytes(
            [
                "matricula,nome_completo,turma_nome,ano_letivo,nome_responsavel,email_responsavel",
                "2026010,X,1º A,2026,R,r@r.com",
            ]
        )
        resp = self._post_upload(
            AlunoViewSet,
            _arquivo("a.csv", csv),
            user=self.professor_a,
        )
        self.assertEqual(resp.status_code, 403)

    def test_export_de_outra_escola_nao_vaza(self):
        # Aluno só na escola B.
        Aluno.objects.create(
            escola=self.escola_b,
            turma=self.turma_b,
            matricula="b001",
            nome_completo="Vazaria",
            nome_responsavel="r",
            email_responsavel="r@r.com",
        )
        resp = self._get(
            AlunoViewSet, "export", query="formato=csv", user=self.diretor_a
        )
        self.assertNotIn("Vazaria", resp.content.decode("utf-8-sig"))


# ===================================================================== #
# Professor: cria Usuario + dispara email de reset                       #
# ===================================================================== #


class ImportProfessorTests(_Base):
    def test_import_professor_cria_usuario_e_envia_email(self):
        csv = _csv_bytes(
            [
                "username,first_name,last_name,email,ativo",
                "novo_prof,Novo,Professor,novo@example.com,true",
            ]
        )
        # `enviar_link_redefinicao` é síncrono em testes (backend locmem),
        # então `mail.outbox` reflete o envio na hora.
        resp = self._post_upload(
            ProfessorViewSet,
            _arquivo("p.csv", csv),
            confirmar=True,
        )
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data["criados"], 1)

        usuario = Usuario.objects.get(username="novo_prof")
        self.assertEqual(usuario.perfil, Usuario.Perfil.PROFESSOR)
        self.assertEqual(usuario.escola_id, self.escola_a.id)
        self.assertTrue(
            Professor.objects.filter(usuario=usuario, escola=self.escola_a).exists()
        )
        # Email de redefinição foi enviado.
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("novo@example.com", mail.outbox[0].to)

    def test_dry_run_professor_nao_dispara_email(self):
        """Pré-visualização não pode mandar email — só na confirmação."""
        csv = _csv_bytes(
            [
                "username,first_name,last_name,email,ativo",
                "preview_prof,Preview,Professor,preview@example.com,true",
            ]
        )
        resp = self._post_upload(
            ProfessorViewSet, _arquivo("p.csv", csv), confirmar=False
        )
        self.assertEqual(resp.status_code, 200)
        # `criados` reporta o que SERIA criado; persistido deve ser False.
        self.assertEqual(resp.data["criados"], 1)
        self.assertFalse(resp.data["persistido"])
        # Nenhum side-effect: nem email, nem Usuario salvo no banco.
        self.assertEqual(len(mail.outbox), 0)
        self.assertFalse(
            Usuario.objects.filter(username="preview_prof").exists()
        )

    def test_reimport_professor_mesmo_csv_e_idempotente_e_nao_redispara_email(self):
        """2º import do mesmo CSV pula o professor (skip_row na chave).

        Documenta a contrapartida da unicidade global de username:
        re-rodar o mesmo arquivo NA MESMA escola é seguro (idempotente).
        A falha por username duplicado em outra escola fica coberta no
        `test_import_professor_username_duplicado_falha_linha`.
        """
        csv = _csv_bytes(
            [
                "username,first_name,last_name,email,ativo",
                "novo_prof,Novo,Professor,novo@example.com,true",
            ]
        )
        resp1 = self._post_upload(
            ProfessorViewSet, _arquivo("p.csv", csv), confirmar=True
        )
        self.assertEqual(resp1.data["criados"], 1)
        self.assertEqual(len(mail.outbox), 1)

        # 2º import: nada novo, professor é pulado.
        resp2 = self._post_upload(
            ProfessorViewSet, _arquivo("p.csv", csv), confirmar=True
        )
        self.assertEqual(resp2.data["criados"], 0)
        self.assertEqual(len(resp2.data["pulados"]), 1)
        # Não dispara email de novo.
        self.assertEqual(len(mail.outbox), 1)

    def test_import_professor_username_duplicado_falha_linha(self):
        # Cria primeiro um usuário com o username pra forçar conflito.
        Usuario.objects.create_user(
            username="ja_existe",
            password="x",
            perfil=Usuario.Perfil.DIRETOR,
        )
        csv = _csv_bytes(
            [
                "username,first_name,last_name,email,ativo",
                "ja_existe,Conflito,Aqui,c@c.com,true",
            ]
        )
        resp = self._post_upload(
            ProfessorViewSet, _arquivo("p.csv", csv), confirmar=True
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["criados"], 0)
        self.assertTrue(len(resp.data["erros"]) >= 1)
        self.assertIn("já existe", resp.data["erros"][0]["mensagem"].lower())


# ===================================================================== #
# Lecionamento: amarra entidades que já existem                          #
# ===================================================================== #


class ImportLecionamentoTests(_Base):
    @classmethod
    def setUpTestData(cls) -> None:
        super().setUpTestData()
        # Disciplina + Professor já cadastrados pra amarrar Lecionamento.
        cls.disciplina = Disciplina.objects.create(
            escola=cls.escola_a, nome="Matemática"
        )
        usuario_prof = Usuario.objects.create_user(
            username="prof_existente",
            password="x",
            perfil=Usuario.Perfil.PROFESSOR,
            escola=cls.escola_a,
        )
        cls.professor = Professor.objects.create(
            usuario=usuario_prof, escola=cls.escola_a
        )

    def test_import_lecionamento_amarra_entidades(self):
        csv = _csv_bytes(
            [
                "professor_username,turma_nome,ano_letivo,disciplina_nome,ativo",
                "prof_existente,1º A,2026,Matemática,true",
            ]
        )
        resp = self._post_upload(
            LecionamentoViewSet, _arquivo("l.csv", csv), confirmar=True
        )
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data["criados"], 1)
        self.assertTrue(
            Lecionamento.objects.filter(
                professor=self.professor,
                turma=self.turma_a,
                disciplina=self.disciplina,
            ).exists()
        )

    def test_import_lecionamento_disciplina_inexistente_falha(self):
        csv = _csv_bytes(
            [
                "professor_username,turma_nome,ano_letivo,disciplina_nome,ativo",
                "prof_existente,1º A,2026,Português,true",
            ]
        )
        resp = self._post_upload(
            LecionamentoViewSet, _arquivo("l.csv", csv), confirmar=True
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["criados"], 0)
        self.assertTrue(len(resp.data["erros"]) >= 1)


# ===================================================================== #
# Disciplina + Turma (smoke — confirma que o ciclo end-to-end roda)      #
# ===================================================================== #


class ImportAlunoCachePerformanceTests(_Base):
    def test_cache_de_turma_evita_n_mais_1_em_arquivo_grande(self):
        """10 alunos pra mesma turma devem disparar 1 query de turma, não 10."""
        linhas = [
            "matricula,nome_completo,turma_nome,ano_letivo,nome_responsavel,email_responsavel",
        ]
        for i in range(10):
            linhas.append(
                f"CACHE{i:03d},Cache Aluno {i},1º A,2026,R,r@r.com"
            )
        csv = _csv_bytes(linhas)

        # Snapshot do contador de queries durante o import.
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        with CaptureQueriesContext(connection) as ctx:
            resp = self._post_upload(
                AlunoViewSet, _arquivo("alunos.csv", csv), confirmar=True
            )
        self.assertEqual(resp.data["criados"], 10)

        sqls = [q["sql"] for q in ctx.captured_queries]
        # Quantas vezes consultamos `escola_turma` filtrando por nome?
        # 1 hit do cache miss inicial; 9 hits do cache (zero queries).
        # A heurística é frouxa pra acomodar variações de filtros do ORM.
        turma_lookups = [
            s for s in sqls
            if 'FROM "escola_turma"' in s and "nome" in s
        ]
        self.assertLessEqual(
            len(turma_lookups),
            2,
            f"Cache de turma não está evitando N+1: {len(turma_lookups)} queries",
        )


class ImportErroNoCabecalhoTests(_Base):
    def test_base_error_aparece_na_resposta(self):
        """Erros de header (ex.: coluna obrigatória ausente) chegam em `erros`.

        O `_coletar_erros` agora inclui `result.base_errors` — antes
        sumia silenciosamente. Aqui upload sem `matricula` no header
        dispara base_error.
        """
        csv = _csv_bytes(
            [
                "nome_completo,turma_nome,ano_letivo,nome_responsavel,email_responsavel",
                "Sem Matricula,1º A,2026,R,r@r.com",
            ]
        )
        resp = self._post_upload(
            AlunoViewSet, _arquivo("alunos.csv", csv), confirmar=False
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(
            len(resp.data["erros"]) >= 1,
            f"Esperava erros de header, veio: {resp.data}",
        )


class ImportXlsxSmokeTests(_Base):
    def test_import_xlsx_processa_mesma_pipeline_que_csv(self):
        """Smoke test do path XLSX — tablib detecta pela extensão."""
        import io

        import tablib

        ds = tablib.Dataset(
            headers=[
                "matricula",
                "nome_completo",
                "turma_nome",
                "ano_letivo",
                "nome_responsavel",
                "email_responsavel",
            ]
        )
        ds.append(("XLSX001", "Aluno XLSX", "1º A", 2026, "R", "r@r.com"))
        binario = io.BytesIO(ds.export("xlsx")).getvalue()

        arquivo = SimpleUploadedFile(
            "alunos.xlsx",
            binario,
            content_type=(
                "application/vnd.openxmlformats-officedocument."
                "spreadsheetml.sheet"
            ),
        )
        resp = self._post_upload(AlunoViewSet, arquivo, confirmar=True)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data["criados"], 1)
        self.assertTrue(
            Aluno.objects.filter(matricula="XLSX001").exists()
        )


class ImportDisciplinaTurmaTests(_Base):
    def test_import_disciplina_csv(self):
        csv = _csv_bytes(
            [
                "nome,ativa",
                "Português,true",
                "História,true",
            ]
        )
        resp = self._post_upload(
            DisciplinaViewSet, _arquivo("d.csv", csv), confirmar=True
        )
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data["criados"], 2)
        self.assertEqual(
            Disciplina.objects.filter(escola=self.escola_a).count(), 2
        )

    def test_import_turma_aceita_label_pt_br_no_turno(self):
        csv = _csv_bytes(
            [
                "nome,turno,ano_letivo,ativa",
                # Label PT-BR — o resource normaliza pra valor canônico.
                "3º C,Vespertino,2026,true",
            ]
        )
        resp = self._post_upload(
            TurmaViewSet, _arquivo("t.csv", csv), confirmar=True
        )
        self.assertEqual(resp.status_code, 200, resp.data)
        nova = Turma.objects.get(
            escola=self.escola_a, nome="3º C", ano_letivo=2026
        )
        self.assertEqual(nova.turno, "vespertino")
