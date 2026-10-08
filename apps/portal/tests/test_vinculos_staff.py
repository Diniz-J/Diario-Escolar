"""Testes da escrita do vínculo responsável × aluno (fatia 4).

`ResponsavelAluno` decide quem lê o boletim, as ocorrências e os
comunicados de qual aluno. Um vínculo indevido não é um registro errado, é
acesso indevido aos dados de uma criança — então o escopo de escola tem
teste em todas as direções que podem furar, inclusive a que o `clean()` do
model não cobre.
"""
from django.urls import reverse
from rest_framework.test import APIClient
from django.test import TestCase

from apps.accounts.models import Usuario
from apps.escola.models import Aluno, Escola, Professor, Turma
from apps.portal.models import Responsavel, ResponsavelAluno

URL_LISTA = "/api/v1/vinculos-responsavel/"


class _VinculoSetup(TestCase):
    """Duas escolas, cada uma com responsável e aluno. Helpers sem testes."""

    @classmethod
    def setUpTestData(cls) -> None:
        cls.escola = Escola.objects.create(nome="Escola A")
        cls.outra = Escola.objects.create(nome="Escola B")
        cls.turma = cls._turma(cls.escola)
        cls.turma_outra = cls._turma(cls.outra)

        cls.aluno = cls._aluno("Ana Filha", cls.turma)
        cls.aluno_outra = cls._aluno("Beto Outro", cls.turma_outra)
        cls.responsavel = cls._responsavel(cls.escola, "mae@example.com")
        cls.responsavel_outra = cls._responsavel(cls.outra, "pai.b@example.com")

        cls.diretora = Usuario.objects.create_user(
            username="dir",
            password="x",
            perfil=Usuario.Perfil.DIRETOR,
            escola=cls.escola,
        )
        cls.admin = Usuario.objects.create_user(
            username="adm", password="x", perfil=Usuario.Perfil.ADMIN
        )
        prof_usuario = Usuario.objects.create_user(
            username="prof",
            password="x",
            perfil=Usuario.Perfil.PROFESSOR,
            escola=cls.escola,
        )
        cls.professor_user = prof_usuario
        Professor.objects.create(usuario=prof_usuario, escola=cls.escola)
        cls.inspetor = Usuario.objects.create_user(
            username="insp",
            password="x",
            perfil=Usuario.Perfil.INSPETOR,
            escola=cls.escola,
        )

    @staticmethod
    def _turma(escola):
        return Turma.objects.create(
            escola=escola,
            nome="1º A",
            turno=Turma.Turno.MATUTINO,
            ano_letivo=2026,
        )

    @staticmethod
    def _aluno(nome, turma, ativo=True):
        return Aluno.objects.create(
            escola=turma.escola,
            matricula=f"M{Aluno.objects.count() + 1}",
            nome_completo=nome,
            turma=turma,
            ativo=ativo,
        )

    @staticmethod
    def _responsavel(escola, email):
        return Responsavel.objects.create(escola=escola, nome=email, email=email)

    def setUp(self) -> None:
        self.client = APIClient()
        self.client.force_authenticate(self.diretora)

    def _vincular(self, responsavel, aluno):
        return self.client.post(
            URL_LISTA,
            {"responsavel": responsavel.pk, "aluno": aluno.pk},
            format="json",
        )


class CriacaoTests(_VinculoSetup):
    def test_secretaria_vincula_responsavel_a_aluno(self):
        resp = self._vincular(self.responsavel, self.aluno)

        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data["aluno_nome"], "Ana Filha")
        self.assertEqual(resp.data["aluno_turma"], "1º A")
        self.assertTrue(
            ResponsavelAluno.objects.filter(
                responsavel=self.responsavel, aluno=self.aluno
            ).exists()
        )

    def test_segundo_responsavel_do_mesmo_aluno(self):
        """O caso que a frente toda existe pra permitir: mãe e pai."""
        pai = self._responsavel(self.escola, "pai@example.com")
        self.assertEqual(self._vincular(self.responsavel, self.aluno).status_code, 201)

        self.assertEqual(self._vincular(pai, self.aluno).status_code, 201)

        self.assertEqual(self.aluno.responsaveis.count(), 2)

    def test_vinculo_duplicado_devolve_400(self):
        """O unique precisa virar 400, não IntegrityError em 500."""
        self._vincular(self.responsavel, self.aluno)

        resp = self._vincular(self.responsavel, self.aluno)

        self.assertEqual(resp.status_code, 400)

    def test_aluno_inativo_pode_ser_vinculado(self):
        """`PORTAL.md`: aluno desativado mantém o histórico pro responsável."""
        inativo = self._aluno("Ana Transferida", self.turma, ativo=False)

        self.assertEqual(self._vincular(self.responsavel, inativo).status_code, 201)


class EscopoDeEscolaTests(_VinculoSetup):
    """As quatro direções em que o escopo pode furar."""

    def test_responsavel_de_outra_escola_e_recusado(self):
        resp = self._vincular(self.responsavel_outra, self.aluno)

        self.assertEqual(resp.status_code, 400)
        self.assertIn("responsavel", resp.data)

    def test_aluno_de_outra_escola_e_recusado(self):
        resp = self._vincular(self.responsavel, self.aluno_outra)

        self.assertEqual(resp.status_code, 400)
        self.assertIn("aluno", resp.data)

    def test_par_consistente_de_outra_escola_e_recusado(self):
        """O furo que o `clean()` do model NÃO pega.

        Responsável e aluno são os dois da Escola B, então `clean()` não
        reclama — eles concordam entre si. Só o guard de IDOR por lado
        barra a diretora da Escola A de criar esse vínculo.
        """
        resp = self._vincular(self.responsavel_outra, self.aluno_outra)

        self.assertEqual(resp.status_code, 400)
        self.assertEqual(
            ResponsavelAluno.objects.filter(aluno=self.aluno_outra).count(), 0
        )

    def test_admin_global_vincula_em_qualquer_escola_mas_nao_cruzado(self):
        self.client.force_authenticate(self.admin)

        self.assertEqual(
            self._vincular(self.responsavel_outra, self.aluno_outra).status_code, 201
        )
        # Mesmo pro admin, cruzar escola é recusado — pelo `clean()`.
        cruzado = self._vincular(self.responsavel, self.aluno_outra)
        self.assertEqual(cruzado.status_code, 400)
        self.assertIn("aluno", cruzado.data)

    def test_listagem_nao_mostra_vinculo_de_outra_escola(self):
        ResponsavelAluno.objects.create(
            responsavel=self.responsavel_outra, aluno=self.aluno_outra
        )

        resp = self.client.get(
            URL_LISTA, {"responsavel": self.responsavel_outra.pk}
        )

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data, [])

    def test_delete_de_vinculo_de_outra_escola_da_404(self):
        alheio = ResponsavelAluno.objects.create(
            responsavel=self.responsavel_outra, aluno=self.aluno_outra
        )

        resp = self.client.delete(f"{URL_LISTA}{alheio.pk}/")

        self.assertEqual(resp.status_code, 404)
        self.assertTrue(ResponsavelAluno.objects.filter(pk=alheio.pk).exists())

    def test_vinculo_cruzado_preexistente_nao_aparece_pra_ninguem(self):
        """Rede contra dado inválido já no banco.

        `objects.create()` não passa por `clean()`, então um vínculo
        cruzando escola pode ter entrado por shell. Filtrar só pelo
        responsável mostraria o nome do aluno alheio à diretora da escola
        do responsável.
        """
        cruzado = ResponsavelAluno.objects.create(
            responsavel=self.responsavel, aluno=self.aluno_outra
        )

        resp = self.client.get(URL_LISTA, {"responsavel": self.responsavel.pk})

        self.assertEqual(resp.status_code, 200)
        self.assertNotIn(cruzado.pk, [item["id"] for item in resp.data])


class RemocaoTests(_VinculoSetup):
    def test_secretaria_remove_vinculo(self):
        vinculo = ResponsavelAluno.objects.create(
            responsavel=self.responsavel, aluno=self.aluno
        )

        resp = self.client.delete(f"{URL_LISTA}{vinculo.pk}/")

        self.assertEqual(resp.status_code, 204)
        self.assertFalse(ResponsavelAluno.objects.filter(pk=vinculo.pk).exists())

    def test_remocao_fica_no_historico(self):
        """DELETE é real, mas o modelo é auditado — a deleção é registrada."""
        vinculo = ResponsavelAluno.objects.create(
            responsavel=self.responsavel, aluno=self.aluno
        )
        pk = vinculo.pk

        self.client.delete(f"{URL_LISTA}{pk}/")

        historico = ResponsavelAluno.history.filter(id=pk)
        self.assertTrue(historico.filter(history_type="-").exists())

    def test_sem_put_nem_patch(self):
        """Trocar um lado do par é outro vínculo, não edição deste."""
        vinculo = ResponsavelAluno.objects.create(
            responsavel=self.responsavel, aluno=self.aluno
        )
        url = f"{URL_LISTA}{vinculo.pk}/"

        for metodo in (self.client.put, self.client.patch):
            with self.subTest(metodo.__name__):
                resp = metodo(url, {"aluno": self.aluno.pk}, format="json")
                self.assertEqual(resp.status_code, 405)


class PermissaoTests(_VinculoSetup):
    def test_professor_e_inspetor_nao_acessam(self):
        """Critério da fatia: professor não acessa."""
        vinculo = ResponsavelAluno.objects.create(
            responsavel=self.responsavel, aluno=self.aluno
        )

        for user in (self.professor_user, self.inspetor):
            with self.subTest(user.perfil):
                self.client.force_authenticate(user)
                self.assertEqual(
                    self.client.get(
                        URL_LISTA, {"responsavel": self.responsavel.pk}
                    ).status_code,
                    403,
                )
                self.assertEqual(
                    self._vincular(self.responsavel, self.aluno).status_code, 403
                )
                self.assertEqual(
                    self.client.delete(f"{URL_LISTA}{vinculo.pk}/").status_code, 403
                )

    def test_anonimo_nao_acessa(self):
        self.client.force_authenticate(None)

        self.assertEqual(self.client.get(URL_LISTA).status_code, 401)


class EscopoObrigatorioTests(_VinculoSetup):
    def test_listagem_sem_filtro_e_recusada(self):
        """Mesma escolha dos endpoints matriz: escopo em vez de paginação."""
        resp = self.client.get(URL_LISTA)

        self.assertEqual(resp.status_code, 400)
        self.assertIn("detail", resp.data)

    def test_listagem_por_aluno_tambem_serve_de_escopo(self):
        ResponsavelAluno.objects.create(
            responsavel=self.responsavel, aluno=self.aluno
        )

        resp = self.client.get(URL_LISTA, {"aluno": self.aluno.pk})

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data), 1)

    def test_listagem_escopada_nao_faz_query_por_linha(self):
        """O dialog mostra nome e turma de cada filho: sem N+1."""
        for i in range(5):
            aluno = self._aluno(f"Filho {i}", self.turma)
            ResponsavelAluno.objects.create(
                responsavel=self.responsavel, aluno=aluno
            )

        with self.assertNumQueries(2):
            resp = self.client.get(
                URL_LISTA, {"responsavel": self.responsavel.pk}
            )

        self.assertEqual(len(resp.data), 5)
