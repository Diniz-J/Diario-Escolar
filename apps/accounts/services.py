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
    primeiro_nome = (usuario.first_name or usuario.username).strip()

    assunto = "Redefinir sua senha no Diário Diniz"
    corpo_texto = (
        f"Olá, {primeiro_nome}.\n\n"
        "Recebemos seu pedido de troca de senha. O link abaixo abre a "
        "página pra você definir uma nova — vale pela próxima hora.\n\n"
        f"{link}\n\n"
        "Se não foi você, é só ignorar. A senha atual continua valendo "
        "e o link expira sozinho.\n\n"
        "— Diário Diniz"
    )
    # HTML usa apenas tabelas + estilos inline — clientes de email
    # (Gmail, Outlook, Apple Mail) sao agressivos: removem `<style>`,
    # `<head>`, `class`, etc. Tabelas garantem layout consistente.
    corpo_html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<body style="margin:0;padding:0;background:#ebe2d1;font-family:Georgia,'Times New Roman',serif;color:#2d2a24;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background:#ebe2d1;padding:32px 16px;">
    <tr>
      <td align="center">
        <table role="presentation" width="560" cellpadding="0" cellspacing="0" border="0" style="max-width:560px;width:100%;background:#f5efe0;border-radius:12px;border:1px solid #d9cfb8;">
          <tr>
            <td style="padding:32px 32px 8px 32px;font-family:'Helvetica Neue',Arial,sans-serif;">
              <p style="margin:0 0 4px 0;font-size:11px;letter-spacing:0.25em;text-transform:uppercase;color:#4d5a2e;">
                <span style="display:inline-block;width:6px;height:6px;background:#b07d62;border-radius:50%;vertical-align:middle;margin-right:8px;"></span>diário diniz
              </p>
            </td>
          </tr>
          <tr>
            <td style="padding:8px 32px 0 32px;">
              <h1 style="margin:0;font-family:Georgia,'Times New Roman',serif;font-weight:500;font-size:26px;letter-spacing:-0.01em;line-height:1.2;color:#2d2a24;">
                Vamos trocar sua senha.
              </h1>
              <div style="height:1px;width:40px;background:#b07d62;margin:16px 0 24px 0;"></div>
            </td>
          </tr>
          <tr>
            <td style="padding:0 32px;font-family:'Helvetica Neue',Arial,sans-serif;font-size:15px;line-height:1.55;color:#2d2a24;">
              <p style="margin:0 0 16px 0;">Olá, {primeiro_nome}.</p>
              <p style="margin:0 0 24px 0;">
                Recebemos seu pedido de troca de senha. O botão abaixo abre
                a página pra você definir uma nova — vale pela próxima
                <strong>hora</strong>.
              </p>
            </td>
          </tr>
          <tr>
            <td align="center" style="padding:8px 32px 24px 32px;">
              <a href="{link}" style="display:inline-block;background:#4d5a2e;color:#ebe2d1;text-decoration:none;font-family:'Helvetica Neue',Arial,sans-serif;font-size:15px;font-weight:500;padding:14px 28px;border-radius:8px;">
                Redefinir minha senha
              </a>
            </td>
          </tr>
          <tr>
            <td style="padding:0 32px 16px 32px;font-family:'Helvetica Neue',Arial,sans-serif;font-size:12px;line-height:1.5;color:#6b6859;">
              <p style="margin:0 0 8px 0;">
                Se o botão não abrir, copie este endereço no navegador:
              </p>
              <p style="margin:0;word-break:break-all;">
                <a href="{link}" style="color:#b07d62;text-decoration:underline;">{link}</a>
              </p>
            </td>
          </tr>
          <tr>
            <td style="padding:16px 32px 32px 32px;">
              <div style="height:1px;width:40px;background:#b07d62;margin:0 0 16px 0;"></div>
              <p style="margin:0;font-family:'Helvetica Neue',Arial,sans-serif;font-size:12px;line-height:1.5;color:#6b6859;">
                Se não foi você, é só ignorar. A senha atual continua
                valendo e o link expira sozinho.
              </p>
            </td>
          </tr>
          <tr>
            <td style="padding:0 32px 24px 32px;font-family:'Helvetica Neue',Arial,sans-serif;font-size:10px;letter-spacing:0.18em;text-transform:uppercase;color:#6b6859;">
              diário diniz · v1.0
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""

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
