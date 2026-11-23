"""Serviços da app aulas — lógica que não pertence à view nem ao model.

Hoje: projeção da agenda mensal de aulas de um lecionamento. Os "slots"
não são linhas no banco — são calculados a partir dos dias que a **grade
horária** (`apps.grade.AulaGrade`) dá àquele lecionamento e cruzados com
os `RegistroAula` já existentes, de forma parecida com a agregação
on-the-fly do boletim.

A fonte era `Lecionamento.dias_semana` até nov/2026. A grade diz dia **e**
tempo, ou seja, estritamente mais do que o campo dizia, e duas fontes
sobre o mesmo fato divergiriam — então o campo foi removido (fatia 5 do
`PRESENCA.md`). O diário continua sendo **um registro por dia**, não por
tempo: o que importa nele é o conteúdo que o professor deu no dia (ver
`CLAUDE.md`, app `aulas`), então aqui os dias da grade entram
desduplicados e a quantidade de tempos é ignorada de propósito.
"""
import calendar
from datetime import date

from apps.grade.models import AulaGrade

from .models import RegistroAula


def projetar_agenda(
    *, escola_id, professor_id, turma_id, disciplina_id, ano: int, mes: int
) -> list[dict]:
    """Projeta os slots de aula de um lecionamento num mês.

    Cada slot é um dia do mês que cai num dia da semana que a grade dá a
    este lecionamento, anotado com o status do `RegistroAula`
    correspondente (ou `vazio` se o professor ainda não preencheu). Turma
    sem grade montada para este trio retorna lista vazia — nada a
    projetar, como acontecia antes com o campo vazio.
    """
    dias_com_aula = set(
        AulaGrade.objects.filter(
            escola_id=escola_id,
            lecionamento__professor_id=professor_id,
            lecionamento__turma_id=turma_id,
            lecionamento__disciplina_id=disciplina_id,
            ativo=True,
        ).values_list("dia_semana", flat=True)
    )
    if not dias_com_aula:
        return []

    # Registros existentes do mês, indexados por data pra cruzamento O(1).
    registros = {
        registro.data: registro
        for registro in RegistroAula.objects.filter(
            escola_id=escola_id,
            professor_id=professor_id,
            turma_id=turma_id,
            disciplina_id=disciplina_id,
            data__year=ano,
            data__month=mes,
        )
    }

    hoje = date.today()
    _, total_dias = calendar.monthrange(ano, mes)
    slots: list[dict] = []
    for dia in range(1, total_dias + 1):
        atual = date(ano, mes, dia)
        if atual.weekday() not in dias_com_aula:
            continue
        registro = registros.get(atual)
        slots.append(
            {
                "data": atual,
                "dia_semana": atual.weekday(),
                "status": registro.status if registro else "vazio",
                "registro_id": registro.id if registro else None,
                "futuro": atual > hoje,
            }
        )
    return slots
