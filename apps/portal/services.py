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
from datetime import timedelta

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.db import transaction
from django.template.loader import render_to_string
from django.utils import timezone

from .models import ConviteResponsavel, Responsavel

logger = logging.getLogger(__name__)

Finalidade = ConviteResponsavel.Finalidade

# Janela em que um pedido novo de "esqueci a senha" não gera outro email.
INTERVALO_MINIMO_REDEFINICAO = timedelta(minutes=15)

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

    Falha de envio não deixa rastro no estado da conta:

    - O link novo é **apagado** (não só expirado). Uma linha expirada que
      nunca saiu fazia a tela de responsáveis mostrar "convite expirado"
      pra quem nunca recebeu convite, e o comando de lote a contaria como
      tentativa. O erro em si fica no log (Sentry), via quem chamou.
    - Os links pendentes anteriores só são invalidados **depois** que o
      email sai. Um reenvio que falha mantém o convite anterior valendo.
    """
    convite, token_cru = ConviteResponsavel.gerar(
        responsavel, finalidade, enviado_por=enviado_por
    )
    try:
        montar_email(responsavel, finalidade, token_cru).send(fail_silently=False)
    except Exception:
        convite.delete()
        raise
    ConviteResponsavel.pendentes(responsavel).exclude(pk=convite.pk).update(
        expira_em=timezone.now()
    )
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
    recente = timezone.now() - INTERVALO_MINIMO_REDEFINICAO
    for responsavel in Responsavel.objects.select_related("escola").filter(pk__in=ids):
        # Já tem link de redefinição pendente e recente: não manda outro.
        # Sem isso o "esqueci" só tinha limite por IP — dava pra disparar
        # milhares de emails pro mesmo pai, queimando a cota compartilhada
        # com comunicados e ocorrências, e cada pedido matava o link
        # anterior. O pai usa o que já chegou.
        if ConviteResponsavel.pendentes(responsavel).filter(
            finalidade=Finalidade.REDEFINICAO, criado_em__gte=recente
        ).exists():
            continue
        try:
            emitir_link(responsavel, Finalidade.REDEFINICAO)
        except Exception:  # noqa: BLE001 — vira evento no Sentry
            logger.exception(
                "Falha ao enviar link de redefinição do portal",
                extra={"responsavel_id": responsavel.pk},
            )


def definir_senha(convite: ConviteResponsavel, senha: str) -> bool:
    """Grava a senha e consome o link — atômico. False se o link já foi usado.

    O consumo é um `UPDATE` condicional com rowcount checado, não
    ler-e-gravar: duas requisições simultâneas com o mesmo token passariam
    as duas pela checagem de `buscar_valido` e gravariam senha duas vezes.
    Só uma ganha o UPDATE; a outra recebe False. Mesmo padrão do envio
    dos comunicados.

    Trocar a senha muda a impressão gravada nos tokens (`tokens.py`), então
    toda sessão aberta antes cai no próximo request.
    """
    agora = timezone.now()
    with transaction.atomic():
        consumido = ConviteResponsavel.objects.filter(
            pk=convite.pk, usado_em__isnull=True, expira_em__gt=agora
        ).update(usado_em=agora, atualizado_em=agora)
        if not consumido:
            return False
        responsavel = convite.responsavel
        responsavel.set_password(senha)
        responsavel.save(update_fields=["password", "atualizado_em"])
        # Qualquer outro link pendente (ex.: convite + redefinição) morre.
        ConviteResponsavel.pendentes(responsavel).update(expira_em=agora)
    return True
