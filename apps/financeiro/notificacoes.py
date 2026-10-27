"""Notificação ao responsável quando um pagamento é conciliado.

Módulo separado do `services.py` de propósito: lá mora o que **escreve
dinheiro** (geração, conciliação, vencimento), e misturar email ali
confundiria as duas responsabilidades — a primeira não pode falhar em
silêncio, a segunda é melhor-esforço por definição.

Quem recebe vem de `apps.portal.destinatarios`, como ocorrência e
comunicado: os vínculos `ResponsavelAluno`, com fallback pro campo de
texto do aluno só quando não há vínculo nenhum. O pai cadastrado apenas
pelo M2M tem que receber — é a armadilha central do `RESPONSAVEIS.md`
§4.1. Com mãe e pai vinculados saem duas mensagens individuais, cada uma
saudada pelo próprio nome e com o endereço do outro fora do `to`.

O envio roda fora da request (thread daemon), como na ocorrência: a
conciliação chega por webhook, e o Asaas pausa a fila depois de 15 falhas
consecutivas de entrega — pendurar a resposta dele esperando o provedor
de email é como se chega lá.
"""
import logging
import threading

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string

from apps.common.logging import escola_context
from apps.portal.destinatarios import destinatarios_do_aluno

logger = logging.getLogger(__name__)


def _formatar_brl(valor) -> str:
    """Formata dinheiro no padrão brasileiro.

    À mão porque o projeto não tem locale pt-BR configurado e `floatformat`
    usaria o separador errado — o email vai pro responsável, onde "1.000,00"
    e "1,000.00" significam coisas diferentes.
    """
    inteiro, _, centavos = f"{valor:.2f}".partition(".")
    milhares = f"{int(inteiro):,}".replace(",", ".")
    return f"R$ {milhares},{centavos}"


def montar_email_pagamento(
    fatura, pagamento, nome_responsavel: str = ""
) -> tuple[str, str, str]:
    """Monta (assunto, texto plano, HTML) do aviso de pagamento recebido.

    Texto plano é fallback obrigatório, como nos outros emails do projeto:
    cliente com HTML desligado ou leitor de tela recebe o corpo legível.
    """
    aluno = fatura.aluno
    competencia = f"{fatura.competencia:%m/%Y}"
    valor = _formatar_brl(pagamento.valor)
    data_br = f"{pagamento.data:%d/%m/%Y}"
    saudacao = nome_responsavel or aluno.nome_responsavel or "responsável"

    assunto = f"[Diário Diniz] Pagamento recebido — mensalidade {competencia}"
    texto = (
        f"Prezado(a) {saudacao},\n\n"
        f"Confirmamos o recebimento do pagamento da mensalidade de "
        f"{competencia} do(a) aluno(a) {aluno.nome_completo}.\n\n"
        f"Valor recebido: {valor}\n"
        f"Data do pagamento: {data_br}\n"
        f"Situação da fatura: {fatura.get_status_display()}\n\n"
        f"Esta é uma mensagem automática do Diário Diniz. "
        f"Em caso de dúvidas, procure a secretaria da escola.\n"
    )
    html = render_to_string(
        "financeiro/email_pagamento.html",
        {
            "fatura": fatura,
            "aluno": aluno,
            "nome_responsavel": saudacao,
            "competencia": competencia,
            "valor": valor,
            "data_br": data_br,
            "status_display": fatura.get_status_display(),
            "backend_url": settings.BACKEND_URL.rstrip("/"),
        },
    )
    return assunto, texto, html


def _enviar_mensagens(mensagens: list[tuple], fatura_id, escola_id) -> None:
    """Envia de fato. Roda na thread daemon (ou síncrono em testes).

    NUNCA levanta exceção: o pagamento já está registrado e a fatura já
    está quitada quando isto roda. O erro é logado com stack trace (e vai
    pro Sentry pelo `LoggingIntegration`) e o loop segue pro próximo
    destinatário, pra que o endereço inválido da mãe não impeça o do pai.

    `escola_id` explícito porque a thread não herda o ContextVar da
    request — sem reinjetar, o log de envio sairia sem a escola carimbada.
    """
    ctx = escola_context.set(escola_id)
    try:
        for assunto, texto, html, email_destino in mensagens:
            try:
                msg = EmailMultiAlternatives(
                    subject=assunto,
                    body=texto,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    to=[email_destino],
                )
                msg.attach_alternative(html, "text/html")
                msg.send(fail_silently=False)
            except Exception:
                logger.exception(
                    "Fatura %s: falha ao enviar aviso de pagamento para %s.",
                    fatura_id,
                    email_destino,
                )
            else:
                logger.info(
                    "Fatura %s: aviso de pagamento enviado para %s.",
                    fatura_id,
                    email_destino,
                )
    finally:
        escola_context.reset(ctx)


def notificar_pagamento(fatura, pagamento) -> int:
    """Avisa os responsáveis do aluno que o pagamento foi recebido.

    Devolve quantas mensagens foram disparadas (0 = não havia para onde
    mandar). NUNCA levanta exceção — quem chama é a conciliação, e dinheiro
    conciliado não pode ser desfeito por falha de email.
    """
    destinatarios = destinatarios_do_aluno(fatura.aluno)
    if not destinatarios:
        logger.warning(
            "Fatura %s: aluno %s sem responsável com email — aviso de "
            "pagamento não enviado.",
            fatura.pk,
            fatura.aluno_id,
        )
        return 0

    mensagens = [
        (
            *montar_email_pagamento(fatura, pagamento, destinatario.nome),
            destinatario.email,
        )
        for destinatario in destinatarios
    ]
    args = (mensagens, fatura.pk, fatura.escola_id)

    if getattr(settings, "TESTING", False):
        # Síncrono em testes pra manter `mail.outbox` determinístico.
        _enviar_mensagens(*args)
    else:
        threading.Thread(target=_enviar_mensagens, args=args, daemon=True).start()
    return len(mensagens)
