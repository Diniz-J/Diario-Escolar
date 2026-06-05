"""Serviços de agregação para o boletim do aluno.

Boletim contínuo: sem persistência, calculado on-the-fly a partir dos
modelos existentes. Cada função aqui retorna um dicionário pronto pra
serialização JSON.

Estrutura desde PR #5 (refator da frente de avaliação):

- `frequencia`: agregado de `ItemPresenca` (P/R/J contam como presença
  efetiva; só `A` é falta).
- `notas_por_disciplina`: agrega `NotaAvaliacao` (provas individuais)
  + `NotaPeriodo` (média final digitada pelo professor). **O sistema
  NÃO calcula média**; a escola decide a régua e digita a média final.
  Ver `apps/avaliacao/models.py` pra raciocínio.
- `ocorrencias`: contadores por status.

Convenção de período: 2 modos de filtrar.
- **Por intervalo de datas** (`data_inicio`/`data_fim`): filtra eventos
  (chamada, ocorrência, avaliação) por data. Compatível com versões
  anteriores do boletim.
- **Por período avaliativo** (`periodo_id`): atalho pra "boletim do
  bimestre X" — converte pra `data_inicio`/`data_fim` do período
  automaticamente. Resposta inclui `periodo_nome` agregado.
"""
from datetime import date
from decimal import Decimal
from typing import Any

from django.db.models import Count, Q

from apps.avaliacao.models import (
    Avaliacao,
    NotaAvaliacao,
    NotaPeriodo,
    PeriodoAvaliativo,
)
from apps.escola.models import Aluno
from apps.ocorrencias.models import Ocorrencia
from apps.presenca.models import ItemPresenca


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
    """Agrupa notas do aluno por disciplina, **sem calcular média**.

    Cada bucket contém:
    - `avaliacoes`: lista de `NotaAvaliacao` (provas/trabalhos
      individuais) com a nota lançada — só inclui as que têm `nota`
      preenchida.
    - `notas_finais_por_periodo`: lista de `NotaPeriodo.nota_final`
      digitadas pelo professor (uma por período relevante). Pode estar
      vazia se o professor ainda não fechou nenhum período.

    Filtro por data se aplica à `Avaliacao.data`; `NotaPeriodo` é
    filtrada por `periodo.data_inicio/data_fim` cruzando com a janela.
    Disciplinas sem nada no escopo não aparecem no resultado.

    Reflete a decisão de produto: o sistema só armazena, a escola
    decide a média final (que aparece como `nota_final` no respectivo
    `NotaPeriodo`).
    """
    # 1) Notas individuais (NotaAvaliacao).
    notas_qs = (
        NotaAvaliacao.objects.filter(aluno=aluno, nota__isnull=False)
        .select_related(
            "avaliacao", "avaliacao__disciplina", "avaliacao__periodo"
        )
    )
    notas_qs = _filtro_periodo(
        notas_qs, "avaliacao__data", data_inicio, data_fim
    )

    por_disciplina: dict[int, dict[str, Any]] = {}
    for nota in notas_qs:
        avaliacao = nota.avaliacao
        disciplina = avaliacao.disciplina
        bucket = por_disciplina.setdefault(
            disciplina.id,
            {
                "disciplina": {"id": disciplina.id, "nome": disciplina.nome},
                "avaliacoes": [],
                "notas_finais_por_periodo": [],
            },
        )
        bucket["avaliacoes"].append(
            {
                "avaliacao_id": avaliacao.id,
                "titulo": avaliacao.titulo,
                "tipo": avaliacao.tipo,
                "tipo_display": avaliacao.get_tipo_display(),
                "data": avaliacao.data.isoformat(),
                "nota_maxima": str(avaliacao.nota_maxima),
                "peso": str(avaliacao.peso),
                "nota_obtida": str(nota.nota),
                "periodo_nome": (
                    avaliacao.periodo.nome if avaliacao.periodo_id else None
                ),
            }
        )

    # 2) Médias finais por período (NotaPeriodo).
    finais_qs = (
        NotaPeriodo.objects.filter(aluno=aluno, nota_final__isnull=False)
        .select_related("disciplina", "periodo")
    )
    # Filtra por janela de datas cruzando com período (overlapping).
    if data_inicio:
        finais_qs = finais_qs.filter(periodo__data_fim__gte=data_inicio)
    if data_fim:
        finais_qs = finais_qs.filter(periodo__data_inicio__lte=data_fim)

    for final in finais_qs:
        disciplina = final.disciplina
        bucket = por_disciplina.setdefault(
            disciplina.id,
            {
                "disciplina": {"id": disciplina.id, "nome": disciplina.nome},
                "avaliacoes": [],
                "notas_finais_por_periodo": [],
            },
        )
        bucket["notas_finais_por_periodo"].append(
            {
                "periodo_id": final.periodo_id,
                "periodo_nome": final.periodo.nome,
                "nota_final": str(final.nota_final),
                # `observacao` propositalmente OMITIDA — nota interna
                # do professor, fora do boletim do responsável.
            }
        )

    # Ordena listas internas pra resposta estável.
    resultado = []
    for bucket in por_disciplina.values():
        bucket["avaliacoes"].sort(key=lambda a: a["data"])
        bucket["notas_finais_por_periodo"].sort(
            key=lambda n: n["periodo_id"]
        )
        resultado.append(bucket)
    resultado.sort(key=lambda d: d["disciplina"]["nome"])
    return resultado


def resolver_janela_por_periodo(
    periodo_id: int | None,
) -> tuple[date | None, date | None, PeriodoAvaliativo | None]:
    """Converte `periodo_id` em (data_inicio, data_fim, periodo_obj).

    Atalho usado pelo endpoint `/boletins/aluno/{id}/?periodo=X` — em
    vez do cliente passar datas manuais, passa o id do período e o
    backend resolve.

    Retorna `(None, None, None)` se `periodo_id` é falsy (boletim anual
    / sem filtro).
    """
    if not periodo_id:
        return None, None, None
    try:
        periodo = PeriodoAvaliativo.objects.get(pk=periodo_id)
    except PeriodoAvaliativo.DoesNotExist:
        return None, None, None
    return periodo.data_inicio, periodo.data_fim, periodo


def listar_avaliacoes_do_aluno(
    aluno: Aluno,
    data_inicio: date | None = None,
    data_fim: date | None = None,
) -> list[dict[str, Any]]:
    """Lista plana de todas as avaliações do aluno (com ou sem nota).

    Usado pelo export CSV/XLSX individual: cada linha = uma
    NotaAvaliacao do aluno na janela, mesmo se a nota ainda não foi
    lançada (`nota_obtida` fica vazia). Já inclui dados denormalizados
    pra resposta abrir direto no Excel.
    """
    qs = (
        NotaAvaliacao.objects.filter(aluno=aluno)
        .select_related(
            "avaliacao",
            "avaliacao__disciplina",
            "avaliacao__periodo",
            "avaliacao__turma",
        )
        .order_by(
            "avaliacao__data",
            "avaliacao__disciplina__nome",
            "avaliacao__titulo",
        )
    )
    qs = _filtro_periodo(qs, "avaliacao__data", data_inicio, data_fim)

    linhas: list[dict[str, Any]] = []
    for nota in qs:
        avaliacao = nota.avaliacao
        linhas.append(
            {
                "disciplina": avaliacao.disciplina.nome,
                "periodo": (
                    avaliacao.periodo.nome if avaliacao.periodo_id else "—"
                ),
                "data": avaliacao.data.isoformat(),
                "tipo": avaliacao.get_tipo_display(),
                "titulo": avaliacao.titulo,
                "nota_maxima": str(avaliacao.nota_maxima),
                "nota_obtida": (
                    str(nota.nota) if nota.nota is not None else ""
                ),
                "peso": str(avaliacao.peso),
            }
        )
    return linhas


def montar_boletim(
    aluno: Aluno,
    data_inicio: date | None = None,
    data_fim: date | None = None,
    periodo: PeriodoAvaliativo | None = None,
) -> dict[str, Any]:
    """Compose final do boletim — agrega frequência, notas e ocorrências.

    Quando `periodo` é fornecido (atalho de "boletim do bimestre X"),
    aparece no JSON como objeto separado pra UI exibir o título
    correto ("Boletim do 1º Bimestre" em vez de "Boletim de
    01/02/2026 a 30/04/2026").
    """
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
            "ano_letivo": (
                aluno.turma.ano_letivo if aluno.turma_id else None
            ),
        },
        "escola": {
            "id": aluno.escola_id,
            "nome": aluno.escola.nome if aluno.escola_id else None,
        },
        "periodo": {
            "data_inicio": data_inicio.isoformat() if data_inicio else None,
            "data_fim": data_fim.isoformat() if data_fim else None,
            "id": periodo.id if periodo else None,
            "nome": periodo.nome if periodo else None,
            "ano_letivo": periodo.ano_letivo if periodo else None,
        },
        "frequencia": calcular_frequencia(aluno, data_inicio, data_fim),
        "notas_por_disciplina": calcular_notas_por_disciplina(
            aluno, data_inicio, data_fim
        ),
        "ocorrencias": calcular_ocorrencias(aluno, data_inicio, data_fim),
    }
