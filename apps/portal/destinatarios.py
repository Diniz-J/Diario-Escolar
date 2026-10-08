"""Origem única de "para quem vai o email do responsável".

Antes deste módulo o sistema tinha duas noções de responsável que não
conversavam: os emails (ocorrência e comunicado) saíam pelo campo de texto
`Aluno.email_responsavel`, e o portal lia os vínculos `ResponsavelAluno`.
O efeito era o pai cadastrado só pelo vínculo **ver** os dados no portal e
nunca **receber** email. Ver `RESPONSAVEIS.md` na raiz do repo.

Mora em `apps.portal` porque é onde o vínculo mora. As apps que enviam
(`ocorrencias`, `comunicados`) chamam daqui em vez de ler o aluno.

A regra que parece óbvia e não é (`RESPONSAVEIS.md`, §4.1): **o fallback
pro campo de texto dispara por ausência de vínculo, nunca por ausência de
destino elegível.**

- Aluno com zero vínculos → usa `Aluno.email_responsavel`. É a escola que
  nunca rodou a semeadura; sem o fallback ela pararia de receber email em
  silêncio.
- Aluno com vínculos, mas nenhum elegível (conta inativa ou com
  `recebe_notificacao=False`) → zero destinos, **sem** fallback. Cair no
  campo do aluno aqui reenviaria pro mesmo endereço que acabou de pedir
  silêncio, transformando o opt-out em nada.
"""
from collections.abc import Iterable
from dataclasses import dataclass

from apps.common.texto import normalizar_email

from .models import ResponsavelAluno


@dataclass(frozen=True)
class Destinatario:
    """Um endereço que deve receber a mensagem, com a quem ele pertence.

    `responsavel_id` é `None` quando o destino veio do campo de texto do
    aluno (fallback). O log de entrega do comunicado usa isso pra dizer de
    quem foi a entrega quando há vínculo, e pra manter legível a linha que
    nasceu sem ele.
    """

    email: str
    nome: str
    responsavel_id: int | None


def _do_campo_do_aluno(aluno) -> list[Destinatario]:
    """Fallback: o par `nome_responsavel`/`email_responsavel` do aluno."""
    email = normalizar_email(aluno.email_responsavel)
    if not email:
        return []
    return [
        Destinatario(
            email=email,
            nome=aluno.nome_responsavel or "",
            responsavel_id=None,
        )
    ]


def destinatarios_por_aluno(
    alunos: Iterable,
) -> dict[int, list[Destinatario]]:
    """Resolve os destinatários de vários alunos numa consulta só.

    Usado pelo comunicado, que alcança a escola inteira — uma consulta por
    aluno viraria N+1 com N na casa das centenas. Recebe instâncias de
    `Aluno` (precisa dos campos de fallback) e devolve um dicionário por
    `aluno_id`, sempre com uma entrada por aluno recebido (lista vazia
    quando não há para onde mandar).
    """
    alunos = list(alunos)
    if not alunos:
        return {}

    ids = [aluno.id for aluno in alunos]
    # Uma consulta para o lote inteiro, trazendo também os vínculos cujo
    # responsável não é elegível: é o que distingue "não há cadastro" de
    # "o cadastro diz não" (§4.1). Partição em memória, não no SQL.
    # `order_by("responsavel_id")` em vez do ordering do Meta
    # (`aluno__nome_completo`), que forçaria um JOIN em `escola_aluno` só
    # para ordenar por um campo que não serve aqui. Ordem fixa mantém
    # determinística a sequência de envio e dos logs.
    linhas = ResponsavelAluno.objects.filter(
        aluno_id__in=ids
    ).order_by("responsavel_id").values_list(
        "aluno_id",
        "responsavel_id",
        "responsavel__email",
        "responsavel__nome",
        "responsavel__ativo",
        "responsavel__recebe_notificacao",
    )

    com_vinculo: set[int] = set()
    por_aluno: dict[int, list[Destinatario]] = {}
    vistos: dict[int, set[str]] = {}
    for (
        aluno_id,
        responsavel_id,
        email,
        nome,
        ativo,
        recebe_notificacao,
    ) in linhas:
        com_vinculo.add(aluno_id)
        if not (ativo and recebe_notificacao):
            continue
        email = normalizar_email(email)
        if not email:
            continue
        # Dedup por endereço dentro do aluno. É inalcançável pelo
        # caminho normal — o unique por `(escola, email)` do `Responsavel`
        # recusa a segunda conta e todo vínculo é intra-escola — e fica
        # como rede: `ResponsavelAluno.objects.create()` não passa por
        # `clean()`, então um vínculo cruzando escola feito por shell
        # traria um endereço repetido pra cá, e email de ocorrência em
        # dobro não tem desfazer.
        if email in vistos.setdefault(aluno_id, set()):
            continue
        vistos[aluno_id].add(email)
        por_aluno.setdefault(aluno_id, []).append(
            Destinatario(
                email=email, nome=nome or "", responsavel_id=responsavel_id
            )
        )

    resultado: dict[int, list[Destinatario]] = {}
    for aluno in alunos:
        if aluno.id in com_vinculo:
            resultado[aluno.id] = por_aluno.get(aluno.id, [])
        else:
            resultado[aluno.id] = _do_campo_do_aluno(aluno)
    return resultado


def destinatarios_do_aluno(aluno) -> list[Destinatario]:
    """Resolve os destinatários de um aluno só (ocorrência).

    Delega no lote pra que exista uma única implementação da regra de
    fallback — duas cópias divergiriam, e a divergência aqui significa
    email indevido ou silêncio.
    """
    return destinatarios_por_aluno([aluno])[aluno.id]
