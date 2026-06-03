"""Serviços da app accounts — envio de email de redefinição de senha."""
import logging

from django.conf import settings
from django.core.mail import EmailMultiAlternatives

from .models import Usuario

logger = logging.getLogger(__name__)


def enviar_link_redefinicao(usuario: Usuario, token_cru: str) -> None:
    """Envia o link de redefinição pro email cadastrado do usuário.

    Roda **síncrono**. No fluxo de "esqueci a senha" o usuário fica numa
    tela "enviamos um email pra você" enquanto isso — diferente do email
    de ocorrência (que tem que voltar 201 rápido). Aqui é aceitável dar
    o feedback só depois do SMTP responder.

    Falhas viram `logger.exception` (capturado pelo Sentry via
    `LoggingIntegration`); a view chamadora sempre devolve 200 pra UI pra
    não vazar se o email existe ou não (anti-enumeração).
    """
    base = settings.FRONTEND_URL.rstrip("/")
    link = f"{base}/redefinir-senha?token={token_cru}"
    nome = usuario.get_full_name() or usuario.username

    assunto = "Redefinição de senha — Diário Diniz"
    corpo_texto = (
        f"Olá, {nome}.\n\n"
        "Recebemos uma solicitação para redefinir a senha do seu acesso "
        "ao Diário Diniz. Para escolher uma nova senha, acesse o link "
        "abaixo (válido por 1 hora):\n\n"
        f"{link}\n\n"
        "Se você não fez essa solicitação, pode ignorar este email — "
        "sua senha atual segue valendo.\n\n"
        "— Diário Diniz"
    )
    corpo_html = (
        f"<p>Olá, <strong>{nome}</strong>.</p>"
        "<p>Recebemos uma solicitação para redefinir a senha do seu "
        "acesso ao Diário Diniz. Para escolher uma nova senha, clique "
        "no link abaixo (válido por 1 hora):</p>"
        f'<p><a href="{link}">Redefinir minha senha</a></p>'
        "<p>Se você não fez essa solicitação, pode ignorar este email — "
        "sua senha atual segue valendo.</p>"
        "<p>— Diário Diniz</p>"
    )

    msg = EmailMultiAlternatives(
        subject=assunto,
        body=corpo_texto,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[usuario.email],
    )
    msg.attach_alternative(corpo_html, "text/html")

    try:
        msg.send(fail_silently=False)
    except Exception:  # noqa: BLE001 — vira evento no Sentry
        logger.exception(
            "Falha ao enviar email de redefinição de senha",
            extra={"usuario_id": usuario.id},
        )
        # Não relança — a view chamadora SEMPRE devolve 200 (anti-enumeração).
        # O Sentry captura o erro pra investigação posterior.
