"""Testes dos modelos do portal — identidade e vínculo."""
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from apps.escola.models import Aluno, Escola, Turma
from apps.portal.models import Responsavel, ResponsavelAluno


class _PortalSetup(TestCase):
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

    def _aluno(self, nome, escola=None, turma=None, email="", responsavel="", ativo=True):
        escola = escola or self.escola_a
        return Aluno.objects.create(
            escola=escola,
            matricula=f"M{Aluno.objects.count() + 1}",
            nome_completo=nome,
            turma=turma or (self.turma_a if escola == self.escola_a else self.turma_b),
            ativo=ativo,
            nome_responsavel=responsavel,
            email_responsavel=email,
        )


class ResponsavelTests(_PortalSetup):
    def test_email_e_normalizado_no_save(self):
        """Sem normalizar, o unique por (escola, email) seria furado."""
        r = Responsavel.objects.create(
            escola=self.escola_a, nome="Maria", email="  Maria@Example.COM "
        )
        r.refresh_from_db()
        self.assertEqual(r.email, "maria@example.com")

    def test_email_unico_por_escola(self):
        Responsavel.objects.create(
            escola=self.escola_a, nome="Maria", email="maria@example.com"
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Responsavel.objects.create(
                    escola=self.escola_a, nome="Outra", email="maria@example.com"
                )

    def test_mesmo_email_em_escolas_diferentes_e_permitido(self):
        """O unique é por escola — a tenancy do projeto é por escola."""
        Responsavel.objects.create(
            escola=self.escola_a, nome="Maria", email="maria@example.com"
        )
        Responsavel.objects.create(
            escola=self.escola_b, nome="Maria", email="maria@example.com"
        )
        self.assertEqual(Responsavel.objects.count(), 2)

    def test_conta_nasce_sem_senha_utilizavel(self):
        """Ninguém entra no portal sem passar pelo convite."""
        r = Responsavel.objects.create(
            escola=self.escola_a, nome="Maria", email="maria@example.com"
        )
        r.set_unusable_password()
        r.save(update_fields=["password"])
        r.refresh_from_db()
        self.assertFalse(r.has_usable_password())
        self.assertFalse(r.check_password(""))

    def test_set_password_e_check_password_funcionam(self):
        """O que justifica herdar AbstractBaseUser: hash de senha de graça."""
        r = Responsavel.objects.create(
            escola=self.escola_a, nome="Maria", email="maria@example.com"
        )
        r.set_password("SenhaForte!2026")
        r.save(update_fields=["password"])
        r.refresh_from_db()
        self.assertTrue(r.check_password("SenhaForte!2026"))
        self.assertFalse(r.check_password("errada"))
        # Hash, nunca texto puro.
        self.assertNotIn("SenhaForte", r.password)


class ResponsavelAlunoTests(_PortalSetup):
    def setUp(self) -> None:
        self.responsavel = Responsavel.objects.create(
            escola=self.escola_a, nome="Maria", email="maria@example.com"
        )

    def test_vinculo_unico_por_par(self):
        aluno = self._aluno("Ana")
        ResponsavelAluno.objects.create(responsavel=self.responsavel, aluno=aluno)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                ResponsavelAluno.objects.create(
                    responsavel=self.responsavel, aluno=aluno
                )

    def test_um_responsavel_para_varios_alunos(self):
        ana = self._aluno("Ana")
        bruno = self._aluno("Bruno")
        ResponsavelAluno.objects.create(responsavel=self.responsavel, aluno=ana)
        ResponsavelAluno.objects.create(responsavel=self.responsavel, aluno=bruno)
        self.assertEqual(self.responsavel.vinculos.count(), 2)
        self.assertEqual(
            set(self.responsavel.alunos.values_list("nome_completo", flat=True)),
            {"Ana", "Bruno"},
        )

    def test_varios_responsaveis_para_um_aluno(self):
        """O M2M resolve o 'múltiplos responsáveis' que estava pendente."""
        ana = self._aluno("Ana")
        pai = Responsavel.objects.create(
            escola=self.escola_a, nome="José", email="jose@example.com"
        )
        ResponsavelAluno.objects.create(responsavel=self.responsavel, aluno=ana)
        ResponsavelAluno.objects.create(responsavel=pai, aluno=ana)
        self.assertEqual(ana.responsaveis.count(), 2)

    def test_clean_recusa_vinculo_entre_escolas(self):
        """Última linha de defesa: o escopo do portal parte deste vínculo."""
        aluno_b = self._aluno("De outra escola", escola=self.escola_b)
        vinculo = ResponsavelAluno(responsavel=self.responsavel, aluno=aluno_b)
        with self.assertRaises(ValidationError) as ctx:
            vinculo.full_clean()
        self.assertIn("aluno", ctx.exception.message_dict)

    def test_clean_aceita_vinculo_na_mesma_escola(self):
        aluno = self._aluno("Ana")
        vinculo = ResponsavelAluno(responsavel=self.responsavel, aluno=aluno)
        vinculo.full_clean()

    def test_responsavel_com_vinculo_nao_pode_ser_apagado(self):
        """PROTECT: desvincular é ação explícita, não efeito colateral."""
        aluno = self._aluno("Ana")
        ResponsavelAluno.objects.create(responsavel=self.responsavel, aluno=aluno)
        from django.db.models import ProtectedError

        with self.assertRaises(ProtectedError):
            self.responsavel.delete()
