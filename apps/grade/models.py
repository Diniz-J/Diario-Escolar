"""Modelos da app grade — catálogo de tempos e grade horária da turma.

Dois modelos, ambos cadastro de direção:

- `TempoAula` — catálogo de horários da escola, por turno. É o que torna a
  duração do tempo configurável por cliente (uma escola de 50 minutos e
  outra de 45 usam o mesmo código).
- `AulaGrade` — o slot: um `Lecionamento` ocupa um `TempoAula` num dia da
  semana. Unique por `(escola, turma, dia_semana, tempo)`.

Desenho completo e decisões em `PRESENCA.md`. Quatro coisas que não se
deduzem do código:

**A grade sugere; o registro de presença é dono do dado.** A chamada
(fatia 3) copia tempo, disciplina e professor da grade em vez de apontar
pra cá por FK. Editar a grade ou realocá-la em janeiro não pode reescrever
chamada passada — é o mesmo raciocínio do valor congelado da `Fatura`. Por
isso não existe (nem deve existir) FK de `RegistroPresenca` pra
`AulaGrade`.

**O slot aponta pro `Lecionamento`, não pra disciplina e professor
soltos.** O vínculo professor × turma × disciplina já existe e é validado
lá, então a grade herda a validação e um trio inválido não é agendável. O
custo aceito é que os lecionamentos têm que existir antes de montar a
grade, e não há slot "a definir".

**`AulaGrade.turma` é desnormalizado e essa é a única razão do campo.** A
garantia que importa é "um tempo da turma num dia não tem dois slots", e
`UniqueConstraint` não atravessa FK — sem a cópia, a garantia cairia pro
`clean()`. Mesmo caso e mesma justificativa de `Fatura.aluno`
(`FINANCEIRO.md` §3). Como é derivado, o serializer o preenche a partir do
lecionamento e nunca aceita do payload.

**O slot não é validado contra `Lecionamento.dias_semana`.** A grade vai
*substituir* aquele campo (fatia 5 do `PRESENCA.md`), que diz menos do que
ela: dia sem tempo. Validar contra algo que vai morrer criaria acoplamento
com data de validade, e grade e campo discordando é exatamente o que a
remoção resolve.

Auditoria: `AulaGrade` tem `HistoricalRecords` porque é o registro de quem
dá aula quando — muda na realocação anual e é o tipo de mudança que a
direção precisa rastrear, como o `Lecionamento`. `TempoAula` fica fora,
pelo mesmo critério de `Turma`/`Disciplina` no `CLAUDE.md`: catálogo que
muda raramente.
"""
from django.core.exceptions import ValidationError
from django.db import models
from simple_history.models import HistoricalRecords

from apps.common.models import BaseModelEscopado
from apps.escola.models import Escola, Lecionamento, Turma


class TempoAula(BaseModelEscopado):
    """Um horário do catálogo da escola (ex.: 2º tempo, 07:50–08:40)."""

    # Mesmos turnos da turma: os horários do matutino não servem o
    # vespertino, e é o turno da turma que seleciona o catálogo.
    turno = models.CharField(max_length=20, choices=Turma.Turno.choices)
    ordem = models.PositiveSmallIntegerField()
    hora_inicio = models.TimeField()
    hora_fim = models.TimeField()
    ativo = models.BooleanField(default=True)

    escola = models.ForeignKey(
        Escola, on_delete=models.PROTECT, related_name="tempos_aula"
    )

    class Meta:
        verbose_name = "tempo de aula"
        verbose_name_plural = "tempos de aula"
        ordering = ["turno", "ordem"]
        constraints = [
            models.UniqueConstraint(
                fields=["escola", "turno", "ordem"],
                name="tempo_aula_unique_escola_turno_ordem",
            ),
        ]

    def __str__(self) -> str:
        inicio = self.hora_inicio.strftime("%H:%M") if self.hora_inicio else "?"
        fim = self.hora_fim.strftime("%H:%M") if self.hora_fim else "?"
        return f"{self.ordem}º tempo ({inicio}–{fim}) — {self.get_turno_display()}"

    def clean(self) -> None:
        """Ordem começa em 1 e o tempo tem duração positiva."""
        super().clean()
        errors: dict[str, str] = {}

        if self.ordem is not None and self.ordem < 1:
            errors["ordem"] = "A ordem do tempo começa em 1."

        if (
            self.hora_inicio
            and self.hora_fim
            and self.hora_fim <= self.hora_inicio
        ):
            errors["hora_fim"] = "O fim do tempo deve ser depois do início."

        if errors:
            raise ValidationError(errors)


class AulaGrade(BaseModelEscopado):
    """Slot da grade: este lecionamento ocupa este tempo neste dia."""

    lecionamento = models.ForeignKey(
        Lecionamento, on_delete=models.CASCADE, related_name="slots_grade"
    )
    # Desnormalizado do lecionamento — ver docstring do módulo. Preenchido
    # pelo serializer, nunca pelo payload.
    turma = models.ForeignKey(
        Turma, on_delete=models.PROTECT, related_name="slots_grade"
    )
    # Reusa o enum do lecionamento: 0=segunda ... 6=domingo, alinhado com
    # `date.weekday()` pra projetar datas sem conversão.
    dia_semana = models.IntegerField(choices=Lecionamento.DiaSemana.choices)
    tempo = models.ForeignKey(
        TempoAula, on_delete=models.PROTECT, related_name="slots_grade"
    )
    ativo = models.BooleanField(default=True)

    escola = models.ForeignKey(
        Escola, on_delete=models.PROTECT, related_name="slots_grade"
    )

    history = HistoricalRecords()

    class Meta:
        verbose_name = "aula da grade"
        verbose_name_plural = "aulas da grade"
        ordering = ["turma__nome", "dia_semana", "tempo__ordem"]
        constraints = [
            # Parcial de propósito: o slot desativado fica no banco como
            # histórico da grade antiga, e sem `condition` ele impediria
            # remontar o mesmo horário no ano seguinte.
            models.UniqueConstraint(
                fields=["escola", "turma", "dia_semana", "tempo"],
                condition=models.Q(ativo=True),
                name="aula_grade_unique_turma_dia_tempo_ativo",
            ),
        ]
        indexes = [
            # A tela de chamada (fatia 4) e a projeção da agenda do diário
            # (fatia 5) perguntam "o que esta turma tem neste dia".
            models.Index(
                fields=["turma", "dia_semana"],
                name="grade_idx_turma_dia",
            ),
        ]

    def __str__(self) -> str:
        return (
            f"{self.get_dia_semana_display()}, {self.tempo.ordem}º tempo — "
            f"{self.lecionamento}"
        )

    def clean(self) -> None:
        """Coerência entre lecionamento, turma, tempo e escola."""
        super().clean()
        errors: dict[str, str] = {}

        if self.escola_id:
            for campo in ("lecionamento", "turma", "tempo"):
                valor = getattr(self, f"{campo}_id", None)
                if not valor:
                    continue
                escola_do_campo = getattr(getattr(self, campo), "escola_id", None)
                if escola_do_campo and escola_do_campo != self.escola_id:
                    errors[campo] = (
                        f"O {campo} deve pertencer à mesma escola da grade."
                    )

        # A turma copiada tem que ser a do lecionamento, senão o unique
        # protegeria a grade da turma errada.
        if self.lecionamento_id and self.turma_id:
            if self.lecionamento.turma_id != self.turma_id:
                errors["turma"] = (
                    "A turma do slot deve ser a turma do lecionamento."
                )

        # O catálogo é por turno: um tempo do vespertino numa turma do
        # matutino daria horário que não existe naquele período.
        if self.turma_id and self.tempo_id:
            if self.tempo.turno != self.turma.turno:
                errors["tempo"] = (
                    "O tempo deve ser do mesmo turno da turma."
                )

        if errors:
            raise ValidationError(errors)
