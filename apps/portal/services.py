"""Serviços do portal — emissão de link de senha e definição de senha.

Link de convite e de redefinição seguem o mesmo fluxo: gera o
`ConviteResponsavel`, manda o email com o link e, quando o responsável
abre, `definir_senha` grava a senha e consome o link.

Atenção à cota: o Brevo free entrega 300 emails/dia, **compartilhados com
os comunicados e as ocorrências**. Por isso o convite é individual na UI e
o onboarding em massa passa pelo comando `portal_convidar_responsaveis`,
que tem limite por execução (`PORTAL.md`, seção 2).
"""
import logging
import threading

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.db import transaction
from django.template.loader import render_to_string
from django.utils import timezone

from .models import ConviteResponsavel

logger = logging.getLogger(__name__)

Finalidade = ConviteResponsavel.Finalidade

_TEXTOS = {
    Finalidade.CONVITE: {
        "assunto": "Seu acesso ao portal do responsável — {escola}",
        "titulo": "Acompanhe a vida escolar pelo portal.",
        "texto": (
            "A {escola} criou seu acesso ao portal do responsável, onde você "
            "acompanha comunicados, boletim e ocorrências. O botão abaixo "
            "abre a página pra você definir sua senha — vale por 7 dias."
        ),
        "botao": "Definir minha senha",
        "rodape": (
            "Se você não é responsável por um aluno desta escola, ignore este "
            "email. Nenhuma conta é ativada sem a senha."
        ),
    },
    Finalidade.REDEFINICAO: {
        "assunto": "Redefinir sua senha do portal — {escola}",
        "titulo": "Vamos trocar sua senha.",
        "texto": (
            "Recebemos um pedido de troca da sua senha do portal do "
            "responsável. O botão abaixo abre a página pra você definir uma "
            "nova — vale pela próxima hora."
        ),
        "botao": "Redefinir minha senha",
        "rodape": (
            "Se não foi você, é só ignorar. A senha atual continua valendo e "
            "o link expira sozinho."
        ),
    },
}


def montar_email(responsavel, finalidade, token_cru: str) -> EmailMultiAlternatives:
    base = settings.FRONTEND_URL.rstrip("/")
    link = f"{base}/portal/definir-senha?token={token_cru}"
    escola = responsavel.escola.nome
    textos = {k: v.format(escola=escola) for k, v in _TEXTOS[finalidade].items()}
    contexto = {**textos, "escola": escola, "nome": responsavel.nome, "link": link}

    corpo_texto = (
        f"Olá, {responsavel.nome}.\n\n{textos['texto']}\n\n{link}\n\n"
        f"{textos['rodape']}\n\n— {escola}"
    )
    msg = EmailMultiAlternatives(
        subject=textos["assunto"],
        body=corpo_texto,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[responsavel.email],
    )
    msg.attach_alternative(
        render_to_string("portal/email_link.html", contexto), "text/html"
    )
    return msg


def emitir_link(responsavel, finalidade, enviado_por=None) -> ConviteResponsavel:
    """Gera o link e envia o email, **síncrono**. Levanta se o envio falhar.

    Se o email não sair, o link é invalidado antes de propagar o erro.
    Sem isso, o comando de lote veria um convite "pendente" e nunca mais
    tentaria aquele responsável — o pai ficaria sem convite pra sempre.
    """
    convite, token_cru = ConviteResponsavel.gerar(
        responsavel, finalidade, enviado_por=enviado_por
    )
    try:
        montar_email(responsavel, finalidade, token_cru).send(fail_silently=False)
    except Exception:
        convite.invalidar()
        raise
    return convite


def solicitar_redefinicao(responsaveis) -> None:
    """Dispara o link de redefinição pro "esqueci a senha".

    Fora da request (thread daemon), como o email de ocorrência: enviar
    síncrono deixaria a resposta mais lenta quando o email tem conta, e a
    diferença de tempo diria a um atacante quais emails são de
    responsáveis. Em testes é síncrono, pro `mail.outbox` ser determinístico.
    Falha vira log (Sentry) e nunca chega na resposta.
    """
    ids = [r.pk for r in responsaveis]
    if not ids:
        return
    if getattr(settings, "TESTING", False):
        _enviar_redefinicoes(ids)
    else:
        threading.Thread(
            target=_enviar_redefinicoes, args=(ids,), daemon=True
        ).start()


def _enviar_redefinicoes(ids: list[int]) -> None:
    from .models import Responsavel

    for responsavel in Responsavel.objects.select_related("escola").filter(pk__in=ids):
        try:
            emitir_link(responsavel, Finalidade.REDEFINICAO)
        except Exception:  # noqa: BLE001 — vira evento no Sentry
            logger.exception(
                "Falha ao enviar link de redefinição do portal",
                extra={"responsavel_id": responsavel.pk},
            )


def definir_senha(convite: ConviteResponsavel, senha: str) -> None:
    """Grava a senha e consome o link — atômico.

    Trocar a senha muda a impressão gravada nos tokens (`tokens.py`), então
    toda sessão aberta antes cai no próximo request.
    """
    with transaction.atomic():
        responsavel = convite.responsavel
        responsavel.set_password(senha)
        responsavel.save(update_fields=["password", "atualizado_em"])
        convite.usado_em = timezone.now()
        convite.save(update_fields=["usado_em", "atualizado_em"])
        # Qualquer outro link pendente (ex.: convite + redefinição) morre.
        ConviteResponsavel.pendentes(responsavel).update(expira_em=timezone.now())
