"""Testes do `portal_semear_responsaveis`.

A semeadura é o que permite a escola começar a usar o portal sem redigitar
nada — e é onde um erro silencioso produziria conta duplicada, convite
duplicado ou responsável sem acesso.
"""
from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from apps.escola.models import Aluno, Escola, Turma
from apps.portal.models import Responsavel, ResponsavelAluno


class SemeaduraTests(TestCase):
    @classmethod
    def setUpTestData(cls) -> None:
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

    def _aluno(self, nome, email="", responsavel="", ativo=True, escola=None):
        escola = escola or self.escola_a
        return Aluno.objects.create(
            escola=escola,
            matricula=f"M{Aluno.objects.count() + 1}",
            nome_completo=nome,
            turma=self.turma_a if escola == self.escola_a else self.turma_b,
            ativo=ativo,
            nome_responsavel=responsavel,
            email_responsavel=email,
        )

    def _semear(self, *args):
        out = StringIO()
        call_command("portal_semear_responsaveis", *args, stdout=out)
        return out.getvalue()

    def test_cria_responsavel_e_vinculo(self):
        self._aluno("Ana", "maria@example.com", "Maria Silva")
        self._semear()

        responsavel = Responsavel.objects.get(email="maria@example.com")
        self.assertEqual(responsavel.nome, "Maria Silva")
        self.assertEqual(responsavel.escola, self.escola_a)
        self.assertEqual(responsavel.alunos.count(), 1)

    def test_irmaos_viram_uma_conta_com_dois_vinculos(self):
        """Sem dedup, o pai de dois filhos teria duas contas e dois convites."""
        self._aluno("Irmão 1", "familia@example.com", "José")
        self._aluno("Irmão 2", "familia@example.com", "José")
        self._semear()

        self.assertEqual(Responsavel.objects.count(), 1)
        self.assertEqual(ResponsavelAluno.objects.count(), 2)

    def test_deduplica_normalizando_caixa_e_espaco(self):
        self._aluno("Irmão 1", "Familia@Example.com ", "José")
        self._aluno("Irmão 2", "familia@example.com", "José")
        self._semear()

        self.assertEqual(Responsavel.objects.count(), 1)
        self.assertEqual(Responsavel.objects.get().email, "familia@example.com")

    def test_aluno_sem_email_e_pulado(self):
        """Email é a âncora da identidade: sem ele não há conta a criar."""
        self._aluno("Com email", "tem@example.com", "Maria")
        self._aluno("Sem email", "", "Tem nome mas não tem email")
        saida = self._semear()

        self.assertEqual(Responsavel.objects.count(), 1)
        self.assertEqual(ResponsavelAluno.objects.count(), 1)
        self.assertIn("1 alunos sem email", saida)

    def test_idempotente(self):
        """Rodar de novo não duplica — só completa o que faltar."""
        self._aluno("Ana", "maria@example.com", "Maria")
        self._semear()
        self._semear()
        self.assertEqual(Responsavel.objects.count(), 1)
        self.assertEqual(ResponsavelAluno.objects.count(), 1)

    def test_segunda_rodada_pega_aluno_novo(self):
        self._aluno("Ana", "maria@example.com", "Maria")
        self._semear()
        self._aluno("Novo", "maria@example.com", "Maria")
        self._semear()

        self.assertEqual(Responsavel.objects.count(), 1)
        self.assertEqual(ResponsavelAluno.objects.count(), 2)

    def test_inclui_aluno_inativo(self):
        """Transferido: o responsável mantém o histórico (decisão do PORTAL.md)."""
        self._aluno("Transferido", "mae@example.com", "Mãe", ativo=False)
        self._semear()
        self.assertEqual(Responsavel.objects.count(), 1)
        self.assertEqual(ResponsavelAluno.objects.count(), 1)

    def test_mesmo_email_em_duas_escolas_gera_duas_contas(self):
        self._aluno("Da A", "mae@example.com", "Mãe")
        self._aluno("Da B", "mae@example.com", "Mãe", escola=self.escola_b)
        self._semear()

        self.assertEqual(Responsavel.objects.count(), 2)
        self.assertEqual(
            set(Responsavel.objects.values_list("escola_id", flat=True)),
            {self.escola_a.id, self.escola_b.id},
        )

    def test_filtro_por_escola(self):
        self._aluno("Da A", "a@example.com", "Mãe A")
        self._aluno("Da B", "b@example.com", "Mãe B", escola=self.escola_b)
        self._semear("--escola-id", str(self.escola_a.id))

        self.assertEqual(Responsavel.objects.count(), 1)
        self.assertEqual(Responsavel.objects.get().email, "a@example.com")

    def test_nome_padrao_quando_cadastro_nao_tem_nome(self):
        self._aluno("Ana", "mae@example.com", "")
        self._semear()
        self.assertEqual(Responsavel.objects.get().nome, "Responsável")

    def test_nome_vem_do_primeiro_cadastro_que_tiver(self):
        """Irmãos com o nome preenchido em só um dos cadastros."""
        self._aluno("Irmão 1", "familia@example.com", "")
        self._aluno("Irmão 2", "familia@example.com", "José Souza")
        self._semear()
        self.assertEqual(Responsavel.objects.get().nome, "José Souza")

    def test_conta_semeada_nao_pode_logar(self):
        """O acesso só nasce pelo convite (fatia 3)."""
        self._aluno("Ana", "mae@example.com", "Mãe")
        self._semear()
        self.assertFalse(Responsavel.objects.get().has_usable_password())

    def test_dry_run_nao_grava(self):
        self._aluno("Ana", "mae@example.com", "Mãe")
        saida = self._semear("--dry-run")

        self.assertEqual(Responsavel.objects.count(), 0)
        self.assertEqual(ResponsavelAluno.objects.count(), 0)
        self.assertIn("dry-run", saida)
        self.assertIn("mae@example.com", saida)

    def test_segunda_rodada_preenche_nome_que_faltava(self):
        """`get_or_create` só aplica defaults na criação.

        Sem tratamento, a conta semeada antes de a escola preencher o
        `nome_responsavel` ficaria como "Responsável" para sempre, mesmo
        rodando o comando de novo — contrariando a promessa de que a
        segunda rodada completa o que faltou.
        """
        aluno = self._aluno("Ana", "mae@example.com", "")
        self._semear()
        self.assertEqual(Responsavel.objects.get().nome, "Responsável")

        aluno.nome_responsavel = "Maria Silva"
        aluno.save(update_fields=["nome_responsavel"])
        saida = self._semear()

        self.assertEqual(Responsavel.objects.get().nome, "Maria Silva")
        self.assertIn("1 nomes preenchidos", saida)

    def test_nao_sobrescreve_nome_real_ja_gravado(self):
        """Nome corrigido à mão no admin não é atropelado pelo cadastro.

        O cadastro do aluno é a fonte menos confiável: quem ajustou o nome
        no admin sabe mais que o campo digitado na matrícula.
        """
        aluno = self._aluno("Ana", "mae@example.com", "Maria")
        self._semear()
        responsavel = Responsavel.objects.get()
        responsavel.nome = "Maria Aparecida Silva"
        responsavel.save(update_fields=["nome"])

        aluno.nome_responsavel = "M. Silva"
        aluno.save(update_fields=["nome_responsavel"])
        self._semear()

        self.assertEqual(
            Responsavel.objects.get().nome, "Maria Aparecida Silva"
        )
