"""Testes do mural no portal (fatia 5 do `PORTAL.md`).

Verificação da fatia: responsável só vê a turma do filho. Mais: material
desativado some, filho desativado não vê o mural, e sem N+1.
"""
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.models import Usuario
from apps.escola.models import Aluno, Disciplina, Escola, Lecionamento, Professor, Turma
from apps.materiais.models import Material
from apps.portal.models import Responsavel, ResponsavelAluno
from apps.portal.tokens import PortalRefreshToken


class MuralNoPortalTests(TestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        cls.escola = Escola.objects.create(nome="Escola A")
        cls.turma1 = cls._turma("1º A")
        cls.turma2 = cls._turma("2º A")
        cls.disciplina = Disciplina.objects.create(escola=cls.escola, nome="Ciências")
        usuario = Usuario.objects.create_user(
            username="prof", password="x", perfil=Usuario.Perfil.PROFESSOR,
            escola=cls.escola, first_name="Carla", last_name="Professora",
        )
        cls.professor = Professor.objects.create(usuario=usuario, escola=cls.escola)
        for turma in (cls.turma1, cls.turma2):
            Lecionamento.objects.create(
                escola=cls.escola, professor=cls.professor, turma=turma,
                disciplina=cls.disciplina,
            )

        cls.filho = cls._aluno("Ana Filha", cls.turma1)
        cls.filho_inativo = cls._aluno("Ana Transferida", cls.turma1, ativo=False)
        cls.filho_beto = cls._aluno("Beto Filho", cls.turma2)
        cls.ana = Responsavel.objects.create(escola=cls.escola, email="ana@example.com", nome="Ana")
        for filho in (cls.filho, cls.filho_inativo):
            ResponsavelAluno.objects.create(responsavel=cls.ana, aluno=filho)
        beto = Responsavel.objects.create(escola=cls.escola, email="beto@example.com", nome="Beto")
        ResponsavelAluno.objects.create(responsavel=beto, aluno=cls.filho_beto)

        cls.m_turma1 = cls._material(cls.turma1, "Experimento da semana")
        cls.m_desativado = cls._material(cls.turma1, "Removido", ativo=False)
        cls.m_turma2 = cls._material(cls.turma2, "Só do 2º A")

    @classmethod
    def _turma(cls, nome):
        return Turma.objects.create(
            escola=cls.escola, nome=nome, turno=Turma.Turno.MATUTINO, ano_letivo=2026
        )

    @classmethod
    def _aluno(cls, nome, turma, ativo=True):
        return Aluno.objects.create(
            escola=cls.escola, matricula=f"M{Aluno.objects.count() + 1}",
            nome_completo=nome, turma=turma, ativo=ativo,
        )

    @classmethod
    def _material(cls, turma, titulo, ativo=True):
        return Material.objects.create(
            escola=cls.escola, turma=turma, disciplina=cls.disciplina,
            professor=cls.professor, titulo=titulo, ativo=ativo,
            link="https://example.com/material",
        )

    def setUp(self) -> None:
        self.client = APIClient()
        access = PortalRefreshToken.para_responsavel(self.ana).access_token
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")

    def _mural(self, aluno):
        return self.client.get(reverse("api_v1:portal_aluno_materiais", args=[aluno.pk]))

    def test_so_a_turma_do_filho_e_so_ativos(self):
        resp = self._mural(self.filho)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual([m["id"] for m in resp.data["results"]], [self.m_turma1.pk])

    def test_campos_sem_ids_internos(self):
        item = self._mural(self.filho).data["results"][0]
        self.assertEqual(item["disciplina"], "Ciências")
        self.assertEqual(item["professor"], "Carla Professora")
        for campo in ("turma", "escola", "ativo"):
            self.assertNotIn(campo, item)

    def test_filho_de_outra_familia_da_404(self):
        self.assertEqual(self._mural(self.filho_beto).status_code, 404)

    def test_filho_desativado_nao_ve_o_mural(self):
        resp = self._mural(self.filho_inativo)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["count"], 0)

    def test_filho_que_trocou_de_turma_ve_o_mural_da_nova(self):
        Aluno.objects.filter(pk=self.filho.pk).update(turma=self.turma2)
        ids = [m["id"] for m in self._mural(self.filho).data["results"]]
        self.assertEqual(ids, [self.m_turma2.pk])

    def test_consultas_nao_crescem_com_o_mural(self):
        def contar():
            with CaptureQueriesContext(connection) as ctx:
                self.assertEqual(self._mural(self.filho).status_code, 200)
            return len(ctx.captured_queries)

        antes = contar()
        for i in range(4):
            self._material(self.turma1, f"Extra {i}")
        self.assertEqual(contar(), antes)
