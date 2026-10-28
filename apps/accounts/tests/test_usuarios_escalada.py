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

    def test_secretaria_edita_outra_conta_de_direcao_da_propria_escola(self):
        """Invertido em out/2026 — antes era 403; ver o docstring da classe.

        A direção passou a gerenciar os próprios pares pra não depender do
        `/admin/`. O movimento é lateral: secretaria e diretor são aliases
        em `apps/common/permissions.py` e já tinham escrita total sobre a
        escola. O que fecha o laço do takeover descrito acima é o teste
        vizinho, que mantém a conta do **admin** intocável — e é ela que
        alcança as outras escolas.
        """
        self._login(self.secretaria_a)
        resp = self.client.patch(
            self._url(self.diretor_a.id),
            {"email": "nova.diretora@example.com"},
            format="json",
        )
        self.assertEqual(resp.status_code, 200, resp.data)
        self.diretor_a.refresh_from_db()
        self.assertEqual(self.diretor_a.email, "nova.diretora@example.com")

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

    def test_secretaria_dispara_reset_em_conta_de_direcao_da_propria_escola(self):
        """Invertido junto com a edição acima (out/2026).

        O link vai pro email **do alvo**, não pro de quem dispara, então
        isto não entrega a conta a ninguém — é o que torna o reset seguro
        de delegar, ao contrário de definir `password` direto, que segue
        sendo só do admin.
        """
        self._login(self.secretaria_a)
        resp = self.client.post(
            f"/api/v1/usuarios/{self.diretor_a.id}/enviar-reset-senha/"
        )
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [self.diretor_a.email])

    def test_secretaria_nao_dispara_reset_na_conta_do_admin(self):
        """A metade que NÃO foi invertida — é aqui que o takeover morre."""
        self._login(self.secretaria_a)
        resp = self.client.post(
            f"/api/v1/usuarios/{self.admin.id}/enviar-reset-senha/"
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


class GestaoDePelaDirecaoTests(_UsuarioEscaladaSetup):
    """O que a fatia de out/2026 abriu, e as linhas que ela manteve.

    A direção passou a cadastrar e gerenciar os próprios pares pra não
    depender do `/admin/` do Django (item 10 do roadmap). Cada teste
    aqui é um lado dessa fronteira — os que passam a valer e os que
    continuam fechados.
    """

    @classmethod
    def setUpTestData(cls) -> None:
        super().setUpTestData()
        # Admin COM escola preenchida. O `cls.admin` do setup base tem
        # `escola=None`, então o `get_queryset` da secretaria já o
        # esconde e a resposta sai 404 pelo escopo — o que faz o guard
        # `_checar_alvo_privilegiado` passar sem ser exercitado. Isto
        # apareceu em teste de mutação: apagar o guard não reprovava
        # nada. Com um admin dentro da escola o alvo é alcançável pelo
        # queryset, e só o guard separa.
        cls.admin_na_escola_a = Usuario.objects.create_user(
            username="adm_a",
            password=SENHA_VALIDA,
            email="adm_a@diariodiniz.local",
            perfil=Usuario.Perfil.ADMIN,
            escola=cls.escola_a,
        )

    def test_secretaria_nao_edita_admin_alcancavel_pelo_queryset(self):
        """403 exato, não `(403, 404)`: aqui é o guard que recusa.

        Sem a asserção estrita o teste passaria pelo escopo de escola e
        mediria a coisa errada.
        """
        self._login(self.secretaria_a)
        resp = self.client.patch(
            self._url(self.admin_na_escola_a.id),
            {"email": "atacante@example.com"},
            format="json",
        )
        self.assertEqual(resp.status_code, 403, resp.data)
        self.admin_na_escola_a.refresh_from_db()
        self.assertEqual(
            self.admin_na_escola_a.email, "adm_a@diariodiniz.local"
        )

    def test_secretaria_nao_reseta_senha_de_admin_alcancavel(self):
        self._login(self.secretaria_a)
        resp = self.client.post(
            f"/api/v1/usuarios/{self.admin_na_escola_a.id}/enviar-reset-senha/"
        )
        self.assertEqual(resp.status_code, 403, resp.data)
        self.assertEqual(len(mail.outbox), 0)

    def test_secretaria_nao_apaga_admin_alcancavel(self):
        self._login(self.secretaria_a)
        resp = self.client.delete(self._url(self.admin_na_escola_a.id))
        self.assertEqual(resp.status_code, 403, resp.data)
        self.assertTrue(
            Usuario.objects.filter(pk=self.admin_na_escola_a.pk).exists()
        )

    def test_secretaria_cria_conta_de_direcao_na_propria_escola(self):
        self._login(self.secretaria_a)
        resp = self.client.post(
            "/api/v1/usuarios/",
            {
                "username": "nova_sec",
                "email": "nova.sec@example.com",
                "perfil": Usuario.Perfil.SECRETARIA,
                "escola": self.escola_a.id,
            },
            format="json",
        )
        self.assertEqual(resp.status_code, 201, resp.data)
        criado = Usuario.objects.get(username="nova_sec")
        self.assertEqual(criado.perfil, Usuario.Perfil.SECRETARIA)
        self.assertEqual(criado.escola_id, self.escola_a.id)

    def test_conta_criada_sem_senha_nasce_sem_senha_utilizavel(self):
        """O acesso chega pelo link de redefinição, não por senha digitada.

        Sem o `set_unusable_password`, o hash ficaria em string vazia —
        que não casa com senha nenhuma, mas também não é o marcador que
        `has_usable_password()` entende, e a tela não teria como dizer
        se a conta já foi ativada.
        """
        self._login(self.secretaria_a)
        self.client.post(
            "/api/v1/usuarios/",
            {
                "username": "sem_senha",
                "email": "sem.senha@example.com",
                "perfil": Usuario.Perfil.INSPETOR,
                "escola": self.escola_a.id,
            },
            format="json",
        )
        self.assertFalse(
            Usuario.objects.get(username="sem_senha").has_usable_password()
        )

    def test_secretaria_promove_professor_a_coordenador(self):
        self._login(self.secretaria_a)
        resp = self.client.patch(
            self._url(self.professor_a.id),
            {"perfil": Usuario.Perfil.COORDENADOR},
            format="json",
        )
        self.assertEqual(resp.status_code, 200, resp.data)
        self.professor_a.refresh_from_db()
        self.assertEqual(self.professor_a.perfil, Usuario.Perfil.COORDENADOR)

    def test_secretaria_desativa_conta_de_quem_saiu_da_escola(self):
        """O caso urgente que motivou liberar `is_active`.

        Se só o admin global cortasse acesso, revogar o acesso de quem
        saiu viraria chamado externo — e revogação é a ação que menos
        pode esperar.
        """
        self._login(self.secretaria_a)
        resp = self.client.patch(
            self._url(self.diretor_a.id), {"is_active": False}, format="json"
        )
        self.assertEqual(resp.status_code, 200, resp.data)
        self.diretor_a.refresh_from_db()
        self.assertFalse(self.diretor_a.is_active)

    # --- As linhas que continuam fechadas ---

    def test_secretaria_nao_cria_conta_admin(self):
        self._login(self.secretaria_a)
        resp = self.client.post(
            "/api/v1/usuarios/",
            {
                "username": "backdoor",
                "email": "backdoor@example.com",
                "perfil": Usuario.Perfil.ADMIN,
                "escola": self.escola_a.id,
            },
            format="json",
        )
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn("perfil", resp.data)
        self.assertFalse(Usuario.objects.filter(username="backdoor").exists())

    def test_secretaria_nao_promove_terceiro_a_admin(self):
        self._login(self.secretaria_a)
        resp = self.client.patch(
            self._url(self.professor_a.id),
            {"perfil": Usuario.Perfil.ADMIN},
            format="json",
        )
        self.assertEqual(resp.status_code, 400, resp.data)
        self.professor_a.refresh_from_db()
        self.assertEqual(self.professor_a.perfil, Usuario.Perfil.PROFESSOR)

    def test_secretaria_nao_edita_a_conta_do_admin(self):
        self._login(self.secretaria_a)
        resp = self.client.patch(
            self._url(self.admin.id), {"is_active": False}, format="json"
        )
        self.assertIn(resp.status_code, (403, 404), resp.data)
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_active)

    def test_secretaria_nao_move_usuario_para_outra_escola(self):
        self._login(self.secretaria_a)
        resp = self.client.patch(
            self._url(self.professor_a.id),
            {"escola": self.escola_b.id},
            format="json",
        )
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn("escola", resp.data)
        self.professor_a.refresh_from_db()
        self.assertEqual(self.professor_a.escola_id, self.escola_a.id)

    def test_secretaria_nao_altera_o_proprio_perfil(self):
        self._login(self.secretaria_a)
        resp = self.client.patch(
            self._url(self.secretaria_a.id),
            {"perfil": Usuario.Perfil.DIRETOR},
            format="json",
        )
        self.assertEqual(resp.status_code, 400, resp.data)
        self.secretaria_a.refresh_from_db()
        self.assertEqual(self.secretaria_a.perfil, Usuario.Perfil.SECRETARIA)

    def test_secretaria_nao_desativa_a_propria_conta(self):
        """Auto-tranco: dentro da escola não sobraria quem destrancasse."""
        self._login(self.secretaria_a)
        resp = self.client.patch(
            self._url(self.secretaria_a.id), {"is_active": False}, format="json"
        )
        self.assertEqual(resp.status_code, 400, resp.data)
        self.secretaria_a.refresh_from_db()
        self.assertTrue(self.secretaria_a.is_active)

    def test_secretaria_nao_gerencia_conta_de_outra_escola(self):
        self._login(self.secretaria_a)
        resp = self.client.patch(
            self._url(self.professor_b.id),
            {"perfil": Usuario.Perfil.COORDENADOR},
            format="json",
        )
        self.assertEqual(resp.status_code, 404, resp.data)
        self.professor_b.refresh_from_db()
        self.assertEqual(self.professor_b.perfil, Usuario.Perfil.PROFESSOR)
