"""Agregações dos relatórios operacionais.

App sem modelo, no mesmo molde de `apps/boletins` — tudo é calculado
on-the-fly a partir do que já está persistido.

Mora aqui também `metricas_dashboard`, que não é relatório exportável e
sim o par de agregados que o dashboard consome (presença média e
reincidência de ocorrências) — está nesta app porque a régua de presença
efetiva é daqui.

Regra de frequência: `P`, `R` e `J` contam como presença efetiva, só `A`
é falta. É a mesma régua do boletim
(`apps/boletins/services.py:calcular_frequencia`) e tem teste travando
que as duas não divergem: se alguém mudar uma, a suíte acusa.
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from django.db.models import Count, Q
from django.utils import timezone

from apps.escola.models import Aluno, Turma
from apps.presenca.models import ItemPresenca, RegistroPresenca

# Mínimo legal de frequência (LDB, art. 24, VI). Fica aqui, e não no
# settings, porque é regra do ensino básico brasileiro e não
# configuração de instalação — escola nenhuma escolhe esse número.
LIMITE_FREQUENCIA = Decimal("75")

# Status que contam como presença efetiva no cálculo.
_STATUS_EFETIVOS = (
    ItemPresenca.Status.PRESENTE,
    ItemPresenca.Status.RETARDATARIO,
    ItemPresenca.Status.JUSTIFICADO,
)


def calcular_percentual(total: int, efetivas: int) -> Decimal:
    """Percentual de presença com 2 casas. Sem chamada registrada → 0.

    Turma sem nenhuma chamada na janela devolve 0,00 em vez de explodir
    numa divisão por zero. O relatório mostra o total de chamadas ao
    lado, então o leitor distingue "ninguém veio" de "ninguém fez
    chamada".
    """
    if total <= 0:
        return Decimal("0.00")
    percentual = (Decimal(efetivas) / Decimal(total)) * Decimal("100")
    return percentual.quantize(Decimal("0.01"))


def _filtro_janela(
    data_inicio: date | None,
    data_fim: date | None,
    *,
    prefixo: str,
) -> Q:
    """Monta o filtro de janela sobre a data do registro de chamada.

    `prefixo` é o caminho até o `RegistroPresenca` a partir do modelo
    que está sendo anotado ("presencas__registro" a partir do Aluno,
    vazio a partir do próprio registro). Ponta ausente significa "sem
    limite nesse lado", igual ao boletim.
    """
    campo = f"{prefixo}__data" if prefixo else "data"
    filtro = Q()
    if data_inicio:
        filtro &= Q(**{f"{campo}__gte": data_inicio})
    if data_fim:
        filtro &= Q(**{f"{campo}__lte": data_fim})
    return filtro


def frequencia_por_turma(
    turma: Turma,
    data_inicio: date | None = None,
    data_fim: date | None = None,
) -> dict[str, Any]:
    """Frequência de cada aluno da turma na janela, numa query só.

    Os contadores saem como agregados condicionais anotados sobre o
    `Aluno` (um JOIN, `Count` com `filter` por status) em vez de chamar
    `calcular_frequencia` aluno por aluno: numa turma de 35 isso seria
    35 queries, e o relatório existe justamente pra turma inteira.

    **Só contam as chamadas DESTA turma.** O relatório é por turma, não
    por aluno (o boletim é que é por aluno): o aluno remanejado da A pra
    B no meio do ano aparece no relatório da A com as chamadas da A e no
    da B com as da B — nunca com as da outra. Contar todas as presenças
    do aluno fazia o remanejado levar as faltas da turma antiga pra nova
    (e o total dele passar o `total_chamadas` da turma), e a promoção de
    ano que só troca a turma arrastava o ano anterior inteiro.

    Quem entra na lista: todo aluno **ativo** que está na turma hoje, mais
    quem tem chamada **nesta turma** na janela — o inativo que estudou
    parte do período e o remanejado que já saiu. Omiti-los faria as
    faltas deles desaparecerem do relatório e o total mentir.
    """
    janela = _filtro_janela(data_inicio, data_fim, prefixo="presencas__registro")
    # Todo `Count` filtra pela turma do REGISTRO, não pela turma atual do
    # aluno (`presencas__registro__turma`).
    nesta_turma = Q(presencas__registro__turma=turma) & janela

    def _contar(status: str | None = None) -> Count:
        filtro = nesta_turma
        if status:
            filtro = filtro & Q(presencas__status=status)
        return Count("presencas", filter=filtro)

    # `pk__in` com subquery (e não um JOIN no filtro) pra a lista não
    # multiplicar as linhas que os `Count` abaixo agregam.
    com_chamada_aqui = ItemPresenca.objects.filter(
        registro__turma=turma
    ).filter(_filtro_janela(data_inicio, data_fim, prefixo="registro"))
    alunos_qs = (
        Aluno.objects.filter(
            Q(turma=turma, ativo=True)
            | Q(pk__in=com_chamada_aqui.values("aluno_id"))
        )
        .annotate(
            total=_contar(),
            presentes=_contar(ItemPresenca.Status.PRESENTE),
            ausentes=_contar(ItemPresenca.Status.AUSENTE),
            justificados=_contar(ItemPresenca.Status.JUSTIFICADO),
            retardatarios=_contar(ItemPresenca.Status.RETARDATARIO),
        )
        .order_by("nome_completo", "pk")
    )

    linhas: list[dict[str, Any]] = []
    soma_total = 0
    soma_efetivas = 0
    for aluno in alunos_qs:
        efetivas = aluno.presentes + aluno.retardatarios + aluno.justificados
        percentual = calcular_percentual(aluno.total, efetivas)
        soma_total += aluno.total
        soma_efetivas += efetivas
        linhas.append(
            {
                "aluno_id": aluno.pk,
                "matricula": aluno.matricula,
                "nome_completo": aluno.nome_completo,
                "ativo": aluno.ativo,
                "total": aluno.total,
                "presentes": aluno.presentes,
                "ausentes": aluno.ausentes,
                "justificados": aluno.justificados,
                "retardatarios": aluno.retardatarios,
                "presencas_efetivas": efetivas,
                "percentual_presenca": str(percentual),
                # Aluno sem nenhuma chamada na janela fica fora do
                # alerta: 0% ali significa "não há dado", e apontá-lo
                # como infrequente mandaria a secretaria atrás de um
                # problema que não existe.
                "abaixo_do_limite": (
                    aluno.total > 0 and percentual < LIMITE_FREQUENCIA
                ),
            }
        )

    total_chamadas = RegistroPresenca.objects.filter(
        turma=turma
    ).filter(_filtro_janela(data_inicio, data_fim, prefixo="")).count()

    return {
        "turma": {
            "id": turma.pk,
            "nome": turma.nome,
            "turno": turma.get_turno_display(),
            "ano_letivo": turma.ano_letivo,
        },
        "janela": {
            "data_inicio": data_inicio.isoformat() if data_inicio else None,
            "data_fim": data_fim.isoformat() if data_fim else None,
        },
        "limite_frequencia": str(LIMITE_FREQUENCIA.quantize(Decimal("0.01"))),
        "total_chamadas": total_chamadas,
        "alunos": linhas,
        "resumo": {
            "total_alunos": len(linhas),
            "abaixo_do_limite": sum(
                1 for linha in linhas if linha["abaixo_do_limite"]
            ),
            # Frequência da turma como um todo: efetivas sobre o total
            # de registros, NÃO a média das porcentagens individuais —
            # a média de médias distorce quando um aluno entrou no meio
            # do período e tem menos chamadas que os outros.
            "percentual_turma": str(
                calcular_percentual(soma_total, soma_efetivas)
            ),
        },
    }


def linhas_planas(relatorio: dict[str, Any]) -> tuple[list[str], list[list[Any]]]:
    """Converte o relatório em cabeçalho + linhas, pro CSV/XLSX.

    Vive aqui e não na view porque a ordem das colunas é parte do
    relatório: a secretaria abre o arquivo no Excel e espera matrícula e
    nome primeiro.
    """
    headers = [
        "matricula",
        "nome",
        "situacao",
        "chamadas",
        "presencas",
        "faltas",
        "justificadas",
        "retardatarios",
        "presencas_efetivas",
        "percentual_presenca",
        "abaixo_do_limite",
    ]
    linhas = [
        [
            linha["matricula"],
            linha["nome_completo"],
            "ativo" if linha["ativo"] else "inativo",
            linha["total"],
            linha["presentes"],
            linha["ausentes"],
            linha["justificados"],
            linha["retardatarios"],
            linha["presencas_efetivas"],
            linha["percentual_presenca"],
            "sim" if linha["abaixo_do_limite"] else "nao",
        ]
        for linha in relatorio["alunos"]
    ]
    return headers, linhas


# Teto de linhas do PDF de ocorrências. O recorte da tela pode ser um ano
# inteiro da escola; o WeasyPrint é síncrono na request e um PDF de dez
# mil blocos derruba o worker no free tier. CSV e XLSX não têm teto — o
# custo deles é linear e barato, e é pra onde o erro manda quem precisa
# do recorte inteiro.
LIMITE_PDF_OCORRENCIAS = 1000


def _nome_do_professor(ocorrencia) -> str:
    """Nome legível do professor, ou vazio quando a ocorrência não tem um.

    `professor` é opcional no modelo (a direção registra sem vincular),
    então não dá pra assumir que existe.
    """
    professor = ocorrencia.professor
    if professor is None:
        return ""
    return professor.usuario.get_full_name() or professor.usuario.username


def linhas_ocorrencias(ocorrencias) -> tuple[list[str], list[list[Any]]]:
    """Cabeçalho + linhas do export plano de ocorrências.

    Resolve nome de turma, aluno e professor em vez de devolver id: a
    planilha é lida fora do sistema, onde `turma=7` não quer dizer nada.
    Quem chama precisa ter feito `select_related` — ver a action
    `exportar` do `OcorrenciaViewSet`.
    """
    headers = [
        "data",
        "turma",
        "aluno",
        "matricula",
        "professor",
        "status",
        "descricao",
    ]
    linhas = [
        [
            ocorrencia.data_ocorrencia.isoformat(),
            ocorrencia.turma.nome,
            ocorrencia.aluno.nome_completo,
            ocorrencia.aluno.matricula,
            _nome_do_professor(ocorrencia),
            ocorrencia.get_status_display(),
            ocorrencia.descricao,
        ]
        for ocorrencia in ocorrencias
    ]
    return headers, linhas


def agrupar_ocorrencias_por_aluno(ocorrencias) -> list[dict[str, Any]]:
    """Agrupa as ocorrências por aluno, preservando a ordem recebida.

    O PDF vai pra conselho de classe, e ali a pergunta é sempre "o que
    houve com este aluno", não "o que houve nesta terça" — por isso
    agrupa por aluno e não cronologicamente, ao contrário do diário de
    aula. A ordem dos grupos segue a primeira aparição, então o recorte
    ordenado por data mais recente coloca na frente quem teve o último
    registro.

    Em Python, sobre a lista já materializada: agrupar no banco custaria
    outra query e o conjunto já está na memória pra render mesmo.
    """
    grupos: dict[int, dict[str, Any]] = {}
    for ocorrencia in ocorrencias:
        grupo = grupos.setdefault(
            ocorrencia.aluno_id,
            {
                "aluno_nome": ocorrencia.aluno.nome_completo,
                "matricula": ocorrencia.aluno.matricula,
                "turma_nome": ocorrencia.turma.nome,
                "ocorrencias": [],
            },
        )
        grupo["ocorrencias"].append(
            {
                "data": ocorrencia.data_ocorrencia,
                "status": ocorrencia.status,
                "status_display": ocorrencia.get_status_display(),
                "professor_nome": _nome_do_professor(ocorrencia),
                "descricao": ocorrencia.descricao,
            }
        )
    return list(grupos.values())


def contar_ocorrencias_por_status(ocorrencias) -> dict[str, int]:
    """Contadores por status do recorte, pra faixa de resumo do PDF."""
    from apps.ocorrencias.models import Ocorrencia

    contagem = {status: 0 for status in Ocorrencia.Status.values}
    for ocorrencia in ocorrencias:
        # `.get()` e não `contagem[...] += 1`: nada no banco impede um
        # status que saiu do enum (migração antiga, valor removido), e
        # ali isso seria `KeyError` — um 500 no download por causa de uma
        # linha velha. O template lê só os quatro status conhecidos, e o
        # total continua contando todas as linhas.
        contagem[ocorrencia.status] = contagem.get(ocorrencia.status, 0) + 1
    return contagem


# Teto de linhas do PDF cadastral. Mesma razão do teto de ocorrências: o
# recorte pode ser a escola inteira e o WeasyPrint é síncrono na request.
# Uma escola de porte médio cabe; a rede inteira não, e o erro manda pro
# CSV/XLSX.
LIMITE_PDF_ALUNOS = 1500


def linhas_alunos(alunos) -> tuple[list[str], list[list[Any]]]:
    """Cabeçalho + linhas do relatório cadastral.

    Traz o nome da turma, não o id: a planilha é lida fora do sistema.
    Data vazia sai como string vazia em vez de "None" — a secretaria
    imprime isso e entrega pra alguém preencher à mão.

    Quem chama precisa ter feito `select_related("turma")`.
    """
    headers = [
        "matricula",
        "nome",
        "data_nascimento",
        "turma",
        "situacao",
        "responsavel",
        "email_responsavel",
    ]
    linhas = [
        [
            aluno.matricula,
            aluno.nome_completo,
            aluno.data_nascimento.isoformat() if aluno.data_nascimento else "",
            aluno.turma.nome,
            "ativo" if aluno.ativo else "inativo",
            aluno.nome_responsavel,
            aluno.email_responsavel,
        ]
        for aluno in alunos
    ]
    return headers, linhas


def agrupar_alunos_por_turma(alunos) -> list[dict[str, Any]]:
    """Agrupa os alunos por turma, preservando a ordem recebida.

    O cadastral impresso serve de lista de turma, então sai separado por
    turma mesmo quando o recorte é a escola toda — uma lista corrida de
    400 nomes não serve pra nada em cima de uma mesa.
    """
    grupos: dict[int, dict[str, Any]] = {}
    for aluno in alunos:
        grupo = grupos.setdefault(
            aluno.turma_id,
            {
                "turma_nome": aluno.turma.nome,
                "turno": aluno.turma.get_turno_display(),
                "ano_letivo": aluno.turma.ano_letivo,
                "alunos": [],
            },
        )
        grupo["alunos"].append(aluno)
    return list(grupos.values())


# Janela default das métricas do dashboard, em dias (hoje incluso). O
# dashboard responde "o que está acontecendo agora", então a janela é
# curta de propósito: num recorte anual a presença média de março
# continuaria pesando no número de outubro e o card pararia de reagir ao
# mês corrente.
JANELA_DASHBOARD_DIAS = 30

# A partir de quantas ocorrências na janela o aluno conta como
# reincidente. Dois é o menor número que caracteriza repetição — a
# métrica existe pra direção enxergar quem voltou a aparecer, não pra
# contar quem apareceu uma vez.
LIMIAR_REINCIDENCIA = 2


def _janela_recente(dias: int) -> tuple[date, date]:
    """Janela fechada de `dias` datas terminando hoje.

    `dias - 1` porque as duas pontas são inclusivas: 30 dias contados de
    hoje pra trás cobrem 30 datas, não 31.
    """
    hoje = timezone.localdate()
    return hoje - timedelta(days=dias - 1), hoje


def metricas_dashboard(
    escola_id: int | None,
    turma: Turma | None = None,
    dias: int = JANELA_DASHBOARD_DIAS,
) -> dict[str, Any]:
    """Presença média e reincidência de ocorrências na janela recente.

    As duas métricas que faltavam no dashboard (`CLAUDE.md`, FASE 3
    item 8). Vivem aqui, e não numa app `dashboard` nova, porque a régua
    de presença efetiva (`_STATUS_EFETIVOS` + `calcular_percentual`) é
    desta app: uma terceira cópia dela é exatamente o que o teste de
    não-divergência entre boletim e relatório existe pra impedir.

    `escola_id=None` significa "sem filtro de escola" — é o admin global,
    que no resto do projeto enxerga todas (ver `eh_admin_global`). Quem
    chama resolve isso; aqui `None` é literal.

    **Presença média é sobre registros, não média de médias**: efetivas
    divididas pelo total de itens da janela. A média das porcentagens
    individuais distorceria pelo aluno que entrou no meio do período e
    tem menos chamadas que os outros — mesmo raciocínio do
    `percentual_turma` em `frequencia_por_turma`.

    **Reincidência é contada em Python** sobre uma lista de contadores
    por aluno (um por aluno COM ocorrência na janela, portanto dezenas,
    não milhares). Resolver em SQL exigiria `HAVING` sobre a anotação
    dentro de um `aggregate`, e o que se ganharia em elegância se
    perderia na leitura — a lista também dá de graça o total de alunos
    envolvidos e o total de ocorrências, que o card usa na sublinha.
    """
    data_inicio, data_fim = _janela_recente(dias)

    itens = ItemPresenca.objects.filter(
        registro__data__gte=data_inicio, registro__data__lte=data_fim
    )
    chamadas = RegistroPresenca.objects.filter(
        data__gte=data_inicio, data__lte=data_fim
    )
    ocorrencias_do_aluno = Q(
        ocorrencias__data_ocorrencia__gte=data_inicio,
        ocorrencias__data_ocorrencia__lte=data_fim,
    )
    alunos = Aluno.objects.all()

    if escola_id is not None:
        itens = itens.filter(escola_id=escola_id)
        chamadas = chamadas.filter(escola_id=escola_id)
        alunos = alunos.filter(escola_id=escola_id)

    if turma is not None:
        # Filtra pela turma do REGISTRO e da OCORRÊNCIA, não pela turma
        # atual do aluno: o remanejado no meio do ano levaria pra turma
        # nova as faltas e as ocorrências da antiga. Mesma decisão de
        # `frequencia_por_turma`.
        itens = itens.filter(registro__turma=turma)
        chamadas = chamadas.filter(turma=turma)
        ocorrencias_do_aluno &= Q(ocorrencias__turma=turma)

    presenca = itens.aggregate(
        total=Count("pk"),
        efetivas=Count("pk", filter=Q(status__in=_STATUS_EFETIVOS)),
    )
    total_itens = presenca["total"] or 0
    efetivas = presenca["efetivas"] or 0

    contagens = list(
        alunos.annotate(qtd=Count("ocorrencias", filter=ocorrencias_do_aluno))
        .filter(qtd__gt=0)
        .values_list("qtd", flat=True)
    )

    percentual = calcular_percentual(total_itens, efetivas)
    return {
        "janela": {
            "dias": dias,
            "data_inicio": data_inicio.isoformat(),
            "data_fim": data_fim.isoformat(),
        },
        "turma_id": turma.pk if turma is not None else None,
        "presenca": {
            "percentual_medio": str(percentual),
            "total_itens": total_itens,
            "presencas_efetivas": efetivas,
            "total_chamadas": chamadas.count(),
            # Sem chamada na janela o percentual é 0,00 por definição de
            # `calcular_percentual`. O front precisa distinguir isso de
            # "ninguém veio", senão o card acusa 0% de presença numa
            # escola que só não fez chamada ainda.
            "abaixo_do_limite": (
                total_itens > 0 and percentual < LIMITE_FREQUENCIA
            ),
            "limite_frequencia": str(
                LIMITE_FREQUENCIA.quantize(Decimal("0.01"))
            ),
        },
        "reincidencia": {
            "limiar": LIMIAR_REINCIDENCIA,
            "alunos_reincidentes": sum(
                1 for qtd in contagens if qtd >= LIMIAR_REINCIDENCIA
            ),
            "alunos_com_ocorrencia": len(contagens),
            "total_ocorrencias": sum(contagens),
        },
    }
