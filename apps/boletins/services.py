"""Serviços de agregação para o boletim do aluno.

Boletim contínuo: sem persistência, calculado on-the-fly a partir dos
modelos existentes (ItemPresenca, Ocorrencia, EntregaTarefa). Cada
função aqui retorna um dicionário pronto pra serialização JSON.

Convenção de período: se `data_inicio` e/ou `data_fim` forem fornecidos,
filtram pela data do evento (data da chamada, data da ocorrência, data
de lançamento da tarefa). Não fornecer = considera tudo.

Decisão: status `J` (justificado) conta como presença efetiva, pois
costuma vir acompanhado de atestado válido. `A` é a única falta.
"""
from datetime import date
from decimal import Decimal
from typing import Any

from django.db.models import Count, Q

from apps.escola.models import Aluno
from apps.ocorrencias.models import Ocorrencia
from apps.presenca.models import ItemPresenca
from apps.tarefas.models import EntregaTarefa


def _filtro_periodo(
    qs,
    campo_data: str,
    data_inicio: date | None,
    data_fim: date | None,
):
    """Aplica filtro `[data_inicio, data_fim]` (inclusivo nas pontas).

    Strings None nas pontas significam 'sem limite' nesse lado.
    """
    if data_inicio:
        qs = qs.filter(**{f"{campo_data}__gte": data_inicio})
    if data_fim:
        qs = qs.filter(**{f"{campo_data}__lte": data_fim})
    return qs


def calcular_frequencia(
    aluno: Aluno,
    data_inicio: date | None = None,
    data_fim: date | None = None,
) -> dict[str, Any]:
    """Conta itens de presença do aluno, agrupados por status.

    `presencas_efetivas` soma P + R + J (justificado conta como
    presença). `percentual_presenca` é calculado sobre o total.
    """
    qs = ItemPresenca.objects.filter(aluno=aluno)
    qs = _filtro_periodo(qs, "registro__data", data_inicio, data_fim)
    agregado = qs.aggregate(
        total=Count("id"),
        presentes=Count("id", filter=Q(status="P")),
        ausentes=Count("id", filter=Q(status="A")),
        justificados=Count("id", filter=Q(status="J")),
        retardatarios=Count("id", filter=Q(status="R")),
    )
    total = agregado["total"] or 0
    efetivas = (
        agregado["presentes"]
        + agregado["retardatarios"]
        + agregado["justificados"]
    )
    if total > 0:
        percentual = (Decimal(efetivas) / Decimal(total)) * Decimal("100")
        percentual = percentual.quantize(Decimal("0.01"))
    else:
        percentual = Decimal("0.00")
    return {
        "total": total,
        "presentes": agregado["presentes"],
        "ausentes": agregado["ausentes"],
        "justificados": agregado["justificados"],
        "retardatarios": agregado["retardatarios"],
        "presencas_efetivas": efetivas,
        "percentual_presenca": str(percentual),
    }


def calcular_ocorrencias(
    aluno: Aluno,
    data_inicio: date | None = None,
    data_fim: date | None = None,
) -> dict[str, Any]:
    """Conta ocorrências do aluno por status."""
    qs = Ocorrencia.objects.filter(aluno=aluno)
    qs = _filtro_periodo(qs, "data_ocorrencia", data_inicio, data_fim)
    agregado = qs.aggregate(
        total=Count("id"),
        abertas=Count("id", filter=Q(status="aberta")),
        em_andamento=Count("id", filter=Q(status="em_andamento")),
        resolvidas=Count("id", filter=Q(status="resolvida")),
        arquivadas=Count("id", filter=Q(status="arquivada")),
    )
    return {
        "total": agregado["total"] or 0,
        "abertas": agregado["abertas"],
        "em_andamento": agregado["em_andamento"],
        "resolvidas": agregado["resolvidas"],
        "arquivadas": agregado["arquivadas"],
    }


def calcular_notas_por_disciplina(
    aluno: Aluno,
    data_inicio: date | None = None,
    data_fim: date | None = None,
) -> list[dict[str, Any]]:
    """Agrupa entregas com nota por disciplina e calcula média ponderada.

    Considera apenas entregas onde `nota` foi preenchida e a tarefa
    vale nota. Média = Σ(nota × peso) / Σ(peso). Sem tarefas com nota,
    a disciplina não aparece no boletim.

    O agrupamento é feito em Python (em vez de SQL puro) porque
    `disciplina__nome` é mais legível e o volume é pequeno (entregas de
    um aluno).
    """
    entregas = (
        EntregaTarefa.objects
        .filter(aluno=aluno, tarefa__vale_nota=True, nota__isnull=False)
        .select_related("tarefa", "tarefa__disciplina")
    )
    entregas = _filtro_periodo(
        entregas, "tarefa__data_lancamento", data_inicio, data_fim
    )

    por_disciplina: dict[int, dict[str, Any]] = {}
    for entrega in entregas:
        tarefa = entrega.tarefa
        disciplina = tarefa.disciplina
        bucket = por_disciplina.setdefault(
            disciplina.id,
            {
                "disciplina": {"id": disciplina.id, "nome": disciplina.nome},
                "tarefas": [],
                "_soma_ponderada": Decimal("0"),
                "_soma_pesos": Decimal("0"),
            },
        )
        bucket["tarefas"].append(
            {
                "tarefa_id": tarefa.id,
                "titulo": tarefa.titulo,
                "nota": str(entrega.nota),
                "nota_maxima": (
                    str(tarefa.nota_maxima) if tarefa.nota_maxima else None
                ),
                "peso": str(tarefa.peso),
                "data_lancamento": tarefa.data_lancamento.isoformat(),
            }
        )
        bucket["_soma_ponderada"] += entrega.nota * tarefa.peso
        bucket["_soma_pesos"] += tarefa.peso

    resultado = []
    for bucket in por_disciplina.values():
        soma_pesos = bucket.pop("_soma_pesos")
        soma_ponderada = bucket.pop("_soma_ponderada")
        media = (
            (soma_ponderada / soma_pesos).quantize(Decimal("0.01"))
            if soma_pesos > 0
            else Decimal("0.00")
        )
        bucket["media_ponderada"] = str(media)
        resultado.append(bucket)
    # Ordena pra resposta estável.
    resultado.sort(key=lambda d: d["disciplina"]["nome"])
    return resultado


def montar_boletim(
    aluno: Aluno,
    data_inicio: date | None = None,
    data_fim: date | None = None,
) -> dict[str, Any]:
    """Compose final do boletim — agrega as três frentes."""
    return {
        "aluno": {
            "id": aluno.id,
            "nome_completo": aluno.nome_completo,
            "matricula": aluno.matricula,
            "ativo": aluno.ativo,
        },
        "turma": {
            "id": aluno.turma_id,
            "nome": aluno.turma.nome if aluno.turma_id else None,
        },
        "periodo": {
            "data_inicio": data_inicio.isoformat() if data_inicio else None,
            "data_fim": data_fim.isoformat() if data_fim else None,
        },
        "frequencia": calcular_frequencia(aluno, data_inicio, data_fim),
        "notas_por_disciplina": calcular_notas_por_disciplina(
            aluno, data_inicio, data_fim
        ),
        "ocorrencias": calcular_ocorrencias(aluno, data_inicio, data_fim),
    }
