"""Testes da agregação da timeline do aluno.

Cobre o que a timeline promete (as três origens numa ordem só) e as
decisões que seriam "corrigidas" por engano: a régua de presença
diferente da frequência, o histórico cadastral lido inteiro e a lista de
permissão de campos que mantém contato de responsável fora da tela do
professor.
"""
from datetime import date, timedelta

from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import Usuario
from apps.escola.models import Aluno, Escola, Professor, Turma
from apps.ocorrencias.models import Ocorrencia
from apps.presenca.models import ItemPresenca, RegistroPresenca
from apps.timeline.services import (
    TIPO_CADASTRO,
    TIPO_OCORRENCIA,
    TIPO_PRESENCA,
    montar_timeline,
)


def _presenca(turma, dia: date, aluno, status: str) -> RegistroPresenca:
    registro = RegistroPresenca.objects.create(
        escola=turma.escola, turma=turma, data=dia
    )
    ItemPresenca.objects.create(registro=registro, aluno=aluno, status=status)
    return registro


class TimelineServiceTests(TestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        cls.escola = Escola.objects.create(nome="Escola")
        cls.turma = Turma.objects.create(
            escola=cls.escola,
            nome="1º A",
            turno=Turma.Turno.MATUTINO,
            ano_letivo=2026,
        )
        cls.turma_b = Turma.objects.create(
            escola=cls.escola,
            nome="1º B",
            turno=Turma.Turno.MATUTINO,
            ano_letivo=2026,
        )

    def setUp(self) -> None:
        self.aluno = Aluno.objects.create(
            escola=self.escola,
            matricula="A1",
            nome_completo="Ana",
            turma=self.turma,
        )

    def _titulos(self, timeline) -> list[str]:
        return [evento["titulo"] for evento in timeline["eventos"]]

    def _por_tipo(self, timeline, tipo) -> list[dict]:
        return [e for e in timeline["eventos"] if e["tipo"] == tipo]

    def test_junta_as_tres_origens_em_ordem_decrescente(self):
        Ocorrencia.objects.create(
            escola=self.escola,
            turma=self.turma,
            aluno=self.aluno,
            descricao="Conversa em sala",
            data_ocorrencia=date(2026, 3, 10),
        )
        _presenca(
            self.turma,
            date(2026, 3, 12),
            self.aluno,
            ItemPresenca.Status.AUSENTE,
        )

        timeline = montar_timeline(self.aluno)
        datas = [evento["data"] for evento in timeline["eventos"]]
        self.assertEqual(datas, sorted(datas, reverse=True))
        self.assertEqual(len(self._por_tipo(timeline, TIPO_OCORRENCIA)), 1)
        self.assertEqual(len(self._por_tipo(timeline, TIPO_PRESENCA)), 1)
        # Cadastro do aluno: criado no `setUp`, entra como primeiro evento
        # do histórico.
        self.assertEqual(len(self._por_tipo(timeline, TIPO_CADASTRO)), 1)
        self.assertEqual(timeline["aluno"]["nome_completo"], "Ana")
        self.assertEqual(timeline["aluno"]["turma"], "1º A")

    def test_presenca_normal_fica_fora(self):
        """`P` não é evento: 200 'veio à aula' afogariam o resto."""
        _presenca(
            self.turma,
            date(2026, 3, 2),
            self.aluno,
            ItemPresenca.Status.PRESENTE,
        )
        timeline = montar_timeline(self.aluno)
        self.assertEqual(self._por_tipo(timeline, TIPO_PRESENCA), [])

    def test_justificada_e_retardatario_sao_eventos(self):
        """Régua diferente da frequência, de propósito.

        Em `apps/relatorios/services.py` `J` e `R` contam como presença
        efetiva. Aqui entram como evento: a pergunta da timeline é "o que
        aconteceu", e chegar atrasado aconteceu. Se alguém "consertar"
        isso pra alinhar com a frequência, este teste acusa.
        """
        _presenca(
            self.turma,
            date(2026, 3, 3),
            self.aluno,
            ItemPresenca.Status.JUSTIFICADO,
        )
        _presenca(
            self.turma,
            date(2026, 3, 4),
            self.aluno,
            ItemPresenca.Status.RETARDATARIO,
        )
        timeline = montar_timeline(self.aluno)
        titulos = {e["titulo"] for e in self._por_tipo(timeline, TIPO_PRESENCA)}
        self.assertEqual(titulos, {"Justificado", "Retardatário"})

    def test_evento_de_presenca_aponta_para_a_chamada(self):
        registro = _presenca(
            self.turma,
            date(2026, 3, 5),
            self.aluno,
            ItemPresenca.Status.AUSENTE,
        )
        evento = self._por_tipo(montar_timeline(self.aluno), TIPO_PRESENCA)[0]
        self.assertEqual(evento["referencia_id"], registro.pk)
        self.assertEqual(evento["turma"], "1º A")

    def test_ocorrencia_leva_status_e_autor(self):
        usuario = Usuario.objects.create_user(
            username="prof",
            password="x",
            first_name="Marina",
            last_name="Dias",
            perfil=Usuario.Perfil.PROFESSOR,
            escola=self.escola,
        )
        professor = Professor.objects.create(
            escola=self.escola, usuario=usuario
        )
        ocorrencia = Ocorrencia.objects.create(
            escola=self.escola,
            turma=self.turma,
            aluno=self.aluno,
            professor=professor,
            descricao="Saiu sem autorização",
            data_ocorrencia=date(2026, 3, 10),
            status=Ocorrencia.Status.EM_ANDAMENTO,
        )

        evento = self._por_tipo(montar_timeline(self.aluno), TIPO_OCORRENCIA)[0]
        self.assertEqual(evento["referencia_id"], ocorrencia.pk)
        self.assertEqual(evento["status"], "em_andamento")
        self.assertEqual(evento["status_label"], "Em andamento")
        self.assertEqual(evento["autor"], "Marina Dias")
        self.assertEqual(evento["detalhe"], "Saiu sem autorização")

    def test_ocorrencia_sem_professor_nao_quebra(self):
        """`professor` é opcional: a direção registra sem vincular."""
        Ocorrencia.objects.create(
            escola=self.escola,
            turma=self.turma,
            aluno=self.aluno,
            descricao="Registro da direção",
            data_ocorrencia=date(2026, 3, 10),
        )
        evento = self._por_tipo(montar_timeline(self.aluno), TIPO_OCORRENCIA)[0]
        self.assertEqual(evento["autor"], "")

    def test_remanejamento_vira_evento_com_nome_das_turmas(self):
        self.aluno.turma = self.turma_b
        self.aluno.save(update_fields=["turma"])

        eventos = self._por_tipo(montar_timeline(self.aluno), TIPO_CADASTRO)
        remanejamento = [e for e in eventos if e["titulo"] == "Turma alterada"]
        self.assertEqual(len(remanejamento), 1)
        self.assertEqual(remanejamento[0]["detalhe"], "1º A → 1º B")

    def test_soft_delete_e_reativacao_viram_eventos(self):
        self.aluno.ativo = False
        self.aluno.save(update_fields=["ativo"])
        self.aluno.ativo = True
        self.aluno.save(update_fields=["ativo"])

        titulos = self._titulos(montar_timeline(self.aluno))
        self.assertIn("Aluno inativado", titulos)
        self.assertIn("Aluno reativado", titulos)
        self.assertIn("Aluno cadastrado", titulos)

    def test_contato_do_responsavel_nao_vira_evento(self):
        """Lista de permissão de campos: PII do responsável fica fora.

        A timeline é lida por professor e inspetor, e contato de
        responsável é nível-direção no resto do sistema.
        """
        self.aluno.nome_responsavel = "Joana"
        self.aluno.email_responsavel = "joana@example.com"
        self.aluno.save(
            update_fields=["nome_responsavel", "email_responsavel"]
        )

        timeline = montar_timeline(self.aluno)
        eventos = self._por_tipo(timeline, TIPO_CADASTRO)
        self.assertEqual([e["titulo"] for e in eventos], ["Aluno cadastrado"])
        serializado = str(timeline)
        self.assertNotIn("joana@example.com", serializado)
        self.assertNotIn("Joana", serializado)

    def test_autor_da_mudanca_cadastral(self):
        secretaria = Usuario.objects.create_user(
            username="sec",
            password="x",
            first_name="Carlos",
            last_name="Luz",
            perfil=Usuario.Perfil.SECRETARIA,
            escola=self.escola,
        )
        self.aluno.ativo = False
        self.aluno._history_user = secretaria
        self.aluno.save(update_fields=["ativo"])

        eventos = self._por_tipo(montar_timeline(self.aluno), TIPO_CADASTRO)
        inativacao = [e for e in eventos if e["titulo"] == "Aluno inativado"][0]
        self.assertEqual(inativacao["autor"], "Carlos Luz")

    def test_autor_vazio_quando_mudanca_veio_de_fora_de_request(self):
        """Seed e management command não têm `request.user` pra capturar."""
        self.aluno.ativo = False
        self.aluno.save(update_fields=["ativo"])
        eventos = self._por_tipo(montar_timeline(self.aluno), TIPO_CADASTRO)
        self.assertTrue(all(evento["autor"] == "" for evento in eventos))

    def test_janela_filtra_ocorrencia_e_presenca(self):
        Ocorrencia.objects.create(
            escola=self.escola,
            turma=self.turma,
            aluno=self.aluno,
            descricao="Antiga",
            data_ocorrencia=date(2026, 2, 1),
        )
        Ocorrencia.objects.create(
            escola=self.escola,
            turma=self.turma,
            aluno=self.aluno,
            descricao="Na janela",
            data_ocorrencia=date(2026, 3, 15),
        )
        _presenca(
            self.turma,
            date(2026, 2, 2),
            self.aluno,
            ItemPresenca.Status.AUSENTE,
        )

        timeline = montar_timeline(
            self.aluno, date(2026, 3, 1), date(2026, 3, 31)
        )
        self.assertEqual(len(self._por_tipo(timeline, TIPO_OCORRENCIA)), 1)
        self.assertEqual(
            self._por_tipo(timeline, TIPO_OCORRENCIA)[0]["detalhe"],
            "Na janela",
        )
        self.assertEqual(self._por_tipo(timeline, TIPO_PRESENCA), [])
        self.assertEqual(timeline["janela"]["data_inicio"], "2026-03-01")

    def test_janela_nao_perde_mudanca_cadastral_por_falta_da_entrada_anterior(
        self,
    ):
        """O histórico é lido inteiro e filtrado depois.

        O cadastro do aluno é de hoje (`setUp`) e a inativação também.
        Se o filtro de janela fosse aplicado no banco, uma janela que
        começa hoje perderia a entrada anterior e a inativação não teria
        com o que ser comparada — o evento desapareceria.
        """
        hoje = timezone.localdate()
        self.aluno.ativo = False
        self.aluno.save(update_fields=["ativo"])

        timeline = montar_timeline(self.aluno, hoje, hoje)
        self.assertIn("Aluno inativado", self._titulos(timeline))

    def test_evento_cadastral_fora_da_janela_fica_de_fora(self):
        hoje = timezone.localdate()
        ontem = hoje - timedelta(days=1)
        timeline = montar_timeline(self.aluno, ontem, ontem)
        self.assertEqual(self._por_tipo(timeline, TIPO_CADASTRO), [])

    def test_teto_corta_e_avisa(self):
        for dia in range(2, 8):
            _presenca(
                self.turma,
                date(2026, 3, dia),
                self.aluno,
                ItemPresenca.Status.AUSENTE,
            )

        timeline = montar_timeline(self.aluno, limite=3)
        self.assertEqual(len(timeline["eventos"]), 3)
        self.assertTrue(timeline["truncado"])
        self.assertEqual(timeline["limite"], 3)
        # 6 faltas + o cadastro do aluno.
        self.assertEqual(timeline["total_eventos"], 7)

    def test_sem_truncar_quando_cabe(self):
        timeline = montar_timeline(self.aluno)
        self.assertFalse(timeline["truncado"])
        self.assertEqual(timeline["total_eventos"], 1)

    def test_ordem_interna_nao_vaza_na_resposta(self):
        """`_ordem` é chave de desempate interna, não parte do contrato."""
        _presenca(
            self.turma,
            date(2026, 3, 2),
            self.aluno,
            ItemPresenca.Status.AUSENTE,
        )
        for evento in montar_timeline(self.aluno)["eventos"]:
            self.assertNotIn("_ordem", evento)
