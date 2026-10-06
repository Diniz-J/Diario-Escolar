"""Testes do convite, da definição de senha e do reset (fatia 3 do `PORTAL.md`).

Verificação da fatia: convite reusado falha, expirado falha, só nível
diretor convida, lote respeita a cota. Mais: link novo invalida o antigo,
"esqueci" não revela conta, e trocar a senha derruba as sessões antigas.
"""
import importlib
import re
from datetime import timedelta
from io import StringIO
from unittest import mock

from django.apps import apps as django_apps
from django.core import mail
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import Usuario
from apps.escola.models import Escola
from apps.portal.models import ConviteResponsavel, Responsavel
from apps.portal.services import INTERVALO_MINIMO_REDEFINICAO, definir_senha

SENHA_STAFF = "senha-super-segura-123"
SENHA_NOVA = "Nova-senha-do-pai-2026"

URL_LOGIN = reverse("api_v1:portal_login")
URL_REFRESH = reverse("api_v1:portal_refresh")
URL_ME = reverse("api_v1:portal_me")
URL_ESQUECI = reverse("api_v1:portal_senha_esqueci")
URL_DEFINIR = reverse("api_v1:portal_senha_definir")
ENVIO = "django.core.mail.EmailMultiAlternatives.send"


def url_convidar(pk) -> str:
    return reverse("api_v1:responsavel_convidar", args=[pk])


def token_do_email(msg) -> str:
    return re.search(r"definir-senha\?token=([\w-]+)", msg.body).group(1)


class _ConviteSetup(TestCase):
    """Helpers sem testes, pra subclasse não herdar teste do pai."""

    @classmethod
    def setUpTestData(cls) -> None:
        cls.escola = Escola.objects.create(nome="Escola A")
        cls.outra_escola = Escola.objects.create(nome="Escola B")
        cls.diretora = cls._staff("diretora", Usuario.Perfil.DIRETOR, cls.escola)
        cls.professor = cls._staff("prof", Usuario.Perfil.PROFESSOR, cls.escola)
        cls.semeado = cls._responsavel(cls.escola, "maria@example.com")

    @staticmethod
    def _staff(username, perfil, escola):
        return Usuario.objects.create_user(
            username=username, password=SENHA_STAFF, perfil=perfil, escola=escola
        )

    @staticmethod
    def _responsavel(escola, email, senha=None, ativo=True):
        r = Responsavel(escola=escola, email=email, nome="Maria", ativo=ativo)
        if senha is None:
            r.set_unusable_password()
        else:
            r.set_password(senha)
        r.save()
        return r

    def setUp(self) -> None:
        self.client = APIClient()
        mail.outbox = []

    def _convidar(self, responsavel, como=None):
        self.client.force_authenticate(user=como or self.diretora)
        resp = self.client.post(url_convidar(responsavel.pk))
        self.client.force_authenticate(user=None)
        return resp

    def _definir(self, token, senha=SENHA_NOVA):
        return self.client.post(
            URL_DEFINIR, {"token": token, "password": senha}, format="json"
        )

    def _login(self, email="maria@example.com", senha=SENHA_NOVA):
        return self.client.post(
            URL_LOGIN, {"email": email, "password": senha}, format="json"
        )


class ConvidarTests(_ConviteSetup):
    def test_diretora_convida_e_o_email_leva_o_link(self):
        resp = self._convidar(self.semeado)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["maria@example.com"])
        convite = ConviteResponsavel.objects.get(responsavel=self.semeado)
        self.assertEqual(convite.finalidade, ConviteResponsavel.Finalidade.CONVITE)
        self.assertEqual(convite.enviado_por, self.diretora)
        # Só o hash fica no banco: o token cru do email não está lá.
        self.assertNotEqual(convite.token_hash, token_do_email(mail.outbox[0]))

    def test_professor_nao_convida(self):
        resp = self._convidar(self.semeado, como=self.professor)
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(len(mail.outbox), 0)

    def test_responsavel_de_outra_escola_da_404(self):
        alheio = self._responsavel(self.outra_escola, "joao@example.com")
        self.assertEqual(self._convidar(alheio).status_code, 404)

    def test_conta_inativa_ou_ja_ativada_da_400(self):
        inativa = self._responsavel(self.escola, "inativa@example.com", ativo=False)
        ativada = self._responsavel(self.escola, "ativada@example.com", senha="x-Senha-123")
        self.assertEqual(self._convidar(inativa).status_code, 400)
        self.assertEqual(self._convidar(ativada).status_code, 400)
        self.assertEqual(len(mail.outbox), 0)

    def test_conta_criada_sem_senha_pode_ser_convidada(self):
        """Pelo admin a senha é só leitura: a conta nascia com `""`, que o
        Django trata como senha utilizável — convite recusado, conta presa."""
        sem_senha = Responsavel.objects.create(
            escola=self.escola, email="admin@example.com", nome="Pelo admin"
        )
        self.assertFalse(sem_senha.has_usable_password())
        self.assertEqual(self._convidar(sem_senha).status_code, 200)

    def test_apagar_quem_convidou_nao_e_bloqueado(self):
        """Com `PROTECT`, apagar a secretaria que mandou um convite dava
        `ProtectedError` (500 no `DELETE /usuarios/<id>/`)."""
        secretaria = self._staff("secretaria", Usuario.Perfil.SECRETARIA, self.escola)
        self._convidar(self.semeado, como=secretaria)
        secretaria.delete()
        self.assertIsNone(ConviteResponsavel.objects.get().enviado_por)

    def test_migration_conserta_conta_gravada_com_senha_vazia(self):
        """O `save()` corrige o próximo save; linhas já no banco com `""`
        precisam da migration 0003."""
        Responsavel.objects.filter(pk=self.semeado.pk).update(password="")
        migration = importlib.import_module(
            "apps.portal.migrations.0003_responsavel_senha_vazia"
        )
        migration.marcar_sem_senha(django_apps, None)
        self.semeado.refresh_from_db()
        self.assertFalse(self.semeado.has_usable_password())
        self.assertEqual(self._convidar(self.semeado).status_code, 200)

    def test_falha_no_envio_da_502_e_invalida_o_convite(self):
        with mock.patch(ENVIO, side_effect=ConnectionError("provedor fora")):
            resp = self._convidar(self.semeado)
        self.assertEqual(resp.status_code, 502)
        self.assertFalse(ConviteResponsavel.pendentes(self.semeado).exists())

    def test_convite_novo_invalida_o_anterior(self):
        self._convidar(self.semeado)
        self._convidar(self.semeado)
        antigo, novo = (token_do_email(m) for m in mail.outbox)
        self.assertEqual(self._definir(antigo).status_code, 400)
        self.assertEqual(self._definir(novo).status_code, 200)


class DefinirSenhaTests(_ConviteSetup):
    def _token(self):
        self._convidar(self.semeado)
        return token_do_email(mail.outbox[-1])

    def test_definir_senha_libera_o_login(self):
        self.assertEqual(self._login().status_code, 401)
        self.assertEqual(self._definir(self._token()).status_code, 200)
        self.assertEqual(self._login().status_code, 200)

    def test_convite_reusado_falha(self):
        token = self._token()
        self.assertEqual(self._definir(token).status_code, 200)
        self.assertEqual(self._definir(token, "Outra-senha-2026").status_code, 400)

    def test_convite_expirado_falha(self):
        token = self._token()
        ConviteResponsavel.objects.update(expira_em=timezone.now() - timedelta(seconds=1))
        self.assertEqual(self._definir(token).status_code, 400)

    def test_token_inexistente_falha(self):
        self.assertEqual(self._definir("nao-existe").status_code, 400)

    def test_senha_fraca_e_recusada_sem_consumir_o_link(self):
        token = self._token()
        resp = self._definir(token, "123")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("password", resp.data)
        self.assertEqual(self._definir(token).status_code, 200)

    def test_link_so_e_consumido_uma_vez_mesmo_em_corrida(self):
        """Duas requisições simultâneas passam pelo `buscar_valido` antes de
        qualquer uma consumir o link; só uma pode gravar a senha."""
        self._token()
        convite = ConviteResponsavel.objects.get()
        # Os dois "requests" já têm o convite em mão, validado.
        self.assertTrue(definir_senha(convite, SENHA_NOVA))
        self.assertFalse(definir_senha(convite, "Senha-do-atacante-2026"))
        self.assertEqual(self._login().status_code, 200)

    def test_conta_desativada_depois_do_convite_nao_define_senha(self):
        token = self._token()
        Responsavel.objects.filter(pk=self.semeado.pk).update(ativo=False)
        self.assertEqual(self._definir(token).status_code, 400)


class EsqueciSenhaTests(_ConviteSetup):
    def _esqueci(self, email):
        return self.client.post(URL_ESQUECI, {"email": email}, format="json")

    def test_conta_com_senha_recebe_link_de_redefinicao(self):
        self._responsavel(self.escola, "ativa@example.com", senha="x-Senha-123")
        resp = self._esqueci("  ATIVA@example.com ")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(mail.outbox), 1)
        convite = ConviteResponsavel.objects.get()
        self.assertEqual(convite.finalidade, ConviteResponsavel.Finalidade.REDEFINICAO)
        self.assertLessEqual(convite.expira_em, timezone.now() + timedelta(hours=1))

    def test_resposta_igual_e_sem_email_quando_nao_ha_conta_com_senha(self):
        """Email inexistente e conta sem senha respondem igual à conta real
        — e só a conta real recebe email."""
        self._responsavel(self.escola, "ativa@example.com", senha="x-Senha-123")
        respostas = [
            self._esqueci("ativa@example.com"),
            self._esqueci("ninguem@example.com"),
            self._esqueci("maria@example.com"),  # semeada, sem senha
        ]
        self.assertEqual({r.status_code for r in respostas}, {200})
        self.assertEqual(len({str(r.data["detail"]) for r in respostas}), 1)
        self.assertEqual(len(mail.outbox), 1)

    def test_pedidos_repetidos_nao_mandam_outro_email_nem_matam_o_link(self):
        """Sem limite por conta, dava pra disparar milhares de emails pro
        mesmo pai (cota compartilhada) e cada pedido matava o link anterior."""
        self._responsavel(self.escola, "ativa@example.com", senha="x-Senha-123")
        for _ in range(3):
            self.assertEqual(self._esqueci("ativa@example.com").status_code, 200)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(self._definir(token_do_email(mail.outbox[0])).status_code, 200)

    def test_passada_a_janela_um_pedido_novo_manda_outro_link(self):
        self._responsavel(self.escola, "ativa@example.com", senha="x-Senha-123")
        self._esqueci("ativa@example.com")
        ConviteResponsavel.objects.update(
            criado_em=timezone.now() - INTERVALO_MINIMO_REDEFINICAO - timedelta(seconds=1)
        )
        self._esqueci("ativa@example.com")
        self.assertEqual(len(mail.outbox), 2)

    def test_trocar_a_senha_derruba_as_sessoes_antigas(self):
        ativa = self._responsavel(self.escola, "ativa@example.com", senha="x-Senha-123")
        tokens = self._login("ativa@example.com", "x-Senha-123").data
        self._esqueci("ativa@example.com")
        self.assertEqual(self._definir(token_do_email(mail.outbox[-1])).status_code, 200)

        antigo = self.client.get(URL_ME, HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
        self.assertEqual(antigo.status_code, 401)
        resp = self.client.post(URL_REFRESH, {"refresh": tokens["refresh"]}, format="json")
        self.assertEqual(resp.status_code, 401)

        novo = self._login("ativa@example.com", SENHA_NOVA).data["access"]
        resp = self.client.get(URL_ME, HTTP_AUTHORIZATION=f"Bearer {novo}")
        self.assertEqual(resp.data["id"], ativa.pk)


class ConvidarEmLoteTests(_ConviteSetup):
    @classmethod
    def setUpTestData(cls) -> None:
        super().setUpTestData()
        cls._responsavel(cls.escola, "b@example.com")
        cls._responsavel(cls.escola, "c@example.com")
        cls._responsavel(cls.escola, "ativada@example.com", senha="x-Senha-123")
        cls._responsavel(cls.escola, "inativa@example.com", ativo=False)

    def _rodar(self, **opts):
        out = StringIO()
        call_command("portal_convidar_responsaveis", stdout=out, **opts)
        return out.getvalue()

    def test_respeita_o_limite_e_retoma_sem_repetir(self):
        self._rodar(limite=2)
        self.assertEqual(len(mail.outbox), 2)
        self._rodar(limite=2)
        self.assertEqual(len(mail.outbox), 3)
        self._rodar(limite=2)
        self.assertEqual(len(mail.outbox), 3)
        # Só os 3 semeados ativos; conta já ativada e inativa ficam de fora.
        self.assertEqual(
            sorted(m.to[0] for m in mail.outbox),
            ["b@example.com", "c@example.com", "maria@example.com"],
        )

    def test_dry_run_nao_envia(self):
        saida = self._rodar(dry_run=True)
        self.assertEqual(len(mail.outbox), 0)
        self.assertIn("3 na fila", saida)

    def test_para_no_primeiro_erro_e_quem_falhou_volta_pra_fila(self):
        envio_real = mail.EmailMultiAlternatives.send
        chamadas = {"n": 0}

        def envio_que_falha_no_segundo(msg, *args, **kwargs):
            chamadas["n"] += 1
            if chamadas["n"] == 2:
                raise ConnectionError("cota estourada")
            return envio_real(msg, *args, **kwargs)

        with mock.patch(ENVIO, autospec=True, side_effect=envio_que_falha_no_segundo):
            with self.assertRaises(CommandError):
                self._rodar()
        self.assertEqual(len(mail.outbox), 1)
        # Os dois que faltaram (o que falhou incluso) saem na próxima rodada.
        self._rodar()
        self.assertEqual(len(mail.outbox), 3)

    def test_limite_invalido_e_erro_explicito(self):
        with self.assertRaises(CommandError):
            self._rodar(limite=0)
