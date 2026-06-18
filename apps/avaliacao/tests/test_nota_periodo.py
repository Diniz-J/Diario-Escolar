"""Testes de `NotaPeriodo` + endpoints de inicialização e lançamento em lote.

Cobre:
- inicializar auto-cria por aluno ativo (pula inativo)
- inicializar é idempotente (não recria)
- lancar-em-lote faz upsert (cria E atualiza)
- transação atômica falha o lote se aluno inválido
- audit log via /historico/
- IDOR e escopo de escola
- estado do PeriodoAvaliativo muda pra "fechado" quando há NotaPeriodo
"""
from datetime import date
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.accounts.models import Usuario
from apps.avaliacao.models import NotaPeriodo, PeriodoAvaliativo
from apps.avaliacao.views import NotaPeriodoViewSet
from apps.escola.models import Aluno, Disciplina, Escola, Turma


class _Base(TestCase):
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
        cls.disciplina_mat = Disciplina.objects.create(
            escola=cls.escola_a, nome="Matemática"
        )
        cls.periodo_1 = PeriodoAvaliativo.objects.create(
            escola=cls.escola_a,
            nome="1º Bim",
            ordem=1,
            ano_letivo=2026,
            data_inicio=date(2026, 2, 1),
            data_fim=date(2026, 4, 30),
        )

        cls.aluno1 = Aluno.objects.create(
            escola=cls.escola_a,
            turma=cls.turma_a,
            matricula="001",
            nome_completo="Ana",
            nome_responsavel="r",
            email_responsavel="r@r.com",
        )
        cls.aluno2 = Aluno.objects.create(
            escola=cls.escola_a,
            turma=cls.turma_a,
            matricula="002",
            nome_completo="Bia",
            nome_responsavel="r",
            email_responsavel="r@r.com",
        )
        cls.aluno_inativo = Aluno.objects.create(
            escola=cls.escola_a,
            turma=cls.turma_a,
            matricula="003",
            nome_completo="Ex-aluno",
            ativo=False,
            nome_responsavel="r",
            email_responsavel="r@r.com",
        )

        cls.admin = Usuario.objects.create_user(
            username="adm", password="x", perfil=Usuario.Perfil.ADMIN
        )
        cls.diretor = Usuario.objects.create_user(
            username="dir",
            password="x",
            perfil=Usuario.Perfil.DIRETOR,
            escola=cls.escola_a,
        )
        cls.professor = Usuario.objects.create_user(
            username="prof",
            password="x",
            perfil=Usuario.Perfil.PROFESSOR,
            escola=cls.escola_a,
        )

    def _request_action(
        self, action: str, payload: dict, user=None, pk=None
    ):
        path = f"/{pk}/{action}/" if pk else f"/{action}/"
        if action == "historico":
            req = self.factory.get(path)
            view = NotaPeriodoViewSet.as_view({"get": "historico"})
        else:
            req = self.factory.post(path, payload, format="json")
            view = NotaPeriodoViewSet.as_view({"post": action.replace("-", "_")})
        force_authenticate(req, user=user or self.diretor)
        if pk:
            return view(req, pk=pk)
        return view(req)

    def _request_list(self, query="", user=None):
        path = f"/?{query}" if query else "/"
        req = self.factory.get(path)
        view = NotaPeriodoViewSet.as_view({"get": "list"})
        force_authenticate(req, user=user or self.diretor)
        return view(req)


# ===================================================================== #
# Inicializar                                                            #
# ===================================================================== #


class InicializarTests(_Base):
    def test_inicializar_cria_uma_por_aluno_ativo(self):
        resp = self._request_action(
            "inicializar",
            {
                "turma": self.turma_a.id,
                "disciplina": self.disciplina_mat.id,
                "periodo": self.periodo_1.id,
            },
        )
        self.assertEqual(resp.status_code, 200, resp.data)
        # 2 alunos ativos, 1 inativo — esperado: 2 NotaPeriodo.
        self.assertEqual(len(resp.data), 2)
        alunos = {n["aluno"] for n in resp.data}
        self.assertEqual(alunos, {self.aluno1.id, self.aluno2.id})
        # Todas com nota_final = null inicialmente.
        for n in resp.data:
            self.assertIsNone(n["nota_final"])

    def test_inicializar_eh_idempotente(self):
        """Chamar duas vezes não cria duplicado."""
        for _ in range(2):
            resp = self._request_action(
                "inicializar",
                {
                    "turma": self.turma_a.id,
                    "disciplina": self.disciplina_mat.id,
                    "periodo": self.periodo_1.id,
                },
            )
            self.assertEqual(resp.status_code, 200)
        # No banco: exatamente 2 NotaPeriodo (uma por aluno ativo).
        self.assertEqual(NotaPeriodo.objects.count(), 2)

    def test_inicializar_preserva_notas_ja_lancadas(self):
        """Inicializar duas vezes não apaga nota existente."""
        # Primeira chamada cria vazias.
        self._request_action(
            "inicializar",
            {
                "turma": self.turma_a.id,
                "disciplina": self.disciplina_mat.id,
                "periodo": self.periodo_1.id,
            },
        )
        # Professor preenche a nota da Ana.
        nota_ana = NotaPeriodo.objects.get(
            aluno=self.aluno1,
            disciplina=self.disciplina_mat,
            periodo=self.periodo_1,
        )
        nota_ana.nota_final = Decimal("8.50")
        nota_ana.save()

        # Segunda chamada de inicializar.
        resp = self._request_action(
            "inicializar",
            {
                "turma": self.turma_a.id,
                "disciplina": self.disciplina_mat.id,
                "periodo": self.periodo_1.id,
            },
        )
        # A nota da Ana continua lá.
        nota_ana.refresh_from_db()
        self.assertEqual(nota_ana.nota_final, Decimal("8.50"))

    def test_inicializar_turma_de_outra_escola_404(self):
        """Diretor da escola A não consegue inicializar turma da B."""
        turma_b = Turma.objects.create(
            escola=self.escola_b,
            nome="1º A",
            turno=Turma.Turno.MATUTINO,
            ano_letivo=2026,
        )
        resp = self._request_action(
            "inicializar",
            {
                "turma": turma_b.id,
                "disciplina": self.disciplina_mat.id,
                "periodo": self.periodo_1.id,
            },
        )
        self.assertEqual(resp.status_code, 404)


# ===================================================================== #
# Lançar em lote (UPSERT)                                                #
# ===================================================================== #


class LancarEmLoteTests(_Base):
    def test_lancar_cria_quando_nao_existe(self):
        """UPSERT: sem inicializar antes, lancar-em-lote já cria."""
        resp = self._request_action(
            "lancar-em-lote",
            {
                "turma": self.turma_a.id,
                "disciplina": self.disciplina_mat.id,
                "periodo": self.periodo_1.id,
                "itens": [
                    {"aluno_id": self.aluno1.id, "nota_final": "8.00"},
                ],
            },
        )
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data["atualizadas"], 1)
        nota = NotaPeriodo.objects.get(
            aluno=self.aluno1,
            disciplina=self.disciplina_mat,
            periodo=self.periodo_1,
        )
        self.assertEqual(nota.nota_final, Decimal("8.00"))

    def test_lancar_atualiza_existente(self):
        NotaPeriodo.objects.create(
            escola=self.escola_a,
            aluno=self.aluno1,
            disciplina=self.disciplina_mat,
            periodo=self.periodo_1,
            nota_final=Decimal("5.00"),
        )
        resp = self._request_action(
            "lancar-em-lote",
            {
                "turma": self.turma_a.id,
                "disciplina": self.disciplina_mat.id,
                "periodo": self.periodo_1.id,
                "itens": [
                    {
                        "aluno_id": self.aluno1.id,
                        "nota_final": "9.00",
                        "observacao": "recuperação",
                    },
                ],
            },
        )
        self.assertEqual(resp.status_code, 200)
        nota = NotaPeriodo.objects.get(aluno=self.aluno1)
        self.assertEqual(nota.nota_final, Decimal("9.00"))
        self.assertEqual(nota.observacao, "recuperação")

    def test_lancar_pode_deslancar(self):
        NotaPeriodo.objects.create(
            escola=self.escola_a,
            aluno=self.aluno1,
            disciplina=self.disciplina_mat,
            periodo=self.periodo_1,
            nota_final=Decimal("7.00"),
        )
        resp = self._request_action(
            "lancar-em-lote",
            {
                "turma": self.turma_a.id,
                "disciplina": self.disciplina_mat.id,
                "periodo": self.periodo_1.id,
                "itens": [{"aluno_id": self.aluno1.id, "nota_final": None}],
            },
        )
        self.assertEqual(resp.status_code, 200)
        nota = NotaPeriodo.objects.get(aluno=self.aluno1)
        self.assertIsNone(nota.nota_final)

    def test_lancar_aluno_fora_da_turma_falha_atomico(self):
        # Aluno em outra turma da mesma escola.
        outra_turma = Turma.objects.create(
            escola=self.escola_a,
            nome="2º A",
            turno=Turma.Turno.MATUTINO,
            ano_letivo=2026,
        )
        aluno_outra = Aluno.objects.create(
            escola=self.escola_a,
            turma=outra_turma,
            matricula="099",
            nome_completo="Outro",
            nome_responsavel="r",
            email_responsavel="r@r.com",
        )
        resp = self._request_action(
            "lancar-em-lote",
            {
                "turma": self.turma_a.id,
                "disciplina": self.disciplina_mat.id,
                "periodo": self.periodo_1.id,
                "itens": [
                    {"aluno_id": self.aluno1.id, "nota_final": "8.00"},
                    {"aluno_id": aluno_outra.id, "nota_final": "9.00"},
                ],
            },
        )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.data["atualizadas"], 0)
        self.assertEqual(len(resp.data["falhas"]), 1)
        # Rollback: nota da Ana NÃO foi salva.
        self.assertFalse(
            NotaPeriodo.objects.filter(aluno=self.aluno1).exists()
        )


# ===================================================================== #
# Audit + estado do período                                              #
# ===================================================================== #


class HistoricoEEstadoTests(_Base):
    def test_historico_retorna_snapshots(self):
        nota = NotaPeriodo.objects.create(
            escola=self.escola_a,
            aluno=self.aluno1,
            disciplina=self.disciplina_mat,
            periodo=self.periodo_1,
            nota_final=Decimal("7.00"),
        )
        nota.nota_final = Decimal("8.50")
        nota.save()

        resp = self._request_action("historico", {}, pk=nota.id)
        self.assertEqual(resp.status_code, 200)
        eventos = resp.data["eventos"]
        # 2 snapshots: criação + 1 update.
        self.assertEqual(len(eventos), 2)
        # Mais recente primeiro: nota_final="8.50".
        self.assertEqual(eventos[0]["nota_final"], "8.50")

    def test_estado_periodo_fecha_quando_ha_nota_lancada(self):
        """`PeriodoAvaliativo.estado` reage à existência de NotaPeriodo."""
        # Vazio inicialmente.
        self.assertEqual(self.periodo_1.estado, PeriodoAvaliativo.ESTADO_VAZIO)

        # Cria NotaPeriodo vazia (nota_final=null) — ainda não conta como
        # fechado.
        NotaPeriodo.objects.create(
            escola=self.escola_a,
            aluno=self.aluno1,
            disciplina=self.disciplina_mat,
            periodo=self.periodo_1,
            nota_final=None,
        )
        self.assertEqual(self.periodo_1.estado, PeriodoAvaliativo.ESTADO_VAZIO)

        # Preenche — agora conta como fechado.
        nota = NotaPeriodo.objects.get(aluno=self.aluno1)
        nota.nota_final = Decimal("8.00")
        nota.save()
        self.assertEqual(
            self.periodo_1.estado, PeriodoAvaliativo.ESTADO_FECHADO
        )


# ===================================================================== #
# Escopo e permissão                                                     #
# ===================================================================== #


class EscopoTests(_Base):
    def test_diretor_so_ve_notas_da_propria_escola(self):
        # Cria nota na escola B.
        turma_b = Turma.objects.create(
            escola=self.escola_b,
            nome="1º A",
            turno=Turma.Turno.MATUTINO,
            ano_letivo=2026,
        )
        disc_b = Disciplina.objects.create(escola=self.escola_b, nome="Mat")
        per_b = PeriodoAvaliativo.objects.create(
            escola=self.escola_b,
            nome="1º Bim",
            ordem=1,
            ano_letivo=2026,
            data_inicio=date(2026, 2, 1),
            data_fim=date(2026, 4, 30),
        )
        aluno_b = Aluno.objects.create(
            escola=self.escola_b,
            turma=turma_b,
            matricula="b1",
            nome_completo="Aluno B",
            nome_responsavel="r",
            email_responsavel="r@r.com",
        )
        NotaPeriodo.objects.create(
            escola=self.escola_b,
            aluno=aluno_b,
            disciplina=disc_b,
            periodo=per_b,
            nota_final=Decimal("9.00"),
        )

        # Escopo obrigatório no list: filtra pelo período da B de propósito
        # — se o escopo de escola falhasse, a nota da B vazaria aqui.
        resp = self._request_list(query=f"periodo={per_b.id}", user=self.diretor)
        self.assertEqual(resp.status_code, 200)
        # Diretor A não vê notas da B.
        nomes = [n["aluno_nome"] for n in resp.data]
        self.assertNotIn("Aluno B", nomes)

    def test_list_sem_escopo_400(self):
        """Sem filtro de escopo o list é recusado (evita matriz inteira)."""
        resp = self._request_list(user=self.diretor)
        self.assertEqual(resp.status_code, 400)

    def test_professor_pode_lancar(self):
        """Decisão do produto: qualquer professor da escola lança;
        audit cobre."""
        resp = self._request_action(
            "lancar-em-lote",
            {
                "turma": self.turma_a.id,
                "disciplina": self.disciplina_mat.id,
                "periodo": self.periodo_1.id,
                "itens": [{"aluno_id": self.aluno1.id, "nota_final": "7.00"}],
            },
            user=self.professor,
        )
        self.assertEqual(resp.status_code, 200, resp.data)
