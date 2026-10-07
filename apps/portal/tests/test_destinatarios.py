"""Testes da resolução de destinatário de email — `apps.portal.destinatarios`.

O que está em jogo aqui é a regra do `RESPONSAVEIS.md` §4.1: o fallback
pro campo de texto do aluno dispara por **ausência de vínculo**, nunca por
ausência de destino elegível. Errar isso significa ou escola silenciada
(sem fallback onde devia) ou opt-out ignorado (fallback onde não devia),
então os dois sentidos têm teste.
"""
from django.db import IntegrityError, transaction
from django.test import TestCase

from apps.escola.models import Aluno, Escola, Turma
from apps.portal.destinatarios import (
    destinatarios_do_aluno,
    destinatarios_por_aluno,
)
from apps.portal.models import Responsavel, ResponsavelAluno


class _DestinatariosSetup(TestCase):
    """Fixtures compartilhadas. Sem teste próprio (ver `_PortalSetup`)."""

    @classmethod
    def setUpTestData(cls) -> None:
        cls.escola = Escola.objects.create(nome="Escola A")
        cls.turma = Turma.objects.create(
            escola=cls.escola,
            nome="1º A",
            turno=Turma.Turno.MATUTINO,
            ano_letivo=2026,
        )

    def _aluno(self, nome, email="", responsavel=""):
        return Aluno.objects.create(
            escola=self.escola,
            matricula=f"M{Aluno.objects.count() + 1}",
            nome_completo=nome,
            turma=self.turma,
            nome_responsavel=responsavel,
            email_responsavel=email,
        )

    def _responsavel(self, nome, email, ativo=True, recebe_notificacao=True):
        return Responsavel.objects.create(
            escola=self.escola,
            nome=nome,
            email=email,
            ativo=ativo,
            recebe_notificacao=recebe_notificacao,
        )

    def _vincular(self, responsavel, aluno):
        return ResponsavelAluno.objects.create(
            responsavel=responsavel, aluno=aluno
        )


class DestinatariosTests(_DestinatariosSetup):
    """Vínculo, fallback e lote."""

    def test_aluno_sem_vinculo_cai_no_campo_do_aluno(self):
        """Escola que nunca rodou a semeadura não pode ficar muda."""
        aluno = self._aluno(
            "Ana", email="Maria@Example.com ", responsavel="Maria Silva"
        )

        destinos = destinatarios_do_aluno(aluno)

        self.assertEqual(len(destinos), 1)
        # Normalizado, mesmo vindo torto do cadastro.
        self.assertEqual(destinos[0].email, "maria@example.com")
        self.assertEqual(destinos[0].nome, "Maria Silva")
        self.assertIsNone(destinos[0].responsavel_id)

    def test_aluno_sem_vinculo_e_sem_email_nao_tem_destino(self):
        aluno = self._aluno("Bruno")

        self.assertEqual(destinatarios_do_aluno(aluno), [])

    def test_dois_vinculos_geram_dois_destinos(self):
        """Mãe e pai cadastrados: os dois recebem."""
        aluno = self._aluno(
            "Carla", email="mae@example.com", responsavel="Mãe"
        )
        mae = self._responsavel("Mãe da Carla", "mae@example.com")
        pai = self._responsavel("Pai da Carla", "pai@example.com")
        self._vincular(mae, aluno)
        self._vincular(pai, aluno)

        destinos = destinatarios_do_aluno(aluno)

        self.assertEqual(
            sorted(d.email for d in destinos),
            ["mae@example.com", "pai@example.com"],
        )
        self.assertEqual(
            sorted(d.responsavel_id for d in destinos), sorted([mae.id, pai.id])
        )

    def test_vinculo_vence_o_campo_do_aluno(self):
        """Com vínculo, o campo de texto não entra — nem como extra."""
        aluno = self._aluno(
            "Diana", email="antigo@example.com", responsavel="Cadastro Antigo"
        )
        novo = self._responsavel("Responsável Novo", "novo@example.com")
        self._vincular(novo, aluno)

        destinos = destinatarios_do_aluno(aluno)

        self.assertEqual([d.email for d in destinos], ["novo@example.com"])

    def test_conta_inativa_nao_cai_no_fallback(self):
        """§4.1: há vínculo, logo não há fallback — mesmo sem destino.

        O inverso (cair no campo do aluno) reenviaria pro mesmo endereço
        que a escola acabou de desativar.
        """
        aluno = self._aluno(
            "Elisa", email="desligado@example.com", responsavel="Desligado"
        )
        inativo = self._responsavel(
            "Desligado", "desligado@example.com", ativo=False
        )
        self._vincular(inativo, aluno)

        self.assertEqual(destinatarios_do_aluno(aluno), [])

    def test_conta_inativa_nao_apaga_o_vinculo_ativo_do_outro(self):
        aluno = self._aluno("Fabio")
        ativo = self._responsavel("Ativo", "ativo@example.com")
        inativo = self._responsavel("Inativo", "inativo@example.com", ativo=False)
        self._vincular(ativo, aluno)
        self._vincular(inativo, aluno)

        destinos = destinatarios_do_aluno(aluno)

        self.assertEqual([d.email for d in destinos], ["ativo@example.com"])

    def test_o_banco_impede_duas_contas_com_o_mesmo_email(self):
        """Por que não existe dedup por endereço dentro de um aluno.

        O `RESPONSAVEIS.md` §4.2 supôs que o casal que usa uma conta só
        geraria dois destinos iguais. Não gera: o unique por
        `(escola, email)` recusa a segunda conta, e todo responsável de um
        aluno é da mesma escola dele. A dedup que importa é entre irmãos,
        e essa é do envio (`_agrupar_por_email` do comunicado), não daqui.
        """
        self._responsavel("Um", "casal@example.com")
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self._responsavel("Outro", "casal@example.com")

    def test_irmaos_resolvem_o_mesmo_responsavel(self):
        """Dedup entre irmãos é do envio, não daqui: cada aluno tem o seu."""
        irmao = self._aluno("Hugo")
        irma = self._aluno("Helena")
        responsavel = self._responsavel("Pai", "pai@example.com")
        self._vincular(responsavel, irmao)
        self._vincular(responsavel, irma)

        mapa = destinatarios_por_aluno([irmao, irma])

        self.assertEqual([d.email for d in mapa[irmao.id]], ["pai@example.com"])
        self.assertEqual([d.email for d in mapa[irma.id]], ["pai@example.com"])

    def test_lote_resolve_em_uma_consulta(self):
        """O comunicado alcança a escola toda: N+1 aqui é inaceitável."""
        alunos = []
        for i in range(5):
            aluno = self._aluno(f"Aluno {i}", email=f"a{i}@example.com")
            responsavel = self._responsavel(f"R{i}", f"r{i}@example.com")
            self._vincular(responsavel, aluno)
            alunos.append(aluno)
        # Dois sem vínculo, pra o fallback entrar no mesmo lote.
        alunos.append(self._aluno("Sem vínculo", email="sv@example.com"))
        alunos.append(self._aluno("Sem nada"))

        with self.assertNumQueries(1):
            mapa = destinatarios_por_aluno(alunos)

        self.assertEqual(len(mapa), 7)
        self.assertEqual(sum(len(v) for v in mapa.values()), 6)

    def test_lote_vazio_nao_consulta(self):
        with self.assertNumQueries(0):
            self.assertEqual(destinatarios_por_aluno([]), {})

    def test_todo_aluno_recebido_aparece_no_mapa(self):
        """Quem chama itera o mapa: aluno sem destino vira lista vazia."""
        aluno = self._aluno("Sem ninguém")

        mapa = destinatarios_por_aluno([aluno])

        self.assertEqual(mapa, {aluno.id: []})


class OptOutTests(_DestinatariosSetup):
    """`recebe_notificacao` — silêncio sem perder o acesso ao portal."""

    def test_opt_out_exclui_do_envio(self):
        aluno = self._aluno("Igor")
        recusou = self._responsavel(
            "Recusou", "recusou@example.com", recebe_notificacao=False
        )
        self._vincular(recusou, aluno)

        self.assertEqual(destinatarios_do_aluno(aluno), [])

    def test_opt_out_nao_cai_no_campo_do_aluno(self):
        """A armadilha central: fallback aqui transformaria o opt-out em nada."""
        aluno = self._aluno(
            "Joana", email="recusou@example.com", responsavel="Recusou"
        )
        recusou = self._responsavel(
            "Recusou", "recusou@example.com", recebe_notificacao=False
        )
        self._vincular(recusou, aluno)

        self.assertEqual(destinatarios_do_aluno(aluno), [])

    def test_opt_out_de_um_nao_silencia_o_outro(self):
        aluno = self._aluno("Lia")
        recusou = self._responsavel(
            "Recusou", "recusou@example.com", recebe_notificacao=False
        )
        aceita = self._responsavel("Aceita", "aceita@example.com")
        self._vincular(recusou, aluno)
        self._vincular(aceita, aluno)

        destinos = destinatarios_do_aluno(aluno)

        self.assertEqual([d.email for d in destinos], ["aceita@example.com"])

    def test_notificacao_nasce_ligada(self):
        """Default `True`: nenhuma escola fica muda por causa da migration."""
        responsavel = self._responsavel("Nova", "nova@example.com")

        self.assertTrue(responsavel.recebe_notificacao)
