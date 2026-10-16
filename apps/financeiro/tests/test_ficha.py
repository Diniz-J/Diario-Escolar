"""Testes da ficha financeira do aluno (fatia 6b).

O ponto delicado está nos totais: eles são somados em Python sobre os
métodos do modelo, e não em SQL. O teste que justifica essa escolha é o
`test_pagamento_a_mais_nao_abate_divida_de_outra_fatura` — com
`Sum(valor - valor_pago)` no banco, o excesso de uma fatura reduziria a
dívida real do aluno e a escola cobraria menos do que deve.
"""
from datetime import date, timedelta
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.models import Usuario
from apps.escola.models import Aluno, Escola, Turma
from apps.financeiro.models import Fatura, PlanoCobranca
from apps.financeiro.services import registrar_pagamento


def url_ficha(aluno_id) -> str:
    return reverse("api_v1:ficha-financeira-aluno", args=[aluno_id])


class _Setup(TestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        cls.hoje = date.today()
        cls.escola = Escola.objects.create(nome="Escola A")
        cls.outra = Escola.objects.create(nome="Escola B")
        cls.turma = Turma.objects.create(
            escola=cls.escola, nome="1A", turno=Turma.Turno.MATUTINO, ano_letivo=2026
        )
        cls.turma_b = Turma.objects.create(
            escola=cls.outra, nome="1A", turno=Turma.Turno.MATUTINO, ano_letivo=2026
        )
        cls.ana = Aluno.objects.create(
            escola=cls.escola, turma=cls.turma, matricula="001", nome_completo="Ana"
        )
        cls.aluno_b = Aluno.objects.create(
            escola=cls.outra, turma=cls.turma_b, matricula="001", nome_completo="Caio"
        )
        cls.diretora = Usuario.objects.create_user(
            username="diretora", password="x",
            perfil=Usuario.Perfil.DIRETOR, escola=cls.escola,
        )
        cls.professor = Usuario.objects.create_user(
            username="professor", password="x",
            perfil=Usuario.Perfil.PROFESSOR, escola=cls.escola,
        )
        cls.admin = Usuario.objects.create_user(
            username="admin", password="x", perfil=Usuario.Perfil.ADMIN,
        )
        cls.plano = PlanoCobranca.objects.create(
            escola=cls.escola,
            aluno=cls.ana,
            valor_mensalidade=Decimal("1000.00"),
            dia_vencimento=10,
            vigencia_inicio=date(2026, 1, 1),
        )

    def setUp(self) -> None:
        self.client = APIClient()
        self.client.force_authenticate(user=self.diretora)

    def fatura(self, competencia, vencimento, **extra) -> Fatura:
        dados = {
            "escola": self.escola,
            "plano": self.plano,
            "aluno": self.ana,
            "competencia": competencia,
            "valor": Decimal("1000.00"),
            "vencimento": vencimento,
        }
        dados.update(extra)
        return Fatura.objects.create(**dados)


class FichaTests(_Setup):
    def test_aluno_sem_nada_devolve_ficha_zerada(self):
        resp = self.client.get(url_ficha(self.ana.pk))
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data["aluno"]["nome_completo"], "Ana")
        self.assertEqual(resp.data["aluno"]["turma"], "1A")
        self.assertEqual(resp.data["totais"]["em_aberto"], "0.00")
        self.assertEqual(resp.data["totais"]["faturas_abertas"], 0)
        self.assertEqual(resp.data["faturas"], [])
        # O plano aparece mesmo sem fatura: é o contrato cadastrado.
        self.assertEqual(len(resp.data["planos"]), 1)

    def test_totais_de_fatura_em_aberto(self):
        self.fatura(date(2026, 3, 1), self.hoje + timedelta(days=10))
        resp = self.client.get(url_ficha(self.ana.pk))
        totais = resp.data["totais"]
        self.assertEqual(totais["em_aberto"], "1000.00")
        self.assertEqual(totais["vencido"], "0.00")
        self.assertEqual(totais["encargos_hoje"], "0.00")
        self.assertEqual(totais["a_cobrar_hoje"], "1000.00")
        self.assertEqual(totais["faturas_abertas"], 1)

    def test_fatura_vencida_entra_no_vencido_e_soma_encargos(self):
        """15 dias de atraso: multa 2% = 20,00 e juros 1%/mês = 5,00."""
        self.fatura(date(2026, 3, 1), self.hoje - timedelta(days=15))
        totais = self.client.get(url_ficha(self.ana.pk)).data["totais"]
        self.assertEqual(totais["em_aberto"], "1000.00")
        self.assertEqual(totais["vencido"], "1000.00")
        self.assertEqual(totais["encargos_hoje"], "25.00")
        self.assertEqual(totais["a_cobrar_hoje"], "1025.00")

    def test_paga_e_cancelada_nao_sao_divida(self):
        self.fatura(
            date(2026, 3, 1),
            self.hoje - timedelta(days=30),
            status=Fatura.Status.PAGO,
            valor_pago=Decimal("1000.00"),
            data_pagamento=self.hoje - timedelta(days=31),
        )
        self.fatura(
            date(2026, 4, 1),
            self.hoje - timedelta(days=5),
            status=Fatura.Status.CANCELADO,
        )
        totais = self.client.get(url_ficha(self.ana.pk)).data["totais"]
        self.assertEqual(totais["em_aberto"], "0.00")
        self.assertEqual(totais["faturas_abertas"], 0)
        # Mas as duas continuam no histórico da ficha.
        self.assertEqual(len(self.client.get(url_ficha(self.ana.pk)).data["faturas"]), 2)

    def test_pagamento_parcial_abate_o_saldo(self):
        fatura = self.fatura(date(2026, 3, 1), self.hoje + timedelta(days=10))
        registrar_pagamento(fatura, Decimal("400.00"), self.hoje, "pix")
        totais = self.client.get(url_ficha(self.ana.pk)).data["totais"]
        self.assertEqual(totais["em_aberto"], "600.00")
        self.assertEqual(totais["pago_no_ano"], "400.00")

    def test_pagamento_a_mais_nao_abate_divida_de_outra_fatura(self):
        """O motivo de somar em Python e não em SQL.

        Fatura A paga com R$ 1.100 (boleto vencido quitado com multa) e
        fatura B em aberto por R$ 1.000. Um `Sum(valor - valor_pago)` no
        banco daria 900 — os 100 de excesso em A abatendo a dívida de B —
        e a escola cobraria menos do que o aluno deve. O piso do
        `saldo()` por fatura é o que impede isso.
        """
        paga = self.fatura(date(2026, 3, 1), self.hoje - timedelta(days=20))
        registrar_pagamento(paga, Decimal("1100.00"), self.hoje, "boleto")
        self.fatura(date(2026, 4, 1), self.hoje + timedelta(days=10))

        totais = self.client.get(url_ficha(self.ana.pk)).data["totais"]
        self.assertEqual(totais["em_aberto"], "1000.00")
        self.assertEqual(totais["faturas_abertas"], 1)
        self.assertEqual(totais["pago_no_ano"], "1100.00")

    def test_pago_no_ano_ignora_ano_anterior(self):
        antiga = self.fatura(date(2026, 1, 1), date(2026, 1, 10))
        # Pagamento no ano passado: entra no histórico, não no total do ano.
        registrar_pagamento(
            antiga, Decimal("500.00"), self.hoje.replace(year=self.hoje.year - 1), "pix"
        )
        resp = self.client.get(url_ficha(self.ana.pk))
        self.assertEqual(resp.data["totais"]["pago_no_ano"], "0.00")
        self.assertEqual(len(resp.data["pagamentos"]), 1)

    def test_historicos_vem_ordenados_do_mais_recente(self):
        self.fatura(date(2026, 3, 1), date(2026, 3, 10))
        self.fatura(date(2026, 5, 1), date(2026, 5, 10))
        self.fatura(date(2026, 4, 1), date(2026, 4, 10))
        competencias = [
            f["competencia"] for f in self.client.get(url_ficha(self.ana.pk)).data["faturas"]
        ]
        self.assertEqual(
            competencias, ["2026-05-01", "2026-04-01", "2026-03-01"]
        )

    def test_plano_encerrado_aparece_no_historico(self):
        """Saber que o aluno era bolsista até março explica a fatura de março."""
        self.plano.ativo = False
        self.plano.save(update_fields=["ativo", "atualizado_em"])
        planos = self.client.get(url_ficha(self.ana.pk)).data["planos"]
        self.assertEqual(len(planos), 1)
        self.assertFalse(planos[0]["ativo"])


class FichaPermissaoTests(_Setup):
    def test_professor_nao_ve(self):
        self.client.force_authenticate(user=self.professor)
        self.assertEqual(self.client.get(url_ficha(self.ana.pk)).status_code, 403)

    def test_anonimo_nao_ve(self):
        self.client.force_authenticate(user=None)
        self.assertEqual(self.client.get(url_ficha(self.ana.pk)).status_code, 401)

    def test_aluno_de_outra_escola_da_404(self):
        """404 e não 403: existência de aluno alheio não é informação daqui."""
        self.assertEqual(self.client.get(url_ficha(self.aluno_b.pk)).status_code, 404)

    def test_admin_global_ve_qualquer_escola(self):
        self.client.force_authenticate(user=self.admin)
        self.assertEqual(self.client.get(url_ficha(self.aluno_b.pk)).status_code, 200)

    def test_aluno_inexistente_da_404(self):
        self.assertEqual(self.client.get(url_ficha(99999)).status_code, 404)
