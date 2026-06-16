"""Serviços da app aulas — lógica que não pertence à view nem ao model.

Hoje: projeção da agenda mensal de aulas de um lecionamento. Os "slots"
não são linhas no banco — são calculados a partir dos `dias_semana` do
`Lecionamento` e cruzados com os `RegistroAula` já existentes, de forma
parecida com a agregação on-the-fly do boletim.
"""
import calendar
from datetime import date

from apps.escola.models import Lecionamento

from .models import RegistroAula


def projetar_agenda(
    *, escola_id, professor_id, turma_id, disciplina_id, ano: int, mes: int
) -> list[dict]:
    """Projeta os slots de aula de um lecionamento num mês.

    Cada slot é um dia do mês que cai num `dias_semana` do lecionamento,
    anotado com o status do `RegistroAula` correspondente (ou `vazio` se
    o professor ainda não preencheu). Sem lecionamento ou sem dias_semana
    definidos, retorna lista vazia (nada a projetar).
    """
    lecionamento = Lecionamento.objects.filter(
        escola_id=escola_id,
        professor_id=professor_id,
        turma_id=turma_id,
        disciplina_id=disciplina_id,
    ).first()
    if lecionamento is None or not lecionamento.dias_semana:
        return []

    dias_com_aula = set(lecionamento.dias_semana)

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
