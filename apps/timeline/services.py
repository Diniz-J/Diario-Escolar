"""Agregação da timeline do aluno (item 13 do roadmap).

App sem modelo, no molde de `apps/boletins` e `apps/relatorios`: nada é
persistido, tudo é montado on-the-fly a partir do que já existe. A
timeline responde "o que aconteceu com este aluno", em ordem
cronológica, juntando três origens:

- **ocorrências** (`apps.ocorrencias`) — com status e autor;
- **presença** (`apps.presenca`) — só o que fugiu do normal;
- **histórico cadastral** (`Aluno.history`, do simple-history) — é o
  "reaproveitar a API HistoricalRecords" que o roadmap pede.

Duas decisões que não se deduzem do código:

**Presença entra pelo que NÃO é presença.** O item `P` fica fora: um ano
letivo rende ~200 "veio à aula", que afogariam as cinco linhas que
importam. Já `A`, `J` e `R` entram todos — e aqui a régua é
deliberadamente **diferente** da frequência (`apps/relatorios/services.py`,
onde `J` e `R` contam como presença efetiva). Não é divergência a
corrigir: lá a pergunta é "quantas faltas tem", aqui é "o que
aconteceu", e chegar atrasado ou faltar com atestado aconteceu.

**O histórico cadastral é lido inteiro, não filtrado pela janela.** Cada
evento nasce da comparação de uma entrada com a anterior, e filtrar no
banco deixaria de fora justamente a entrada anterior à janela — a
primeira mudança do recorte apareceria comparada com nada. Por isso o
filtro de janela é aplicado depois, sobre os eventos já montados.
"""
from __future__ import annotations

from datetime import date
from typing import Any, Iterator

from apps.escola.models import Aluno, Turma
from apps.presenca.models import ItemPresenca

# Teto de eventos devolvidos. A timeline não é paginada (é uma leitura
# cronológica, não uma listagem navegável), então o teto é o que impede
# a resposta de crescer sem limite num aluno com anos de histórico. O
# front avisa que o recorte foi cortado e oferece a janela de datas.
LIMITE_EVENTOS = 500

TIPO_OCORRENCIA = "ocorrencia"
TIPO_PRESENCA = "presenca"
TIPO_CADASTRO = "cadastro"

# Campos do cadastro que viram evento. É uma lista de permissão, e não
# "tudo menos X", por um motivo de privacidade: `nome_responsavel` e
# `email_responsavel` estão de fora porque a timeline é lida também por
# professor e inspetor, e o dado de contato do responsável é
# nível-direção no resto do sistema (é por isso que o relatório
# cadastral de alunos exige WRITE_PERMISSION). Os quatro daqui já
# aparecem na listagem de alunos pra qualquer perfil.
CAMPOS_CADASTRAIS = ("turma_id", "ativo", "matricula", "nome_completo")


def _no_intervalo(
    dia: date, data_inicio: date | None, data_fim: date | None
) -> bool:
    """Janela inclusiva nas duas pontas; `None` é 'sem limite' no lado."""
    if data_inicio and dia < data_inicio:
        return False
    if data_fim and dia > data_fim:
        return False
    return True


def _nome_do_professor(professor) -> str:
    """Nome legível do professor, ou vazio quando não há um.

    `Ocorrencia.professor` é opcional (a direção registra sem vincular).
    """
    if professor is None:
        return ""
    return professor.usuario.get_full_name() or professor.usuario.username


def _eventos_de_ocorrencias(
    aluno: Aluno, data_inicio: date | None, data_fim: date | None
) -> Iterator[dict[str, Any]]:
    qs = aluno.ocorrencias.select_related("turma", "professor__usuario")
    if data_inicio:
        qs = qs.filter(data_ocorrencia__gte=data_inicio)
    if data_fim:
        qs = qs.filter(data_ocorrencia__lte=data_fim)
    for ocorrencia in qs:
        yield {
            "tipo": TIPO_OCORRENCIA,
            "data": ocorrencia.data_ocorrencia.isoformat(),
            "titulo": "Ocorrência",
            "detalhe": ocorrencia.descricao,
            "status": ocorrencia.status,
            "status_label": ocorrencia.get_status_display(),
            "turma": ocorrencia.turma.nome,
            "autor": _nome_do_professor(ocorrencia.professor),
            # O front monta a rota a partir do tipo (`/ocorrencias/<id>`
            # ou `/presenca/<id>`); o serviço não conhece rota de UI.
            "referencia_id": ocorrencia.pk,
            "_ordem": ocorrencia.criado_em,
        }


def _eventos_de_presenca(
    aluno: Aluno, data_inicio: date | None, data_fim: date | None
) -> Iterator[dict[str, Any]]:
    qs = (
        ItemPresenca.objects.filter(aluno=aluno)
        .exclude(status=ItemPresenca.Status.PRESENTE)
        .select_related("registro", "registro__turma")
    )
    if data_inicio:
        qs = qs.filter(registro__data__gte=data_inicio)
    if data_fim:
        qs = qs.filter(registro__data__lte=data_fim)
    for item in qs:
        yield {
            "tipo": TIPO_PRESENCA,
            "data": item.registro.data.isoformat(),
            "titulo": item.get_status_display(),
            "detalhe": item.observacao,
            "status": item.status,
            "status_label": item.get_status_display(),
            "turma": item.registro.turma.nome,
            "autor": "",
            "referencia_id": item.registro_id,
            "_ordem": item.criado_em,
        }


def _rotulo_do_usuario(usuario) -> str:
    """Quem fez a mudança, ou vazio quando o histórico não registrou.

    Fica vazio no que foi criado fora de request (seed, management
    command, `populate_history --auto` do boot), onde o middleware do
    simple-history não tinha `request.user` pra capturar.
    """
    if usuario is None:
        return ""
    return usuario.get_full_name() or usuario.username


def _descrever_mudanca(
    campo: str, antes: Any, depois: Any, nomes_de_turma: dict[int, str]
) -> tuple[str, str] | None:
    """Título e detalhe de uma mudança de campo, ou None pra ignorar."""
    if campo == "ativo":
        if depois:
            return "Aluno reativado", ""
        return "Aluno inativado", ""
    if campo == "turma_id":
        de = nomes_de_turma.get(antes, "—")
        para = nomes_de_turma.get(depois, "—")
        return "Turma alterada", f"{de} → {para}"
    if campo == "matricula":
        return "Matrícula alterada", f"{antes} → {depois}"
    if campo == "nome_completo":
        return "Nome alterado", f"{antes} → {depois}"
    return None


def _eventos_de_cadastro(aluno: Aluno) -> list[dict[str, Any]]:
    """Eventos do histórico do simple-history, sem filtro de janela.

    Ver o docstring do módulo: a janela é aplicada depois, porque cada
    evento precisa da entrada anterior pra existir.
    """
    historico = list(
        aluno.history.select_related("history_user").order_by(
            "history_date", "history_id"
        )
    )
    if not historico:
        return []

    # Resolve nome de turma numa query só, e só quando alguma mudança de
    # turma existe — a grande maioria dos alunos nunca é remanejada.
    ids_de_turma = {
        registro.turma_id for registro in historico if registro.turma_id
    }
    nomes_de_turma: dict[int, str] = {}
    if len(ids_de_turma) > 1:
        nomes_de_turma = dict(
            Turma.objects.filter(pk__in=ids_de_turma).values_list("pk", "nome")
        )

    eventos: list[dict[str, Any]] = []

    def _novo(registro, titulo: str, detalhe: str) -> dict[str, Any]:
        return {
            "tipo": TIPO_CADASTRO,
            "data": registro.history_date.date().isoformat(),
            "titulo": titulo,
            "detalhe": detalhe,
            "status": None,
            "status_label": "",
            "turma": "",
            "autor": _rotulo_do_usuario(registro.history_user),
            "referencia_id": None,
            "_ordem": registro.history_date,
        }

    eventos.append(_novo(historico[0], "Aluno cadastrado", ""))

    for anterior, atual in zip(historico, historico[1:]):
        for campo in CAMPOS_CADASTRAIS:
            antes = getattr(anterior, campo)
            depois = getattr(atual, campo)
            if antes == depois:
                continue
            descricao = _descrever_mudanca(campo, antes, depois, nomes_de_turma)
            if descricao is None:
                continue
            titulo, detalhe = descricao
            eventos.append(_novo(atual, titulo, detalhe))

    return eventos


def montar_timeline(
    aluno: Aluno,
    data_inicio: date | None = None,
    data_fim: date | None = None,
    limite: int = LIMITE_EVENTOS,
) -> dict[str, Any]:
    """Eventos do aluno em ordem cronológica decrescente.

    Mais recente primeiro: a pergunta de quem abre a tela é "o que
    aconteceu agora", e o conselho de classe lê de trás pra frente.
    Empate de data é desempatado pelo instante de criação do registro,
    pra ordem não variar entre requisições.
    """
    eventos = [
        *_eventos_de_ocorrencias(aluno, data_inicio, data_fim),
        *_eventos_de_presenca(aluno, data_inicio, data_fim),
        *(
            evento
            for evento in _eventos_de_cadastro(aluno)
            if _no_intervalo(
                date.fromisoformat(evento["data"]), data_inicio, data_fim
            )
        ),
    ]
    eventos.sort(key=lambda evento: (evento["data"], evento["_ordem"]), reverse=True)

    total = len(eventos)
    truncado = total > limite
    for evento in eventos:
        del evento["_ordem"]

    return {
        "aluno": {
            "id": aluno.pk,
            "nome_completo": aluno.nome_completo,
            "matricula": aluno.matricula,
            "turma": aluno.turma.nome,
            "ativo": aluno.ativo,
        },
        "janela": {
            "data_inicio": data_inicio.isoformat() if data_inicio else None,
            "data_fim": data_fim.isoformat() if data_fim else None,
        },
        "total_eventos": total,
        "limite": limite,
        # O front avisa quando cortou: uma timeline silenciosamente
        # truncada faria a direção concluir que não houve mais nada.
        "truncado": truncado,
        "eventos": eventos[:limite],
    }
