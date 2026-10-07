"""Testes da listagem de responsáveis no staff (fatia 6b).

É a tela que a secretaria usa pra ver o estado do acesso e convidar, então
o que importa aqui é: escopo por escola, permissão de nível-diretor, e a
`situacao` dizer a verdade — mostrar "convidado" pra um convite que já
expirou faria a escola esperar por nada.
"""
from datetime import timedelta

from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from django.test import TestCase

from apps.accounts.models import Usuario
from apps.escola.models import Aluno, Escola, Turma
from apps.portal.models import ConviteResponsavel, Responsavel, ResponsavelAluno

SENHA = "SenhaForte!2026"


class _ListaSetup(TestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        cls.escola_a = Escola.objects.create(nome="Escola A")
        cls.escola_b = Escola.objects.create(nome="Escola B")
        cls.turma_a = Turma.objects.create(
            escola=cls.escola_a, nome="1º A", turno="matutino", ano_letivo=2026
        )
        cls.turma_b = Turma.objects.create(
            escola=cls.escola_b, nome="1º A", turno="matutino", ano_letivo=2026
        )
        cls.diretor = Usuario.objects.create_user(
            username="dir", password=SENHA, email="dir@a.com",
            perfil=Usuario.Perfil.DIRETOR, escola=cls.escola_a,
        )
        cls.professor = Usuario.objects.create_user(
            username="prof", password=SENHA, email="prof@a.com",
            perfil=Usuario.Perfil.PROFESSOR, escola=cls.escola_a,
        )
        cls.admin = Usuario.objects.create_user(
            username="adm", password=SENHA, email="adm@a.com",
            perfil=Usuario.Perfil.ADMIN,
        )

    def setUp(self) -> None:
        self.client = APIClient()

    def _login(self, usuario) -> None:
        token = RefreshToken.for_user(usuario).access_token
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def _url(self, **params) -> str:
        url = reverse("api_v1:responsavel-list")
        if params:
            url += "?" + "&".join(f"{k}={v}" for k, v in params.items())
        return url

    def _responsavel(self, nome, email, escola=None, ativo=True, com_senha=False):
        r = Responsavel.objects.create(
            escola=escola or self.escola_a, nome=nome, email=email, ativo=ativo
        )
        if com_senha:
            r.set_password(SENHA)
        else:
            r.set_unusable_password()
        r.save(update_fields=["password"])
        return r

    def _aluno(self, nome, escola=None, turma=None):
        escola = escola or self.escola_a
        return Aluno.objects.create(
            escola=escola,
            matricula=f"M{Aluno.objects.count() + 1}",
            nome_completo=nome,
            turma=turma or (self.turma_a if escola == self.escola_a else self.turma_b),
        )

    def _resultados(self, resp):
        return resp.data["results"] if "results" in resp.data else resp.data


class PermissaoTests(_ListaSetup):
    def test_nivel_diretor_lista(self):
        self._login(self.diretor)
        self.assertEqual(self.client.get(self._url()).status_code, 200)

    def test_professor_nao_lista(self):
        """Quem pode convidar é quem pode ver — e professor não convida."""
        self._login(self.professor)
        self.assertEqual(self.client.get(self._url()).status_code, 403)

    def test_anonimo_nao_lista(self):
        self.assertIn(self.client.get(self._url()).status_code, (401, 403))

    def test_listagem_e_somente_leitura(self):
        """Conta de usuário externo não nasce pela API do staff."""
        self._login(self.diretor)
        resp = self.client.post(
            self._url(), {"nome": "X", "email": "x@a.com"}, format="json"
        )
        self.assertEqual(resp.status_code, 405)


class EscopoTests(_ListaSetup):
    def test_diretor_nao_ve_responsavel_de_outra_escola(self):
        meu = self._responsavel("Da minha escola", "meu@a.com")
        self._responsavel("De outra", "outro@b.com", escola=self.escola_b)

        self._login(self.diretor)
        resp = self.client.get(self._url())
        ids = [r["id"] for r in self._resultados(resp)]
        self.assertEqual(ids, [meu.id])

    def test_admin_global_ve_as_duas_escolas(self):
        self._responsavel("Da A", "a@a.com")
        self._responsavel("Da B", "b@b.com", escola=self.escola_b)

        self._login(self.admin)
        resp = self.client.get(self._url())
        self.assertEqual(len(self._resultados(resp)), 2)

    def test_detalhe_de_outra_escola_da_404(self):
        alheio = self._responsavel("Alheio", "alheio@b.com", escola=self.escola_b)
        self._login(self.diretor)
        resp = self.client.get(
            reverse("api_v1:responsavel-detail", args=[alheio.id])
        )
        self.assertEqual(resp.status_code, 404)


class SituacaoTests(_ListaSetup):
    """A situação é derivada; mostrar a errada manda a secretaria pro lugar errado."""

    def _situacao_de(self, responsavel) -> str:
        self._login(self.diretor)
        resp = self.client.get(self._url())
        linha = next(
            r for r in self._resultados(resp) if r["id"] == responsavel.id
        )
        return linha["situacao"]

    def test_sem_convite(self):
        r = self._responsavel("Nunca convidado", "n@a.com")
        self.assertEqual(self._situacao_de(r), "sem_convite")

    def test_convidado(self):
        r = self._responsavel("Convidado", "c@a.com")
        ConviteResponsavel.gerar(r, ConviteResponsavel.Finalidade.CONVITE)
        self.assertEqual(self._situacao_de(r), "convidado")

    def test_convite_expirado(self):
        """Sete dias se passaram e o pai não usou: não é 'convidado'."""
        r = self._responsavel("Expirado", "e@a.com")
        convite, _ = ConviteResponsavel.gerar(
            r, ConviteResponsavel.Finalidade.CONVITE
        )
        ConviteResponsavel.objects.filter(pk=convite.pk).update(
            expira_em=timezone.now() - timedelta(days=1)
        )
        self.assertEqual(self._situacao_de(r), "convite_expirado")

    def test_ativo_quando_definiu_senha(self):
        r = self._responsavel("Ativo", "at@a.com", com_senha=True)
        self.assertEqual(self._situacao_de(r), "ativo")

    def test_inativo_tem_precedencia(self):
        """Conta desativada: convidar não é o próximo passo."""
        r = self._responsavel("Desativado", "d@a.com", ativo=False)
        ConviteResponsavel.gerar(r, ConviteResponsavel.Finalidade.CONVITE)
        self.assertEqual(self._situacao_de(r), "inativo")

    def test_convite_usado_nao_mantem_convidado(self):
        """Usou o link e definiu senha: a situação vira ativo, não convidado."""
        r = self._responsavel("Usou", "u@a.com")
        convite, _ = ConviteResponsavel.gerar(
            r, ConviteResponsavel.Finalidade.CONVITE
        )
        from apps.portal.services import definir_senha

        self.assertTrue(definir_senha(convite, SENHA))
        self.assertEqual(self._situacao_de(r), "ativo")

    def test_expira_em_do_convite_pendente_vem_na_resposta(self):
        r = self._responsavel("Convidado", "c@a.com")
        convite, _ = ConviteResponsavel.gerar(
            r, ConviteResponsavel.Finalidade.CONVITE
        )
        self._login(self.diretor)
        linha = self._resultados(self.client.get(self._url()))[0]
        self.assertIsNotNone(linha["convite_expira_em"])
        self.assertEqual(linha["id"], r.id)
        self.assertEqual(convite.responsavel_id, r.id)


class FiltroEBuscaTests(_ListaSetup):
    def test_filtro_por_situacao(self):
        sem = self._responsavel("Sem convite", "s@a.com")
        convidado = self._responsavel("Convidado", "c@a.com")
        ConviteResponsavel.gerar(convidado, ConviteResponsavel.Finalidade.CONVITE)
        ativo = self._responsavel("Ativo", "a@a.com", com_senha=True)

        self._login(self.diretor)
        for situacao, esperado in (
            ("sem_convite", sem),
            ("convidado", convidado),
            ("ativo", ativo),
        ):
            with self.subTest(situacao=situacao):
                resp = self.client.get(self._url(situacao=situacao))
                ids = [r["id"] for r in self._resultados(resp)]
                self.assertEqual(ids, [esperado.id])

    def test_situacao_invalida_da_400(self):
        self._login(self.diretor)
        resp = self.client.get(self._url(situacao="inventada"))
        self.assertEqual(resp.status_code, 400)
        self.assertIn("situacao", resp.data)

    def test_situacao_nao_alcanca_o_detalhe(self):
        """O filtro é da listagem; o detalhe não tem filtro nenhum.

        O DRF chama `filter_queryset` também no `retrieve`, por dentro do
        `get_object`. Com o filtro no `get_queryset`, pedir o detalhe com
        os filtros da tela na URL escondia um responsável que existe
        (404) ou reclamava de um valor inválido (400) numa rota que não
        filtra nada.
        """
        alvo = self._responsavel("Sem convite", "s@a.com")
        detalhe = reverse(
            "api_v1:responsavel-detail", kwargs={"pk": alvo.pk}
        )
        self._login(self.diretor)

        for params in ({}, {"situacao": "ativo"}, {"situacao": "xpto"}):
            with self.subTest(params=params):
                resp = self.client.get(detalhe, params)
                self.assertEqual(resp.status_code, 200)
                self.assertEqual(resp.data["id"], alvo.id)
                # A situação derivada continua sendo calculada: as
                # anotações seguem no `get_queryset`.
                self.assertEqual(resp.data["situacao"], "sem_convite")

    def test_busca_pelo_nome_do_aluno(self):
        """A secretaria procura 'o pai do João', não o nome do responsável."""
        r = self._responsavel("", "pai@a.com")
        aluno = self._aluno("João Pedro")
        ResponsavelAluno.objects.create(responsavel=r, aluno=aluno)
        self._responsavel("Outro", "outro@a.com")

        self._login(self.diretor)
        resp = self.client.get(self._url(search="João"))
        ids = [x["id"] for x in self._resultados(resp)]
        self.assertEqual(ids, [r.id])

    def test_alunos_vinculados_vem_na_resposta(self):
        r = self._responsavel("Mãe", "mae@a.com")
        for nome in ("Ana", "Bruno"):
            ResponsavelAluno.objects.create(
                responsavel=r, aluno=self._aluno(nome)
            )
        self._login(self.diretor)
        linha = self._resultados(self.client.get(self._url()))[0]
        nomes = {a["nome_completo"] for a in linha["alunos"]}
        self.assertEqual(nomes, {"Ana", "Bruno"})
        self.assertEqual(linha["alunos"][0]["turma"], "1º A")


class ConsultasTests(_ListaSetup):
    def test_numero_de_queries_nao_cresce_com_as_linhas(self):
        """Regressão de N+1.

        A situação de cada conta depende de convite pendente e de convite
        qualquer. Resolvido por linha, uma tela de 20 responsáveis faria 40
        queries extras — por isso as annotations usam `Exists`/`Subquery` e
        os alunos vêm por `prefetch_related`.
        """
        for i in range(3):
            r = self._responsavel(f"Resp {i}", f"r{i}@a.com")
            ResponsavelAluno.objects.create(
                responsavel=r, aluno=self._aluno(f"Aluno {i}")
            )
            ConviteResponsavel.gerar(r, ConviteResponsavel.Finalidade.CONVITE)

        self._login(self.diretor)
        with self.assertNumQueries(5) as ctx:
            resp = self.client.get(self._url())
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(self._resultados(resp)), 3)

        # Mais responsáveis não podem significar mais queries.
        for i in range(3, 9):
            r = self._responsavel(f"Resp {i}", f"r{i}@a.com")
            ResponsavelAluno.objects.create(
                responsavel=r, aluno=self._aluno(f"Aluno {i}")
            )
            ConviteResponsavel.gerar(r, ConviteResponsavel.Finalidade.CONVITE)

        with self.assertNumQueries(len(ctx.captured_queries)):
            resp = self.client.get(self._url())
        self.assertEqual(len(self._resultados(resp)), 9)
