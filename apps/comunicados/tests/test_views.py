"""Testes do `ComunicadoViewSet` — permissões, ciclo de vida e escopo.

Padrão do projeto: `APIRequestFactory` + `force_authenticate`, chamando o
ViewSet diretamente.
"""
from django.core import mail
from django.test import TestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.accounts.models import Usuario
from apps.comunicados.models import Comunicado, ComunicadoDestinatario
from apps.comunicados.views import ComunicadoViewSet
from apps.escola.models import Aluno, Escola, Turma


class _ComunicadoSetup(TestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        cls.factory = APIRequestFactory()
        cls.escola = Escola.objects.create(nome="Escola Teste")
        cls.outra_escola = Escola.objects.create(nome="Outra Escola")
        cls.turma = Turma.objects.create(
            escola=cls.escola,
            nome="1º A",
            turno=Turma.Turno.MATUTINO,
            ano_letivo=2026,
        )
        cls.turma_outra_escola = Turma.objects.create(
            escola=cls.outra_escola,
            nome="1º A",
            turno=Turma.Turno.MATUTINO,
            ano_letivo=2026,
        )
        cls.aluno = Aluno.objects.create(
            escola=cls.escola,
            matricula="A1",
            nome_completo="Ana Silva",
            turma=cls.turma,
            nome_responsavel="Maria Silva",
            email_responsavel="maria@example.com",
        )
        cls.usuarios = {
            "admin": Usuario.objects.create_user(
                username="adm", password="x", perfil=Usuario.Perfil.ADMIN
            ),
            "diretor": Usuario.objects.create_user(
                username="dir",
                password="x",
                perfil=Usuario.Perfil.DIRETOR,
                escola=cls.escola,
            ),
            "secretaria": Usuario.objects.create_user(
                username="sec",
                password="x",
                perfil=Usuario.Perfil.SECRETARIA,
                escola=cls.escola,
            ),
            "coordenador": Usuario.objects.create_user(
                username="coord",
                password="x",
                perfil=Usuario.Perfil.COORDENADOR,
                escola=cls.escola,
            ),
            "professor": Usuario.objects.create_user(
                username="prof",
                password="x",
                perfil=Usuario.Perfil.PROFESSOR,
                escola=cls.escola,
            ),
            "inspetor": Usuario.objects.create_user(
                username="insp",
                password="x",
                perfil=Usuario.Perfil.INSPETOR,
                escola=cls.escola,
            ),
        }

    def setUp(self) -> None:
        mail.outbox = []

    # -- helpers ------------------------------------------------------

    def _payload(self, **extra):
        base = {
            "titulo": "Reunião de pais",
            "mensagem": "Dia 20/10 às 19h.",
            "destino": Comunicado.Destino.ESCOLA,
        }
        base.update(extra)
        return base

    def _chamar(self, metodo, acao, usuario, *, pk=None, data=None, params=""):
        req = getattr(self.factory, metodo)(
            f"/{params}", data, format="json"
        ) if data is not None else getattr(self.factory, metodo)(f"/{params}")
        force_authenticate(req, user=usuario)
        view = ComunicadoViewSet.as_view({metodo: acao})
        return view(req, pk=pk) if pk is not None else view(req)

    def _criar(self, escola=None, **extra):
        comunicado = Comunicado.objects.create(
            escola=escola or self.escola,
            titulo=extra.pop("titulo", "Aviso"),
            mensagem=extra.pop("mensagem", "Conteúdo do aviso."),
            destino=extra.pop("destino", Comunicado.Destino.ESCOLA),
            **extra,
        )
        return comunicado


class ComunicadoPermissaoTests(_ComunicadoSetup):
    """Leitura: diretor + docente. Escrita e envio: só nível-diretor."""

    PERFIS_LEITURA = ("admin", "diretor", "secretaria", "coordenador", "professor", "inspetor")
    PERFIS_ESCRITA = ("admin", "diretor", "secretaria", "coordenador")
    PERFIS_SEM_ESCRITA = ("professor", "inspetor")

    def test_todos_os_perfis_leem_a_listagem(self):
        self._criar()
        for perfil in self.PERFIS_LEITURA:
            with self.subTest(perfil=perfil):
                resp = self._chamar("get", "list", self.usuarios[perfil])
                self.assertEqual(resp.status_code, 200)

    def test_nivel_diretor_cria(self):
        for perfil in self.PERFIS_ESCRITA:
            with self.subTest(perfil=perfil):
                usuario = self.usuarios[perfil]
                data = self._payload()
                if perfil == "admin":
                    # Admin global não tem escola vinculada: precisa mandar.
                    data["escola"] = self.escola.id
                resp = self._chamar("post", "create", usuario, data=data)
                self.assertEqual(resp.status_code, 201, resp.data)

    def test_docente_nao_cria(self):
        """Professor/inspetor acompanham, mas não publicam."""
        for perfil in self.PERFIS_SEM_ESCRITA:
            with self.subTest(perfil=perfil):
                resp = self._chamar(
                    "post", "create", self.usuarios[perfil], data=self._payload()
                )
                self.assertEqual(resp.status_code, 403)

    def test_docente_nao_envia(self):
        """A trava mais importante: docente não dispara email pra escola."""
        for perfil in self.PERFIS_SEM_ESCRITA:
            with self.subTest(perfil=perfil):
                comunicado = self._criar()
                resp = self._chamar(
                    "post", "enviar", self.usuarios[perfil], pk=comunicado.pk, data={}
                )
                self.assertEqual(resp.status_code, 403)
                self.assertEqual(len(mail.outbox), 0)

    def test_docente_nao_edita_nem_exclui(self):
        comunicado = self._criar()
        for perfil in self.PERFIS_SEM_ESCRITA:
            with self.subTest(perfil=perfil):
                resp = self._chamar(
                    "patch",
                    "partial_update",
                    self.usuarios[perfil],
                    pk=comunicado.pk,
                    data={"titulo": "Hackeado"},
                )
                self.assertEqual(resp.status_code, 403)
                resp = self._chamar(
                    "delete", "destroy", self.usuarios[perfil], pk=comunicado.pk
                )
                self.assertEqual(resp.status_code, 403)

    def test_docente_consulta_previa_e_destinatarios(self):
        """As actions de consulta são leitura — docente pode abrir a tela."""
        comunicado = self._criar()
        for perfil in self.PERFIS_SEM_ESCRITA:
            with self.subTest(perfil=perfil):
                resp = self._chamar(
                    "get", "previa", self.usuarios[perfil], pk=comunicado.pk
                )
                self.assertEqual(resp.status_code, 200)
                resp = self._chamar(
                    "get", "destinatarios", self.usuarios[perfil], pk=comunicado.pk
                )
                self.assertEqual(resp.status_code, 200)

    def test_anonimo_nao_acessa(self):
        resp = self._chamar("get", "list", None)
        self.assertIn(resp.status_code, (401, 403))


class ComunicadoCicloDeVidaTests(_ComunicadoSetup):
    def test_criar_nasce_rascunho_e_nao_envia(self):
        """Requisito central: salvar NUNCA dispara email."""
        resp = self._chamar(
            "post", "create", self.usuarios["diretor"], data=self._payload()
        )
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data["status"], Comunicado.Status.RASCUNHO)
        self.assertTrue(resp.data["editavel"])
        self.assertEqual(len(mail.outbox), 0)

    def test_criar_registra_autoria(self):
        resp = self._chamar(
            "post", "create", self.usuarios["diretor"], data=self._payload()
        )
        comunicado = Comunicado.objects.get(pk=resp.data["id"])
        self.assertEqual(comunicado.criado_por, self.usuarios["diretor"])
        self.assertIsNone(comunicado.enviado_por)

    def test_enviar_dispara_e_responde_202(self):
        comunicado = self._criar()
        resp = self._chamar(
            "post", "enviar", self.usuarios["diretor"], pk=comunicado.pk, data={}
        )
        self.assertEqual(resp.status_code, 202, resp.data)
        self.assertEqual(resp.data["status"], Comunicado.Status.ENVIADO)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["maria@example.com"])

    def test_enviar_duas_vezes_responde_409(self):
        comunicado = self._criar()
        primeira = self._chamar(
            "post", "enviar", self.usuarios["diretor"], pk=comunicado.pk, data={}
        )
        self.assertEqual(primeira.status_code, 202)

        segunda = self._chamar(
            "post", "enviar", self.usuarios["diretor"], pk=comunicado.pk, data={}
        )
        self.assertEqual(segunda.status_code, 409)
        self.assertEqual(len(mail.outbox), 1, "não pode reenviar o lote")

    def test_enviado_nao_pode_ser_editado(self):
        comunicado = self._criar(status=Comunicado.Status.ENVIADO)
        resp = self._chamar(
            "patch",
            "partial_update",
            self.usuarios["diretor"],
            pk=comunicado.pk,
            data={"titulo": "Mudou depois de enviar"},
        )
        self.assertEqual(resp.status_code, 400)
        comunicado.refresh_from_db()
        self.assertEqual(comunicado.titulo, "Aviso")

    def test_enviado_nao_pode_ser_excluido(self):
        comunicado = self._criar(status=Comunicado.Status.ENVIADO)
        resp = self._chamar(
            "delete", "destroy", self.usuarios["diretor"], pk=comunicado.pk
        )
        self.assertEqual(resp.status_code, 400)
        self.assertTrue(Comunicado.objects.filter(pk=comunicado.pk).exists())

    def test_rascunho_pode_ser_editado_e_excluido(self):
        comunicado = self._criar()
        resp = self._chamar(
            "patch",
            "partial_update",
            self.usuarios["diretor"],
            pk=comunicado.pk,
            data={"titulo": "Título corrigido"},
        )
        self.assertEqual(resp.status_code, 200, resp.data)
        resp = self._chamar(
            "delete", "destroy", self.usuarios["diretor"], pk=comunicado.pk
        )
        self.assertEqual(resp.status_code, 204)
        self.assertFalse(Comunicado.objects.filter(pk=comunicado.pk).exists())


class ComunicadoValidacaoTests(_ComunicadoSetup):
    def test_destino_turmas_exige_turma(self):
        resp = self._chamar(
            "post",
            "create",
            self.usuarios["diretor"],
            data=self._payload(destino=Comunicado.Destino.TURMAS, turmas=[]),
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("turmas", resp.data)

    def test_destino_turmas_recusa_turma_de_outra_escola(self):
        """Sem este guard o diretor endereçaria a turma de outra escola."""
        resp = self._chamar(
            "post",
            "create",
            self.usuarios["diretor"],
            data=self._payload(
                destino=Comunicado.Destino.TURMAS,
                turmas=[self.turma_outra_escola.id],
            ),
        )
        self.assertEqual(resp.status_code, 400)

    def test_destino_escola_ignora_turmas_enviadas(self):
        """Evita o estado contraditório 'toda a escola, mas só o 1º A'."""
        resp = self._chamar(
            "post",
            "create",
            self.usuarios["diretor"],
            data=self._payload(
                destino=Comunicado.Destino.ESCOLA, turmas=[self.turma.id]
            ),
        )
        self.assertEqual(resp.status_code, 201, resp.data)
        comunicado = Comunicado.objects.get(pk=resp.data["id"])
        self.assertEqual(comunicado.turmas.count(), 0)

    def test_titulo_e_mensagem_em_branco_sao_recusados(self):
        for campo in ("titulo", "mensagem"):
            with self.subTest(campo=campo):
                resp = self._chamar(
                    "post",
                    "create",
                    self.usuarios["diretor"],
                    data=self._payload(**{campo: "   "}),
                )
                self.assertEqual(resp.status_code, 400)
                self.assertIn(campo, resp.data)

    def test_contadores_e_status_sao_read_only(self):
        """Resultado do disparo é escrito pelo serviço, não pelo cliente."""
        resp = self._chamar(
            "post",
            "create",
            self.usuarios["diretor"],
            data=self._payload(
                status=Comunicado.Status.ENVIADO, total_enviados=999
            ),
        )
        self.assertEqual(resp.status_code, 201, resp.data)
        comunicado = Comunicado.objects.get(pk=resp.data["id"])
        self.assertEqual(comunicado.status, Comunicado.Status.RASCUNHO)
        self.assertEqual(comunicado.total_enviados, 0)


class ComunicadoEscopoTests(_ComunicadoSetup):
    def test_diretor_nao_ve_comunicado_de_outra_escola(self):
        self._criar(escola=self.outra_escola, titulo="Da outra escola")
        meu = self._criar(titulo="Da minha escola")

        resp = self._chamar("get", "list", self.usuarios["diretor"])
        self.assertEqual(resp.status_code, 200)
        ids = [c["id"] for c in resp.data["results"]]
        self.assertEqual(ids, [meu.pk])

    def test_diretor_nao_acessa_comunicado_de_outra_escola(self):
        alheio = self._criar(escola=self.outra_escola)
        resp = self._chamar(
            "get", "retrieve", self.usuarios["diretor"], pk=alheio.pk
        )
        self.assertEqual(resp.status_code, 404)

    def test_diretor_nao_envia_comunicado_de_outra_escola(self):
        alheio = self._criar(escola=self.outra_escola)
        resp = self._chamar(
            "post", "enviar", self.usuarios["diretor"], pk=alheio.pk, data={}
        )
        self.assertEqual(resp.status_code, 404)
        self.assertEqual(len(mail.outbox), 0)

    def test_diretor_nao_cria_em_outra_escola(self):
        """Guard IDOR: mandar `escola` de outra escola no body não passa."""
        resp = self._chamar(
            "post",
            "create",
            self.usuarios["diretor"],
            data=self._payload(escola=self.outra_escola.id),
        )
        self.assertEqual(resp.status_code, 400)

    def test_escola_e_preenchida_automaticamente(self):
        resp = self._chamar(
            "post", "create", self.usuarios["diretor"], data=self._payload()
        )
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data["escola"], self.escola.id)


class ComunicadoDestinatariosEndpointTests(_ComunicadoSetup):
    def test_log_lista_resultado_por_aluno(self):
        Aluno.objects.create(
            escola=self.escola,
            matricula="A2",
            nome_completo="Bruno Costa",
            turma=self.turma,
            email_responsavel="",
        )
        comunicado = self._criar()
        self._chamar(
            "post", "enviar", self.usuarios["diretor"], pk=comunicado.pk, data={}
        )

        resp = self._chamar(
            "get", "destinatarios", self.usuarios["diretor"], pk=comunicado.pk
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data), 2)
        por_aluno = {d["aluno_nome"]: d for d in resp.data}
        self.assertEqual(
            por_aluno["Ana Silva"]["status"],
            ComunicadoDestinatario.Status.ENVIADO,
        )
        self.assertEqual(
            por_aluno["Bruno Costa"]["status"],
            ComunicadoDestinatario.Status.SEM_EMAIL,
        )
        self.assertEqual(por_aluno["Ana Silva"]["turma_nome"], "1º A")

    def test_log_filtra_por_status(self):
        Aluno.objects.create(
            escola=self.escola,
            matricula="A2",
            nome_completo="Bruno Costa",
            turma=self.turma,
            email_responsavel="",
        )
        comunicado = self._criar()
        self._chamar(
            "post", "enviar", self.usuarios["diretor"], pk=comunicado.pk, data={}
        )

        resp = self._chamar(
            "get",
            "destinatarios",
            self.usuarios["diretor"],
            pk=comunicado.pk,
            params="?status=sem_email",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data), 1)
        self.assertEqual(resp.data[0]["aluno_nome"], "Bruno Costa")

    def test_log_recusa_status_invalido(self):
        comunicado = self._criar()
        resp = self._chamar(
            "get",
            "destinatarios",
            self.usuarios["diretor"],
            pk=comunicado.pk,
            params="?status=inexistente",
        )
        self.assertEqual(resp.status_code, 400)

    def test_previa_retorna_contagens(self):
        comunicado = self._criar()
        resp = self._chamar(
            "get", "previa", self.usuarios["diretor"], pk=comunicado.pk
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["total_alunos"], 1)
        self.assertEqual(resp.data["total_emails"], 1)
        self.assertEqual(resp.data["total_sem_email"], 0)
        self.assertEqual(len(mail.outbox), 0)
