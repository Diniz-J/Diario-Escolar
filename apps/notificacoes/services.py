"""Gravação e despacho das mensagens do outbox.

O contrato com quem chama é de duas etapas, nesta ordem, e a ordem é a
razão de o módulo existir: **grava, depois tenta**. Se o processo morrer
no meio do envio — e no Render deploy e restart são rotina —, a linha
pendente sobrevive e o command de retentativa a encontra. Era isso que
faltava: a thread daemon morria junto com o processo e levava a
mensagem com ela, sem deixar sinal.
"""
from __future__ import annotations

import logging
import threading
from collections.abc import Sequence

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.db import transaction
from django.utils import timezone

from apps.common.logging import escola_context

from .models import Mensagem

logger = logging.getLogger(__name__)


def registrar(
    mensagens: Sequence[tuple[str, str, str, str]],
    *,
    origem: str,
    escola_id: int | None,
    referencia_id: int | None = None,
) -> list[Mensagem]:
    """Grava as mensagens como `pendente` e devolve as linhas criadas.

    Cada item é `(assunto, texto, html, destinatario)` — a mesma tupla
    que os caminhos de envio já montavam antes do outbox existir, pra
    que a adoção não os obrigasse a mudar como constroem o email.
    """
    return Mensagem.objects.bulk_create(
        [
            Mensagem(
                escola_id=escola_id,
                origem=origem,
                referencia_id=referencia_id,
                assunto=assunto,
                corpo_texto=texto,
                corpo_html=html,
                destinatario=destinatario,
            )
            for assunto, texto, html, destinatario in mensagens
        ]
    )


def despachar(
    ids: Sequence[int],
    escola_id: int | None = None,
    *,
    propagar: bool = False,
) -> int:
    """Envia as mensagens destes ids e carimba o resultado em cada linha.

    Recebe **ids**, não instâncias: roda na thread (ou no command de
    retentativa), e reler do banco garante que não se envie de novo o
    que outro processo já marcou como enviado no intervalo.

    Por padrão NUNCA levanta: falha de uma mensagem não cala as outras —
    o email inválido da mãe não pode impedir o do pai, que é a mesma
    regra que ocorrência e comunicado já seguiam.

    `propagar=True` é para o caminho all-or-nothing de **uma** mensagem,
    onde quem chama precisa desfazer algo (o `emitir_link` do portal
    apaga o convite). Aí a exceção **original do provedor** sobe, não uma
    genérica: é ela que diz se foi cota estourada ou endereço recusado, e
    é ela que o Sentry recebe. A linha do outbox já foi carimbada como
    `falhou` antes de subir.

    Recebe `escola_id` explícito e o reinjeta no contexto de log: a
    thread daemon não herda o ContextVar da request, então sem isto os
    logs de envio sairiam sem a escola carimbada.
    """
    ctx = escola_context.set(escola_id)
    enviadas = 0
    try:
        for mensagem in Mensagem.objects.filter(
            pk__in=list(ids)
        ).exclude(status=Mensagem.Status.ENVIADO):
            if _enviar_uma(mensagem, propagar=propagar):
                enviadas += 1
    finally:
        escola_context.reset(ctx)
    return enviadas


def _enviar_uma(mensagem: Mensagem, *, propagar: bool = False) -> bool:
    """Tenta uma mensagem e grava o desfecho. Devolve True se saiu."""
    mensagem.tentativas += 1
    try:
        email = EmailMultiAlternatives(
            subject=mensagem.assunto,
            body=mensagem.corpo_texto,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[mensagem.destinatario],
        )
        if mensagem.corpo_html:
            email.attach_alternative(mensagem.corpo_html, "text/html")
        email.send(fail_silently=False)
    except Exception as exc:
        mensagem.status = Mensagem.Status.FALHOU
        # `str(exc)` e não o traceback: a coluna é lida na tela e no
        # admin. O stack trace completo vai pro log/Sentry logo abaixo.
        mensagem.erro = str(exc)[:1000]
        mensagem.save(
            update_fields=["status", "erro", "tentativas", "atualizado_em"]
        )
        logger.exception(
            "Mensagem %s (%s): falha ao enviar para %s.",
            mensagem.pk,
            mensagem.origem,
            mensagem.destinatario,
        )
        if propagar:
            raise
        return False

    mensagem.status = Mensagem.Status.ENVIADO
    mensagem.erro = ""
    mensagem.enviado_em = timezone.now()
    mensagem.save(
        update_fields=[
            "status",
            "erro",
            "tentativas",
            "enviado_em",
            "atualizado_em",
        ]
    )
    logger.info(
        "Mensagem %s (%s): enviada para %s.",
        mensagem.pk,
        mensagem.origem,
        mensagem.destinatario,
    )
    return True


def enviar(
    mensagens: Sequence[tuple[str, str, str, str]],
    *,
    origem: str,
    escola_id: int | None,
    referencia_id: int | None = None,
) -> int:
    """Grava e dispara. É esta a função que os caminhos de envio chamam.

    O despacho sai da request por thread daemon, como antes — o POST não
    pode esperar o provedor. A diferença é que agora a thread lê do
    banco, e por isso o `transaction.on_commit` deixou de ser precaução e
    virou obrigatório: disparada antes do commit, ela não encontraria as
    linhas que esta request acabou de gravar. É a mesma razão registrada
    em `comunicados/services.py`; aqui ela vale pros quatro caminhos.

    Em `TESTING` roda síncrono, pra `mail.outbox` continuar
    determinístico — sem corrida de thread na asserção.

    Devolve quantas mensagens foram **registradas** (não quantas saíram):
    quem chama precisa saber que havia destino, e o desfecho do envio é
    assunto da linha do outbox, não do retorno.
    """
    if not mensagens:
        return 0

    linhas = registrar(
        mensagens,
        origem=origem,
        escola_id=escola_id,
        referencia_id=referencia_id,
    )
    ids = [linha.pk for linha in linhas]

    if getattr(settings, "TESTING", False):
        despachar(ids, escola_id)
    else:
        transaction.on_commit(
            lambda: threading.Thread(
                target=despachar, args=(ids, escola_id), daemon=True
            ).start()
        )
    return len(ids)
