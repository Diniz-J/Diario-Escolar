"""Testes da API do financeiro (fatia 2).

O que a fatia promete e precisa ficar travado:

- **financeiro é só direção**: professor e inspetor levam 403 em tudo,
  leitura inclusive;
- escopo de escola na leitura e guard de IDOR na escrita;
- a escrita do que é dinheiro não existe aqui: `status`, `valor_pago`,
  `data_pagamento`, `id_externo` são read-only e `POST /pagamentos/` dá
  405 (conciliação é da fatia 3);
- `DELETE` cancela a fatura, e recusa quando há pagamento registrado;
- as invariantes do modelo valem via API (o serializer roda o `clean()`);
- a listagem de faturas não faz query por linha, apesar dos campos
  derivados que leem o plano.
"""
from datetime import date, timedelta
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.models import Usuario
from apps.escola.models import Aluno, Escola, Turma
from apps.financeiro.models import Fatura, FaturaItem, Pagamento, PlanoCobranca

URL_PLANOS = reverse("api_v1:planocobranca-list")
URL_FATURAS = reverse("api_v1:fatura-list")
URL_ITENS = reverse("api_v1:faturaitem-list")
URL_PAGAMENTOS = reverse("api_v1:pagamento-list")


def url_plano(pk) -> str:
    return reverse("api_v1:planocobranca-detail", args=[pk])


def url_fatura(pk) -> str:
    return reverse("api_v1:fatura-detail", args=[pk])


def url_pagamento(pk) -> str:
    return reverse("api_v1:pagamento-detail", args=[pk])


class _Setup(TestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        cls.escola = Escola.objects.create(nome="Escola A")
        cls.outra = Escola.objects.create(nome="Escola B")
        cls.turma = cls._turma(cls.escola, "1A")
        cls.turma2 = cls._turma(cls.escola, "2A")
        cls.turma_b = cls._turma(cls.outra, "1A")

        cls.ana = cls._aluno(cls.escola, cls.turma, "001", "Ana Lima")
        cls.bia = cls._aluno(cls.escola, cls.turma2, "002", "Bia Souza")
        cls.aluno_b = cls._aluno(cls.outra, cls.turma_b, "001", "Caio Dias")

        cls.diretora = cls._usuario("diretora", Usuario.Perfil.DIRETOR, cls.escola)
        cls.secretaria = cls._usuario(
            "secretaria", Usuario.Perfil.SECRETARIA, cls.escola
        )
        cls.coordenador = cls._usuario(
            "coordenador", Usuario.Perfil.COORDENADOR, cls.escola
        )
        cls.professor = cls._usuario(
            "professor", Usuario.Perfil.PROFESSOR, cls.escola
        )
        cls.inspetor = cls._usuario("inspetor", Usuario.Perfil.INSPETOR, cls.escola)
        cls.diretor_b = cls._usuario("diretor_b", Usuario.Perfil.DIRETOR, cls.outra)
        cls.admin = cls._usuario("admin", Usuario.Perfil.ADMIN, None)

        cls.plano_ana = PlanoCobranca.objects.create(
            escola=cls.escola,
            aluno=cls.ana,
            valor_mensalidade=Decimal("1000.00"),
            dia_vencimento=10,
            vigencia_inicio=date(2026, 1, 1),
        )
        cls.plano_b = PlanoCobranca.objects.create(
            escola=cls.outra,
            aluno=cls.aluno_b,
            valor_mensalidade=Decimal("800.00"),
            dia_vencimento=5,
            vigencia_inicio=date(2026, 1, 1),
        )
        cls.fatura_ana = Fatura.objects.create(
            escola=cls.escola,
            plano=cls.plano_ana,
            aluno=cls.ana,
            competencia=date(2026, 3, 1),
            valor=Decimal("1000.00"),
            vencimento=date(2026, 3, 10),
        )
        cls.fatura_b = Fatura.objects.create(
            escola=cls.outra,
            plano=cls.plano_b,
            aluno=cls.aluno_b,
            competencia=date(2026, 3, 1),
            valor=Decimal("800.00"),
            vencimento=date(2026, 3, 5),
        )

    @staticmethod
    def _turma(escola, nome):
        return Turma.objects.create(
            escola=escola, nome=nome, turno=Turma.Turno.MATUTINO, ano_letivo=2026
        )

    @staticmethod
    def _aluno(escola, turma, matricula, nome):
        return Aluno.objects.create(
            escola=escola, turma=turma, matricula=matricula, nome_completo=nome
        )

    @staticmethod
    def _usuario(username, perfil, escola):
        return Usuario.objects.create_user(
            username=username, password="x", perfil=perfil, escola=escola
        )

    def setUp(self) -> None:
        self.client = APIClient()

    def _como(self, usuario) -> None:
        self.client.force_authenticate(user=usuario)

    def payload_plano(self, **extra) -> dict:
        dados = {
            "aluno": self.bia.pk,
            "valor_mensalidade": "900.00",
            "dia_vencimento": 5,
            "vigencia_inicio": "2026-01-01",
        }
        dados.update(extra)
        return dados

    def payload_fatura(self, **extra) -> dict:
        dados = {
            "plano": self.plano_ana.pk,
            "competencia": "2026-04-01",
            "valor": "1000.00",
            "vencimento": "2026-04-10",
        }
        dados.update(extra)
        return dados


# ====================================================================== #
# Permissão                                                              #
# ====================================================================== #


class PermissaoTests(_Setup):
    def test_direcao_le(self):
        for usuario in (self.diretora, self.secretaria, self.coordenador, self.admin):
            with self.subTest(perfil=usuario.perfil):
                self._como(usuario)
                for url in (URL_PLANOS, URL_FATURAS, URL_ITENS, URL_PAGAMENTOS):
                    self.assertEqual(self.client.get(url).status_code, 200, url)

    def test_professor_e_inspetor_nao_leem(self):
        """Mensalidade não é assunto de quem dá aula."""
        for usuario in (self.professor, self.inspetor):
            with self.subTest(perfil=usuario.perfil):
                self._como(usuario)
                for url in (URL_PLANOS, URL_FATURAS, URL_ITENS, URL_PAGAMENTOS):
                    self.assertEqual(self.client.get(url).status_code, 403, url)

    def test_professor_nao_escreve(self):
        self._como(self.professor)
        resp = self.client.post(URL_PLANOS, self.payload_plano(), format="json")
        self.assertEqual(resp.status_code, 403)

    def test_anonimo_nao_le(self):
        self.assertEqual(self.client.get(URL_FATURAS).status_code, 401)


# ====================================================================== #
# Escopo de escola e IDOR                                                #
# ====================================================================== #


class EscopoTests(_Setup):
    def test_listagem_so_traz_a_propria_escola(self):
        self._como(self.diretora)
        ids = [f["id"] for f in self.client.get(URL_FATURAS).data["results"]]
        self.assertEqual(ids, [self.fatura_ana.pk])

    def test_fatura_de_outra_escola_da_404(self):
        self._como(self.diretora)
        self.assertEqual(self.client.get(url_fatura(self.fatura_b.pk)).status_code, 404)

    def test_plano_de_outra_escola_da_404(self):
        self._como(self.diretora)
        self.assertEqual(self.client.get(url_plano(self.plano_b.pk)).status_code, 404)

    def test_admin_global_ve_as_duas_escolas(self):
        self._como(self.admin)
        ids = {f["id"] for f in self.client.get(URL_FATURAS).data["results"]}
        self.assertEqual(ids, {self.fatura_ana.pk, self.fatura_b.pk})

    def test_escrever_na_escola_alheia_da_400(self):
        """Guard de IDOR: o escopo esconde leitura, não bloqueia escrita."""
        self._como(self.diretora)
        resp = self.client.post(
            URL_PLANOS,
            self.payload_plano(escola=self.outra.pk),
            format="json",
        )
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn("escola", resp.data)

    def test_escola_deduzida_do_jwt(self):
        """Diretor não escolhe escola — o auto-escopo preenche."""
        self._como(self.diretora)
        resp = self.client.post(URL_PLANOS, self.payload_plano(), format="json")
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(
            PlanoCobranca.objects.get(pk=resp.data["id"]).escola_id, self.escola.pk
        )

    def test_plano_de_aluno_de_outra_escola_da_400(self):
        self._como(self.diretora)
        resp = self.client.post(
            URL_PLANOS, self.payload_plano(aluno=self.aluno_b.pk), format="json"
        )
        self.assertEqual(resp.status_code, 400, resp.data)


# ====================================================================== #
# PlanoCobranca                                                          #
# ====================================================================== #


class PlanoTests(_Setup):
    def setUp(self) -> None:
        super().setUp()
        self._como(self.diretora)

    def test_criar(self):
        resp = self.client.post(URL_PLANOS, self.payload_plano(), format="json")
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data["aluno_nome"], "Bia Souza")

    def test_valor_efetivo_vem_calculado(self):
        resp = self.client.post(
            URL_PLANOS,
            self.payload_plano(desconto_tipo="percentual", desconto_valor="10.00"),
            format="json",
        )
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data["valor_efetivo"], "810.00")

    def test_multa_e_juros_vem_do_default_de_settings(self):
        resp = self.client.post(URL_PLANOS, self.payload_plano(), format="json")
        self.assertEqual(resp.data["multa_percentual"], "2.00")
        self.assertEqual(resp.data["juros_mes_percentual"], "1.00")

    def test_vigencia_sobreposta_da_400(self):
        """Prova que o `clean()` do modelo roda no caminho da API."""
        resp = self.client.post(
            URL_PLANOS,
            self.payload_plano(aluno=self.ana.pk, vigencia_inicio="2026-06-01"),
            format="json",
        )
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn("vigencia_inicio", resp.data)

    def test_desconto_incoerente_da_400(self):
        resp = self.client.post(
            URL_PLANOS,
            self.payload_plano(desconto_tipo="nenhum", desconto_valor="50.00"),
            format="json",
        )
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn("desconto_valor", resp.data)

    def test_patch_parcial_enxerga_o_registro_todo(self):
        """Mudar só o tipo do desconto bate na invariante do par."""
        resp = self.client.patch(
            url_plano(self.plano_ana.pk),
            {"desconto_valor": "200.00"},
            format="json",
        )
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn("desconto_valor", resp.data)

    def test_editar_o_proprio_plano_nao_colide_consigo(self):
        resp = self.client.patch(
            url_plano(self.plano_ana.pk),
            {"valor_mensalidade": "1100.00"},
            format="json",
        )
        self.assertEqual(resp.status_code, 200, resp.data)

    def test_delete_desativa(self):
        resp = self.client.delete(url_plano(self.plano_ana.pk))
        self.assertEqual(resp.status_code, 204)
        self.plano_ana.refresh_from_db()
        self.assertFalse(self.plano_ana.ativo)

    def test_filtro_vigente_em(self):
        PlanoCobranca.objects.create(
            escola=self.escola,
            aluno=self.bia,
            valor_mensalidade=Decimal("500.00"),
            dia_vencimento=5,
            vigencia_inicio=date(2026, 1, 1),
            vigencia_fim=date(2026, 2, 28),
        )
        resp = self.client.get(URL_PLANOS, {"vigente_em": "2026-06-01"})
        self.assertEqual([p["id"] for p in resp.data], [self.plano_ana.pk])

    def test_listagem_sem_page_devolve_array_cru(self):
        """`PaginacaoPadrao` é opt-in: sem `?page`, lista inteira."""
        resp = self.client.get(URL_PLANOS)
        self.assertIsInstance(resp.data, list)


# ====================================================================== #
# Fatura                                                                 #
# ====================================================================== #


class FaturaTests(_Setup):
    def setUp(self) -> None:
        super().setUp()
        self._como(self.diretora)

    def test_criar_deduz_o_aluno_do_plano(self):
        resp = self.client.post(URL_FATURAS, self.payload_fatura(), format="json")
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data["aluno"], self.ana.pk)
        self.assertEqual(resp.data["aluno_nome"], "Ana Lima")

    def test_aluno_do_payload_e_ignorado(self):
        """`aluno` é read-only: o vínculo vem do contrato, não do corpo."""
        resp = self.client.post(
            URL_FATURAS, self.payload_fatura(aluno=self.bia.pk), format="json"
        )
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data["aluno"], self.ana.pk)

    def test_competencia_repetida_da_400_e_nao_500(self):
        """O unique de banco existe, mas o erro tem que ser legível."""
        resp = self.client.post(
            URL_FATURAS,
            self.payload_fatura(competencia="2026-03-01", vencimento="2026-03-10"),
            format="json",
        )
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn("competencia", resp.data)
        self.assertIn("Ana Lima", str(resp.data["competencia"]))

    def test_competencia_fora_do_dia_primeiro_da_400(self):
        resp = self.client.post(
            URL_FATURAS, self.payload_fatura(competencia="2026-04-15"), format="json"
        )
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn("competencia", resp.data)

    def test_campos_derivados_no_payload(self):
        resp = self.client.get(url_fatura(self.fatura_ana.pk))
        self.assertEqual(resp.status_code, 200)
        for campo in (
            "saldo",
            "encargos",
            "valor_atualizado",
            "dias_atraso",
            "esta_vencida",
        ):
            self.assertIn(campo, resp.data)
        self.assertEqual(resp.data["saldo"], "1000.00")

    def test_status_e_valores_pagos_sao_read_only(self):
        """Marcar "pago" pela API seria receber dinheiro que não entrou."""
        resp = self.client.patch(
            url_fatura(self.fatura_ana.pk),
            {
                "status": "pago",
                "valor_pago": "1000.00",
                "data_pagamento": "2026-03-09",
                "id_externo": "pay_falso",
            },
            format="json",
        )
        self.assertEqual(resp.status_code, 200, resp.data)
        self.fatura_ana.refresh_from_db()
        self.assertEqual(self.fatura_ana.status, Fatura.Status.PENDENTE)
        self.assertEqual(self.fatura_ana.valor_pago, Decimal("0.00"))
        self.assertIsNone(self.fatura_ana.data_pagamento)
        self.assertEqual(self.fatura_ana.id_externo, "")

    def test_valor_e_vencimento_sao_editaveis(self):
        resp = self.client.patch(
            url_fatura(self.fatura_ana.pk),
            {"valor": "1050.00", "vencimento": "2026-03-15"},
            format="json",
        )
        self.assertEqual(resp.status_code, 200, resp.data)
        self.fatura_ana.refresh_from_db()
        self.assertEqual(self.fatura_ana.valor, Decimal("1050.00"))

    def test_delete_cancela(self):
        resp = self.client.delete(url_fatura(self.fatura_ana.pk))
        self.assertEqual(resp.status_code, 204)
        self.fatura_ana.refresh_from_db()
        self.assertEqual(self.fatura_ana.status, Fatura.Status.CANCELADO)

    def test_delete_com_pagamento_registrado_da_400(self):
        self.fatura_ana.valor_pago = Decimal("500.00")
        self.fatura_ana.save(update_fields=["valor_pago", "atualizado_em"])
        resp = self.client.delete(url_fatura(self.fatura_ana.pk))
        self.assertEqual(resp.status_code, 400, resp.data)
        self.fatura_ana.refresh_from_db()
        self.assertEqual(self.fatura_ana.status, Fatura.Status.PENDENTE)

    def test_paginacao_compulsoria(self):
        resp = self.client.get(URL_FATURAS)
        self.assertIn("count", resp.data)
        self.assertIn("results", resp.data)

    def test_opt_out_da_paginacao(self):
        resp = self.client.get(URL_FATURAS, {"page_size": "all"})
        self.assertIsInstance(resp.data, list)

    def test_filtro_por_competencia(self):
        self._nova_fatura(date(2026, 4, 1), date(2026, 4, 10))
        resp = self.client.get(
            URL_FATURAS,
            {"competencia_de": "2026-04-01", "page_size": "all"},
        )
        self.assertEqual([f["competencia"] for f in resp.data], ["2026-04-01"])

    def test_filtro_por_vencimento(self):
        self._nova_fatura(date(2026, 4, 1), date(2026, 4, 10))
        resp = self.client.get(
            URL_FATURAS,
            {"vencimento_ate": "2026-03-31", "page_size": "all"},
        )
        self.assertEqual([f["id"] for f in resp.data], [self.fatura_ana.pk])

    def test_filtro_por_status_e_turma(self):
        resp = self.client.get(
            URL_FATURAS,
            {"status": "pendente", "turma": self.turma.pk, "page_size": "all"},
        )
        self.assertEqual([f["id"] for f in resp.data], [self.fatura_ana.pk])
        vazio = self.client.get(
            URL_FATURAS, {"turma": self.turma2.pk, "page_size": "all"}
        )
        self.assertEqual(vazio.data, [])

    def test_listagem_nao_faz_query_por_linha(self):
        """Os derivados leem o plano — sem select_related seria N+1."""
        self._nova_fatura(date(2026, 4, 1), date(2026, 4, 10))
        # Uma query serve a listagem inteira: plano, aluno e escola vêm
        # no mesmo JOIN. O número não pode crescer com as linhas.
        with self.assertNumQueries(1):
            self.client.get(URL_FATURAS, {"page_size": "all"})
        for competencia in (date(2026, 5, 1), date(2026, 6, 1)):
            self._nova_fatura(competencia, competencia)
        with self.assertNumQueries(1):
            self.client.get(URL_FATURAS, {"page_size": "all"})

    def _nova_fatura(self, competencia, vencimento) -> Fatura:
        return Fatura.objects.create(
            escola=self.escola,
            plano=self.plano_ana,
            aluno=self.ana,
            competencia=competencia,
            valor=Decimal("1000.00"),
            vencimento=vencimento,
        )


# ====================================================================== #
# FaturaItem                                                             #
# ====================================================================== #


class FaturaItemTests(_Setup):
    def setUp(self) -> None:
        super().setUp()
        self._como(self.diretora)

    def test_criar_e_filtrar_por_fatura(self):
        resp = self.client.post(
            URL_ITENS,
            {
                "fatura": self.fatura_ana.pk,
                "descricao": "Material didático",
                "valor": "150.00",
            },
            format="json",
        )
        self.assertEqual(resp.status_code, 201, resp.data)
        lista = self.client.get(URL_ITENS, {"fatura": self.fatura_ana.pk})
        self.assertEqual(len(lista.data), 1)

    def test_item_em_fatura_de_outra_escola_da_400(self):
        resp = self.client.post(
            URL_ITENS,
            {"fatura": self.fatura_b.pk, "descricao": "Taxa", "valor": "10.00"},
            format="json",
        )
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_delete_apaga(self):
        item = FaturaItem.objects.create(
            escola=self.escola,
            fatura=self.fatura_ana,
            descricao="Taxa",
            valor=Decimal("10.00"),
        )
        resp = self.client.delete(reverse("api_v1:faturaitem-detail", args=[item.pk]))
        self.assertEqual(resp.status_code, 204)
        self.assertEqual(FaturaItem.objects.count(), 0)


# ====================================================================== #
# Pagamento — somente leitura nesta fatia                                #
# ====================================================================== #


class PagamentoTests(_Setup):
    def setUp(self) -> None:
        super().setUp()
        self._como(self.diretora)
        self.pagamento = Pagamento.objects.create(
            escola=self.escola,
            fatura=self.fatura_ana,
            valor=Decimal("1000.00"),
            data=date(2026, 3, 9),
            metodo=Pagamento.Metodo.PIX,
        )

    def test_post_registra_e_reconcilia(self):
        """A API não grava pagamento: delega no service, que reconcilia."""
        fatura = Fatura.objects.create(
            escola=self.escola,
            plano=self.plano_ana,
            aluno=self.ana,
            competencia=date(2026, 4, 1),
            valor=Decimal("500.00"),
            vencimento=date(2026, 4, 10),
        )
        resp = self.client.post(
            URL_PAGAMENTOS,
            {
                "fatura": fatura.pk,
                "valor": "500.00",
                "data": "2026-04-09",
                "metodo": "dinheiro",
            },
            format="json",
        )
        self.assertEqual(resp.status_code, 201, resp.data)
        fatura.refresh_from_db()
        self.assertEqual(fatura.status, Fatura.Status.PAGO)
        self.assertEqual(fatura.valor_pago, Decimal("500.00"))
        self.assertEqual(fatura.data_pagamento, date(2026, 4, 9))

    def test_post_em_fatura_de_outra_escola_da_400(self):
        """Guard de IDOR: o escopo do queryset não cobre o campo `fatura`."""
        resp = self.client.post(
            URL_PAGAMENTOS,
            {
                "fatura": self.fatura_b.pk,
                "valor": "10.00",
                "data": "2026-03-09",
                "metodo": "pix",
            },
            format="json",
        )
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn("fatura", resp.data)

    def test_post_repetido_com_a_mesma_referencia_nao_duplica(self):
        payload = {
            "fatura": self.fatura_ana.pk,
            "valor": "100.00",
            "data": "2026-03-09",
            "metodo": "pix",
            "referencia_externa": "pay_999",
        }
        primeiro = self.client.post(URL_PAGAMENTOS, payload, format="json")
        segundo = self.client.post(URL_PAGAMENTOS, payload, format="json")
        self.assertEqual(primeiro.status_code, 201, primeiro.data)
        self.assertEqual(segundo.status_code, 201, segundo.data)
        self.assertEqual(primeiro.data["id"], segundo.data["id"])
        self.assertEqual(Pagamento.objects.filter(referencia_externa="pay_999").count(), 1)

    def test_post_em_fatura_cancelada_da_400(self):
        self.fatura_ana.status = Fatura.Status.CANCELADO
        self.fatura_ana.save(update_fields=["status", "atualizado_em"])
        resp = self.client.post(
            URL_PAGAMENTOS,
            {
                "fatura": self.fatura_ana.pk,
                "valor": "10.00",
                "data": "2026-03-09",
                "metodo": "pix",
            },
            format="json",
        )
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_delete_estorna(self):
        """`DELETE` é estorno — apaga o pagamento e reconcilia a fatura.

        Fatura própria, não a do `setUp`: aquela já tem um pagamento de
        fixture, e estornar um de dois deixaria a fatura paga — correto,
        mas não é o que este teste quer observar.
        """
        fatura = Fatura.objects.create(
            escola=self.escola,
            plano=self.plano_ana,
            aluno=self.ana,
            competencia=date(2026, 5, 1),
            valor=Decimal("300.00"),
            # Vencimento à frente de hoje: o estorno devolve a fatura pra
            # `pendente`. Com vencimento passado a reconciliação devolveria
            # `vencido` — correto, mas não é o que este teste observa.
            vencimento=date.today() + timedelta(days=30),
        )
        pagamento = self.client.post(
            URL_PAGAMENTOS,
            {
                "fatura": fatura.pk,
                "valor": "300.00",
                "data": date.today().isoformat(),
                "metodo": "pix",
            },
            format="json",
        ).data
        resp = self.client.delete(url_pagamento(pagamento["id"]))
        self.assertEqual(resp.status_code, 204)
        fatura.refresh_from_db()
        self.assertEqual(fatura.status, Fatura.Status.PENDENTE)
        self.assertEqual(fatura.valor_pago, Decimal("0.00"))
        self.assertEqual(Pagamento.objects.filter(fatura=fatura).count(), 0)

    def test_patch_nao_existe(self):
        """Corrigir pagamento é estornar e registrar de novo."""
        resp = self.client.patch(
            url_pagamento(self.pagamento.pk), {"valor": "1.00"}, format="json"
        )
        self.assertEqual(resp.status_code, 405)

    def test_professor_nao_registra_pagamento(self):
        self._como(self.professor)
        resp = self.client.post(
            URL_PAGAMENTOS,
            {
                "fatura": self.fatura_ana.pk,
                "valor": "10.00",
                "data": "2026-03-09",
                "metodo": "pix",
            },
            format="json",
        )
        self.assertEqual(resp.status_code, 403)

    def test_leitura_traz_aluno_e_competencia(self):
        resp = self.client.get(url_pagamento(self.pagamento.pk))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["aluno_nome"], "Ana Lima")
        self.assertEqual(resp.data["competencia"], "2026-03-01")

    def test_filtro_por_periodo_e_aluno(self):
        resp = self.client.get(
            URL_PAGAMENTOS,
            {"data_de": "2026-03-01", "aluno": self.ana.pk, "page_size": "all"},
        )
        self.assertEqual([p["id"] for p in resp.data], [self.pagamento.pk])
        vazio = self.client.get(
            URL_PAGAMENTOS, {"data_ate": "2026-03-01", "page_size": "all"}
        )
        self.assertEqual(vazio.data, [])
