"""Testes de escalada de privilégio e IDOR no `UsuarioViewSet`.

Contexto: o ViewSet é liberado pra `IsAdminOrDiretor`, que inclui
`secretaria` e `coordenador` como aliases de diretor. O `UsuarioSerializer`
expõe `perfil`, `password`, `escola` e `is_active` como graváveis, e o
queryset não era escopado por escola. A combinação permitia que qualquer
conta de nível-diretor:

1. se promovesse a `admin` (bypass total em todas as permission classes);
2. definisse a senha de qualquer outro usuário, inclusive do admin;
3. editasse usuários de outra escola;
4. trocasse o email do admin e, em seguida, disparasse o link de
   redefinição pra própria caixa.

Os quatro são takeover da conta mais privilegiada do sistema, exploráveis
com uma escola só. Estes testes travam o comportamento correto.
"""
from django.core import mail
from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import Usuario
from apps.accounts.views import ResetSenhaThrottle
from apps.escola.models import Escola

SENHA_VALIDA = "SenhaForte!2026"


class _UsuarioEscaladaSetup(TestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        cls.escola_a = Escola.objects.create(nome="Escola A")
        cls.escola_b = Escola.objects.create(nome="Escola B")
        cls.admin = Usuario.objects.create_user(
            username="adm",
            password=SENHA_VALIDA,
            email="adm@diariodiniz.local",
            perfil=Usuario.Perfil.ADMIN,
        )
        cls.secretaria_a = Usuario.objects.create_user(
            username="sec_a",
            password=SENHA_VALIDA,
            email="sec_a@diariodiniz.local",
            perfil=Usuario.Perfil.SECRETARIA,
            escola=cls.escola_a,
        )
        cls.diretor_a = Usuario.objects.create_user(
            username="dir_a",
            password=SENHA_VALIDA,
            email="dir_a@diariodiniz.local",
            perfil=Usuario.Perfil.DIRETOR,
            escola=cls.escola_a,
        )
        cls.professor_a = Usuario.objects.create_user(
            username="prof_a",
            password=SENHA_VALIDA,
            email="prof_a@diariodiniz.local",
            perfil=Usuario.Perfil.PROFESSOR,
            escola=cls.escola_a,
        )
        cls.professor_b = Usuario.objects.create_user(
            username="prof_b",
            password=SENHA_VALIDA,
            email="prof_b@diariodiniz.local",
            perfil=Usuario.Perfil.PROFESSOR,
            escola=cls.escola_b,
        )

    def setUp(self) -> None:
        self.client = APIClient()
        mail.outbox = []

    def _login(self, usuario) -> None:
        token = RefreshToken.for_user(usuario).access_token
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def _url(self, usuario_id: int) -> str:
        return f"/api/v1/usuarios/{usuario_id}/"


class EscaladaDePerfilTests(_UsuarioEscaladaSetup):
    def test_secretaria_nao_se_promove_a_admin(self):
        """O vetor mais direto: PATCH no próprio perfil."""
        self._login(self.secretaria_a)
        resp = self.client.patch(
            self._url(self.secretaria_a.id), {"perfil": "admin"}, format="json"
        )
        self.assertEqual(resp.status_code, 400, resp.data)
        self.secretaria_a.refresh_from_db()
        self.assertEqual(self.secretaria_a.perfil, Usuario.Perfil.SECRETARIA)

    def test_diretor_nao_promove_terceiro_a_admin(self):
        self._login(self.diretor_a)
        resp = self.client.patch(
            self._url(self.professor_a.id), {"perfil": "admin"}, format="json"
        )
        self.assertEqual(resp.status_code, 400, resp.data)
        self.professor_a.refresh_from_db()
        self.assertEqual(self.professor_a.perfil, Usuario.Perfil.PROFESSOR)

    def test_secretaria_nao_cria_usuario_admin(self):
        """Criar uma conta admin nova é escalada pela porta de trás."""
        self._login(self.secretaria_a)
        resp = self.client.post(
            "/api/v1/usuarios/",
            {
                "username": "novo_adm",
                "email": "novo_adm@diariodiniz.local",
                "perfil": "admin",
                "password": SENHA_VALIDA,
            },
            format="json",
        )
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertFalse(Usuario.objects.filter(username="novo_adm").exists())

    def test_admin_pode_mudar_perfil(self):
        """O fix não pode engessar quem é admin de verdade."""
        self._login(self.admin)
        resp = self.client.patch(
            self._url(self.professor_a.id), {"perfil": "inspetor"}, format="json"
        )
        self.assertEqual(resp.status_code, 200, resp.data)
        self.professor_a.refresh_from_db()
        self.assertEqual(self.professor_a.perfil, Usuario.Perfil.INSPETOR)


class TrocaDeSenhaDeTerceiroTests(_UsuarioEscaladaSetup):
    def test_secretaria_nao_troca_senha_do_admin(self):
        """Takeover direto: define a senha do admin e loga como ele."""
        self._login(self.secretaria_a)
        resp = self.client.patch(
            self._url(self.admin.id), {"password": "Invadida!2026x"}, format="json"
        )
        self.assertIn(resp.status_code, (400, 403, 404), resp.data)
        self.admin.refresh_from_db()
        self.assertFalse(self.admin.check_password("Invadida!2026x"))
        self.assertTrue(self.admin.check_password(SENHA_VALIDA))

    def test_secretaria_nao_troca_senha_de_professor(self):
        """Mesmo alvo sem privilégio: senha de terceiro é só do admin.

        A direção tem o caminho correto pra isso — a action
        `enviar-reset-senha`, que manda o link pro email do próprio alvo
        sem nunca expor nem definir a senha.
        """
        self._login(self.secretaria_a)
        resp = self.client.patch(
            self._url(self.professor_a.id),
            {"password": "Invadida!2026x"},
            format="json",
        )
        self.assertEqual(resp.status_code, 400, resp.data)
        self.professor_a.refresh_from_db()
        self.assertFalse(self.professor_a.check_password("Invadida!2026x"))

    def test_admin_pode_trocar_senha_de_terceiro(self):
        self._login(self.admin)
        resp = self.client.patch(
            self._url(self.professor_a.id),
            {"password": "DefinidaPeloAdmin!26"},
            format="json",
        )
        self.assertEqual(resp.status_code, 200, resp.data)
        self.professor_a.refresh_from_db()
        self.assertTrue(
            self.professor_a.check_password("DefinidaPeloAdmin!26")
        )


class EscopoPorEscolaTests(_UsuarioEscaladaSetup):
    def test_secretaria_nao_ve_usuario_de_outra_escola(self):
        self._login(self.secretaria_a)
        resp = self.client.get("/api/v1/usuarios/")
        self.assertEqual(resp.status_code, 200)
        dados = resp.data["results"] if "results" in resp.data else resp.data
        ids = {u["id"] for u in dados}
        self.assertNotIn(self.professor_b.id, ids)
        self.assertNotIn(self.admin.id, ids, "admin global não é da escola")

    def test_secretaria_nao_edita_usuario_de_outra_escola(self):
        self._login(self.secretaria_a)
        resp = self.client.patch(
            self._url(self.professor_b.id),
            {"first_name": "Invadido"},
            format="json",
        )
        self.assertEqual(resp.status_code, 404, resp.data)
        self.professor_b.refresh_from_db()
        self.assertNotEqual(self.professor_b.first_name, "Invadido")

    def test_admin_continua_vendo_todas_as_escolas(self):
        self._login(self.admin)
        resp = self.client.get("/api/v1/usuarios/")
        self.assertEqual(resp.status_code, 200)
        dados = resp.data["results"] if "results" in resp.data else resp.data
        ids = {u["id"] for u in dados}
        self.assertIn(self.professor_a.id, ids)
        self.assertIn(self.professor_b.id, ids)


class HijackPorEmailTests(_UsuarioEscaladaSetup):
    """O caminho indireto, que fecha o laço com a action de reset.

    Sem bloquear a edição de conta privilegiada, a secretaria trocava o
    email do admin pro seu próprio, disparava `enviar-reset-senha` e
    recebia o link de redefinição na própria caixa — takeover sem nunca
    tocar no campo `password`.
    """

    def test_secretaria_nao_troca_email_do_admin(self):
        self._login(self.secretaria_a)
        resp = self.client.patch(
            self._url(self.admin.id),
            {"email": "atacante@example.com"},
            format="json",
        )
        self.assertIn(resp.status_code, (403, 404), resp.data)
        self.admin.refresh_from_db()
        self.assertEqual(self.admin.email, "adm@diariodiniz.local")

    def test_secretaria_nao_edita_outra_conta_de_direcao(self):
        self._login(self.secretaria_a)
        resp = self.client.patch(
            self._url(self.diretor_a.id),
            {"email": "atacante@example.com"},
            format="json",
        )
        self.assertIn(resp.status_code, (403, 404), resp.data)
        self.diretor_a.refresh_from_db()
        self.assertEqual(self.diretor_a.email, "dir_a@diariodiniz.local")

    def test_secretaria_edita_a_propria_conta(self):
        """Mexer na própria conta continua liberado — não é escalada."""
        self._login(self.secretaria_a)
        resp = self.client.patch(
            self._url(self.secretaria_a.id),
            {"first_name": "Maria"},
            format="json",
        )
        self.assertEqual(resp.status_code, 200, resp.data)
        self.secretaria_a.refresh_from_db()
        self.assertEqual(self.secretaria_a.first_name, "Maria")

    def test_secretaria_nao_dispara_reset_em_conta_de_direcao(self):
        """Mesmo sem editar o email, reset de conta privilegiada é do admin."""
        self._login(self.secretaria_a)
        resp = self.client.post(
            f"/api/v1/usuarios/{self.diretor_a.id}/enviar-reset-senha/"
        )
        self.assertIn(resp.status_code, (403, 404), resp.data)
        self.assertEqual(len(mail.outbox), 0)


class FluxoCriarProfessorTests(_UsuarioEscaladaSetup):
    """O fix não pode quebrar o cadastro de professor pela direção.

    `ProfessorFormDialog` faz `POST /usuarios/` (perfil=professor, escola,
    password) e depois `PATCH /usuarios/:id` (first_name, last_name). É o
    fluxo do dia a dia da secretaria.
    """

    def test_secretaria_cria_usuario_professor_e_completa_o_nome(self):
        self._login(self.secretaria_a)
        resp = self.client.post(
            "/api/v1/usuarios/",
            {
                "username": "novo_prof",
                "email": "novo_prof@diariodiniz.local",
                "perfil": "professor",
                "escola": self.escola_a.id,
                "password": SENHA_VALIDA,
            },
            format="json",
        )
        self.assertEqual(resp.status_code, 201, resp.data)
        novo_id = resp.data["id"]

        resp = self.client.patch(
            self._url(novo_id),
            {"first_name": "Ana", "last_name": "Silva"},
            format="json",
        )
        self.assertEqual(resp.status_code, 200, resp.data)
        novo = Usuario.objects.get(pk=novo_id)
        self.assertEqual(novo.perfil, Usuario.Perfil.PROFESSOR)
        self.assertEqual(novo.escola_id, self.escola_a.id)
        self.assertEqual(novo.first_name, "Ana")
        self.assertTrue(novo.check_password(SENHA_VALIDA))

    def test_secretaria_nao_cria_usuario_em_outra_escola(self):
        self._login(self.secretaria_a)
        resp = self.client.post(
            "/api/v1/usuarios/",
            {
                "username": "prof_alheio",
                "email": "prof_alheio@diariodiniz.local",
                "perfil": "professor",
                "escola": self.escola_b.id,
                "password": SENHA_VALIDA,
            },
            format="json",
        )
        self.assertEqual(resp.status_code, 400, resp.data)


class ResetSenhaThrottleTests(_UsuarioEscaladaSetup):
    """Rate limit da action de reset.

    Sob `TESTING` o rate é `None` (desligado) pra não poluir a suíte, então
    aqui ele é reativado à mão. `override_settings` **não serve**:
    `SimpleRateThrottle.THROTTLE_RATES` é atributo de classe avaliado no
    import, então mudar `REST_FRAMEWORK` depois não alcança o throttle.
    Mesmo padrão já usado pro throttle do login em `test_security.py`.
    """

    def setUp(self) -> None:
        super().setUp()
        self._rate_original = ResetSenhaThrottle.THROTTLE_RATES
        ResetSenhaThrottle.THROTTLE_RATES = {
            **self._rate_original,
            "reset_senha": "2/min",
        }
        # LocMemCache persiste entre testes do mesmo processo; sem limpar,
        # a contagem de um teste vazaria pro próximo.
        cache.clear()

    def tearDown(self) -> None:
        cache.clear()
        ResetSenhaThrottle.THROTTLE_RATES = self._rate_original

    def _disparar(self):
        return self.client.post(
            f"/api/v1/usuarios/{self.professor_a.id}/enviar-reset-senha/"
        )

    def test_estourar_o_limite_devolve_429(self):
        self._login(self.diretor_a)
        self.assertEqual(self._disparar().status_code, 200)
        self.assertEqual(self._disparar().status_code, 200)
        # Terceira dentro do mesmo minuto: barrada.
        self.assertEqual(self._disparar().status_code, 429)
        # E não mandou email na barrada.
        self.assertEqual(len(mail.outbox), 2)

    def test_limite_e_por_usuario(self):
        """Um diretor no limite não trava o outro — a chave é o usuário."""
        self._login(self.diretor_a)
        self._disparar()
        self._disparar()
        self.assertEqual(self._disparar().status_code, 429)

        self._login(self.admin)
        self.assertEqual(self._disparar().status_code, 200)


class EscolaNulaTests(_UsuarioEscaladaSetup):
    """O guard antigo comparava `request.user.escola_id != usuario.escola_id`.

    Com os dois lados nulos, `None != None` é falso e a comparação
    liberava. `Usuario.escola` é `null=True`, então a conta não-admin sem
    escola é um estado alcançável — e o próprio `usePermissoes` no
    frontend trata esse caso como algo a se defender. O escopo por
    queryset resolve: sem escola, não vê ninguém.
    """

    @classmethod
    def setUpTestData(cls) -> None:
        super().setUpTestData()
        cls.secretaria_sem_escola = Usuario.objects.create_user(
            username="sec_sem_escola",
            password=SENHA_VALIDA,
            email="sec_sem@diariodiniz.local",
            perfil=Usuario.Perfil.SECRETARIA,
        )
        cls.professor_sem_escola = Usuario.objects.create_user(
            username="prof_sem_escola",
            password=SENHA_VALIDA,
            email="prof_sem@diariodiniz.local",
            perfil=Usuario.Perfil.PROFESSOR,
        )

    def test_nao_admin_sem_escola_nao_ve_ninguem(self):
        self._login(self.secretaria_sem_escola)
        resp = self.client.get("/api/v1/usuarios/")
        self.assertEqual(resp.status_code, 200)
        dados = resp.data["results"] if "results" in resp.data else resp.data
        self.assertEqual(dados, [])

    def test_nao_admin_sem_escola_nao_edita_outro_sem_escola(self):
        self._login(self.secretaria_sem_escola)
        resp = self.client.patch(
            self._url(self.professor_sem_escola.id),
            {"first_name": "Invadido"},
            format="json",
        )
        self.assertEqual(resp.status_code, 404, resp.data)
        self.professor_sem_escola.refresh_from_db()
        self.assertNotEqual(self.professor_sem_escola.first_name, "Invadido")

    def test_nao_admin_sem_escola_nao_dispara_reset(self):
        self._login(self.secretaria_sem_escola)
        resp = self.client.post(
            f"/api/v1/usuarios/{self.professor_sem_escola.id}/enviar-reset-senha/"
        )
        self.assertEqual(resp.status_code, 404, resp.data)
        self.assertEqual(len(mail.outbox), 0)

    def test_nao_admin_sem_escola_nao_cria_usuario(self):
        self._login(self.secretaria_sem_escola)
        resp = self.client.post(
            "/api/v1/usuarios/",
            {
                "username": "novo",
                "email": "novo@diariodiniz.local",
                "perfil": "professor",
                "password": SENHA_VALIDA,
            },
            format="json",
        )
        self.assertEqual(resp.status_code, 400, resp.data)
