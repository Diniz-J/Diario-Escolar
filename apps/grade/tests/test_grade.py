"""Testes da grade horária (fatia 1 do `PRESENCA.md`).

Verificações da fatia: o catálogo de tempos é por escola e por turno; o
slot copia a turma do lecionamento em vez de aceitá-la do payload; dois
slots ativos não ocupam o mesmo horário da mesma turma (e isso responde
400, não 500, porque o unique é parcial e o DRF não monta validator pra
constraint condicional); escrita é só direção e leitura alcança professor.
"""
from datetime import time

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.models import Usuario
from apps.escola.models import Disciplina, Escola, Lecionamento, Professor, Turma
from apps.grade.models import AulaGrade, TempoAula

URL_TEMPOS = reverse("api_v1:tempo-aula-list")
URL_GRADE = reverse("api_v1:aula-grade-list")


def url_tempo(pk) -> str:
    return reverse("api_v1:tempo-aula-detail", args=[pk])


def url_slot(pk) -> str:
    return reverse("api_v1:aula-grade-detail", args=[pk])


class _GradeSetup(TestCase):
    """Helpers sem testes, pra subclasse não herdar teste do pai."""

    @classmethod
    def setUpTestData(cls) -> None:
        cls.escola = Escola.objects.create(nome="Escola A")
        cls.outra_escola = Escola.objects.create(nome="Escola B")

        cls.turma_manha = cls._turma(cls.escola, "1º A", Turma.Turno.MATUTINO)
        cls.turma_tarde = cls._turma(cls.escola, "1º B", Turma.Turno.VESPERTINO)
        cls.matematica = Disciplina.objects.create(
            escola=cls.escola, nome="Matemática"
        )
        cls.portugues = Disciplina.objects.create(
            escola=cls.escola, nome="Português"
        )

        cls.prof1 = cls._professor("prof1", cls.escola)
        cls.prof2 = cls._professor("prof2", cls.escola)
        cls.lec_mat = cls._lecionar(cls.prof1, cls.turma_manha, cls.matematica)
        cls.lec_port = cls._lecionar(cls.prof2, cls.turma_manha, cls.portugues)
        cls.lec_tarde = cls._lecionar(cls.prof1, cls.turma_tarde, cls.matematica)

        cls.tempo1 = cls._tempo(cls.escola, 1, "07:00", "07:50")
        cls.tempo2 = cls._tempo(cls.escola, 2, "07:50", "08:40")
        cls.tempo_tarde = cls._tempo(
            cls.escola, 1, "13:00", "13:50", turno=Turma.Turno.VESPERTINO
        )

        cls.diretora = Usuario.objects.create_user(
            username="diretora",
            password="x",
            perfil=Usuario.Perfil.DIRETOR,
            escola=cls.escola,
        )
        # Admin global: sem escola no JWT, então manda `escola` no payload.
        cls.admin = Usuario.objects.create_user(
            username="admin", password="x", perfil=Usuario.Perfil.ADMIN
        )

        # Escola B, pra provar o escopo.
        cls.turma_b = cls._turma(cls.outra_escola, "1º A", Turma.Turno.MATUTINO)
        cls.disciplina_b = Disciplina.objects.create(
            escola=cls.outra_escola, nome="Matemática"
        )
        cls.prof_b = cls._professor("prof_b", cls.outra_escola)
        cls.lec_b = cls._lecionar(cls.prof_b, cls.turma_b, cls.disciplina_b)
        cls.tempo_b = cls._tempo(cls.outra_escola, 1, "07:00", "07:50")
        cls.slot_b = AulaGrade.objects.create(
            escola=cls.outra_escola,
            lecionamento=cls.lec_b,
            turma=cls.turma_b,
            dia_semana=Lecionamento.DiaSemana.SEGUNDA,
            tempo=cls.tempo_b,
        )

    @staticmethod
    def _turma(escola, nome, turno):
        return Turma.objects.create(
            escola=escola, nome=nome, turno=turno, ano_letivo=2026
        )

    @staticmethod
    def _professor(username, escola):
        usuario = Usuario.objects.create_user(
            username=username,
            password="x",
            perfil=Usuario.Perfil.PROFESSOR,
            escola=escola,
            first_name=username.capitalize(),
        )
        return Professor.objects.create(usuario=usuario, escola=escola)

    @staticmethod
    def _lecionar(professor, turma, disciplina):
        return Lecionamento.objects.create(
            escola=turma.escola,
            professor=professor,
            turma=turma,
            disciplina=disciplina,
        )

    @staticmethod
    def _tempo(escola, ordem, inicio, fim, turno=Turma.Turno.MATUTINO):
        h_i, m_i = (int(p) for p in inicio.split(":"))
        h_f, m_f = (int(p) for p in fim.split(":"))
        return TempoAula.objects.create(
            escola=escola,
            turno=turno,
            ordem=ordem,
            hora_inicio=time(h_i, m_i),
            hora_fim=time(h_f, m_f),
        )

    def setUp(self) -> None:
        self.client = APIClient()

    def _como(self, usuario):
        self.client.force_authenticate(user=usuario)

    def _payload_slot(self, **extra):
        dados = {
            "lecionamento": self.lec_mat.id,
            "dia_semana": Lecionamento.DiaSemana.SEGUNDA,
            "tempo": self.tempo1.id,
        }
        dados.update(extra)
        return dados


class TempoAulaModelTests(_GradeSetup):
    def test_duracao_invertida_e_recusada(self):
        tempo = TempoAula(
            escola=self.escola,
            turno=Turma.Turno.MATUTINO,
            ordem=3,
            hora_inicio=time(9, 0),
            hora_fim=time(8, 0),
        )
        with self.assertRaises(ValidationError) as ctx:
            tempo.full_clean()
        self.assertIn("hora_fim", ctx.exception.message_dict)

    def test_ordem_zero_e_recusada(self):
        tempo = TempoAula(
            escola=self.escola,
            turno=Turma.Turno.MATUTINO,
            ordem=0,
            hora_inicio=time(7, 0),
            hora_fim=time(7, 50),
        )
        with self.assertRaises(ValidationError) as ctx:
            tempo.full_clean()
        self.assertIn("ordem", ctx.exception.message_dict)


class AulaGradeModelTests(_GradeSetup):
    def test_turma_divergente_do_lecionamento_e_recusada(self):
        slot = AulaGrade(
            escola=self.escola,
            lecionamento=self.lec_mat,
            turma=self.turma_tarde,
            dia_semana=Lecionamento.DiaSemana.SEGUNDA,
            tempo=self.tempo1,
        )
        with self.assertRaises(ValidationError) as ctx:
            slot.full_clean()
        self.assertIn("turma", ctx.exception.message_dict)

    def test_tempo_de_outro_turno_e_recusado(self):
        """Tempo do vespertino numa turma do matutino é horário inexistente."""
        slot = AulaGrade(
            escola=self.escola,
            lecionamento=self.lec_mat,
            turma=self.turma_manha,
            dia_semana=Lecionamento.DiaSemana.SEGUNDA,
            tempo=self.tempo_tarde,
        )
        with self.assertRaises(ValidationError) as ctx:
            slot.full_clean()
        self.assertIn("tempo", ctx.exception.message_dict)

    def test_escola_desalinhada_e_recusada(self):
        slot = AulaGrade(
            escola=self.escola,
            lecionamento=self.lec_b,
            turma=self.turma_b,
            dia_semana=Lecionamento.DiaSemana.SEGUNDA,
            tempo=self.tempo1,
        )
        with self.assertRaises(ValidationError) as ctx:
            slot.full_clean()
        self.assertIn("lecionamento", ctx.exception.message_dict)


class TempoAulaApiTests(_GradeSetup):
    def test_diretora_cria_sem_mandar_escola(self):
        self._como(self.diretora)
        resposta = self.client.post(
            URL_TEMPOS,
            {
                "turno": Turma.Turno.MATUTINO,
                "ordem": 5,
                "hora_inicio": "10:20",
                "hora_fim": "11:10",
            },
            format="json",
        )
        self.assertEqual(resposta.status_code, 201, resposta.data)
        criado = TempoAula.objects.get(pk=resposta.data["id"])
        self.assertEqual(criado.escola_id, self.escola.id)

    def test_ordem_repetida_no_mesmo_turno_da_400(self):
        self._como(self.diretora)
        resposta = self.client.post(
            URL_TEMPOS,
            {
                "turno": Turma.Turno.MATUTINO,
                "ordem": self.tempo1.ordem,
                "hora_inicio": "07:00",
                "hora_fim": "07:50",
            },
            format="json",
        )
        self.assertEqual(resposta.status_code, 400, resposta.data)

    def test_duracao_invertida_da_400(self):
        self._como(self.diretora)
        resposta = self.client.post(
            URL_TEMPOS,
            {
                "turno": Turma.Turno.MATUTINO,
                "ordem": 6,
                "hora_inicio": "09:00",
                "hora_fim": "08:00",
            },
            format="json",
        )
        self.assertEqual(resposta.status_code, 400, resposta.data)
        self.assertIn("hora_fim", resposta.data)

    def test_professor_le_mas_nao_escreve(self):
        self._como(self.prof1.usuario)
        self.assertEqual(self.client.get(URL_TEMPOS).status_code, 200)
        resposta = self.client.post(
            URL_TEMPOS,
            {
                "turno": Turma.Turno.MATUTINO,
                "ordem": 7,
                "hora_inicio": "11:10",
                "hora_fim": "12:00",
            },
            format="json",
        )
        self.assertEqual(resposta.status_code, 403)

    def test_escopo_esconde_tempo_de_outra_escola(self):
        self._como(self.diretora)
        ids = {item["id"] for item in self.client.get(URL_TEMPOS).data}
        self.assertNotIn(self.tempo_b.id, ids)
        self.assertEqual(
            self.client.get(url_tempo(self.tempo_b.id)).status_code, 404
        )

    def test_idor_escola_alheia_no_payload_da_400(self):
        self._como(self.diretora)
        resposta = self.client.post(
            URL_TEMPOS,
            {
                "escola": self.outra_escola.id,
                "turno": Turma.Turno.MATUTINO,
                "ordem": 8,
                "hora_inicio": "12:00",
                "hora_fim": "12:50",
            },
            format="json",
        )
        self.assertEqual(resposta.status_code, 400, resposta.data)

    def test_delete_desativa_em_vez_de_apagar(self):
        self._como(self.diretora)
        resposta = self.client.delete(url_tempo(self.tempo2.id))
        self.assertEqual(resposta.status_code, 204)
        self.tempo2.refresh_from_db()
        self.assertFalse(self.tempo2.ativo)


class AulaGradeApiTests(_GradeSetup):
    def test_turma_vem_do_lecionamento_e_nao_do_payload(self):
        """`turma` é read-only: payload apontando outra turma é ignorado."""
        self._como(self.diretora)
        resposta = self.client.post(
            URL_GRADE,
            self._payload_slot(turma=self.turma_tarde.id),
            format="json",
        )
        self.assertEqual(resposta.status_code, 201, resposta.data)
        slot = AulaGrade.objects.get(pk=resposta.data["id"])
        self.assertEqual(slot.turma_id, self.turma_manha.id)

    def test_dois_slots_no_mesmo_horario_dao_400(self):
        """400 explícito, não 500: o unique é parcial e o DRF não o cobre."""
        self._como(self.diretora)
        primeira = self.client.post(URL_GRADE, self._payload_slot(), format="json")
        self.assertEqual(primeira.status_code, 201, primeira.data)

        segunda = self.client.post(
            URL_GRADE,
            self._payload_slot(lecionamento=self.lec_port.id),
            format="json",
        )
        self.assertEqual(segunda.status_code, 400, segunda.data)
        self.assertIn("tempo", segunda.data)

    def test_slot_inativo_nao_bloqueia_remontar_o_horario(self):
        """É o que o `condition=ativo` do unique existe pra permitir."""
        AulaGrade.objects.create(
            escola=self.escola,
            lecionamento=self.lec_mat,
            turma=self.turma_manha,
            dia_semana=Lecionamento.DiaSemana.SEGUNDA,
            tempo=self.tempo1,
            ativo=False,
        )
        self._como(self.diretora)
        resposta = self.client.post(
            URL_GRADE,
            self._payload_slot(lecionamento=self.lec_port.id),
            format="json",
        )
        self.assertEqual(resposta.status_code, 201, resposta.data)

    def test_tempo_de_outro_turno_da_400(self):
        self._como(self.diretora)
        resposta = self.client.post(
            URL_GRADE,
            self._payload_slot(tempo=self.tempo_tarde.id),
            format="json",
        )
        self.assertEqual(resposta.status_code, 400, resposta.data)
        self.assertIn("tempo", resposta.data)

    def test_lecionamento_de_outra_escola_da_400(self):
        self._como(self.diretora)
        resposta = self.client.post(
            URL_GRADE,
            self._payload_slot(lecionamento=self.lec_b.id, tempo=self.tempo1.id),
            format="json",
        )
        self.assertEqual(resposta.status_code, 400, resposta.data)
        self.assertIn("lecionamento", resposta.data)

    def test_mesmo_tempo_em_dias_diferentes_e_permitido(self):
        self._como(self.diretora)
        self.assertEqual(
            self.client.post(URL_GRADE, self._payload_slot(), format="json")
            .status_code,
            201,
        )
        resposta = self.client.post(
            URL_GRADE,
            self._payload_slot(dia_semana=Lecionamento.DiaSemana.TERCA),
            format="json",
        )
        self.assertEqual(resposta.status_code, 201, resposta.data)

    def test_professor_le_a_grade_mas_nao_escreve(self):
        self._como(self.prof1.usuario)
        self.assertEqual(self.client.get(URL_GRADE).status_code, 200)
        resposta = self.client.post(URL_GRADE, self._payload_slot(), format="json")
        self.assertEqual(resposta.status_code, 403)

    def test_escopo_esconde_slot_de_outra_escola(self):
        self._como(self.diretora)
        ids = {item["id"] for item in self.client.get(URL_GRADE).data}
        self.assertNotIn(self.slot_b.id, ids)
        self.assertEqual(self.client.get(url_slot(self.slot_b.id)).status_code, 404)

    def test_delete_desativa_em_vez_de_apagar(self):
        slot = AulaGrade.objects.create(
            escola=self.escola,
            lecionamento=self.lec_mat,
            turma=self.turma_manha,
            dia_semana=Lecionamento.DiaSemana.QUARTA,
            tempo=self.tempo1,
        )
        self._como(self.diretora)
        self.assertEqual(self.client.delete(url_slot(slot.id)).status_code, 204)
        slot.refresh_from_db()
        self.assertFalse(slot.ativo)

    def test_derivados_vem_na_resposta(self):
        """A tela da fatia 2 renderiza a semana sem uma query por slot."""
        self._como(self.diretora)
        resposta = self.client.post(URL_GRADE, self._payload_slot(), format="json")
        self.assertEqual(resposta.status_code, 201, resposta.data)
        self.assertEqual(resposta.data["disciplina"], self.matematica.id)
        self.assertEqual(resposta.data["disciplina_nome"], "Matemática")
        self.assertEqual(resposta.data["professor"], self.prof1.id)
        self.assertEqual(resposta.data["tempo_ordem"], self.tempo1.ordem)
