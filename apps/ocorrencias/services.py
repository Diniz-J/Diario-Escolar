"""Serviços da app ocorrencias — lógica que não pertence à view nem ao model.

Hoje: notificação por email ao responsável do aluno quando uma ocorrência
é registrada. O envio roda fora do caminho da request (thread daemon) pra
não pendurar a resposta HTTP enquanto o SMTP responde; é protegido — se o
email falhar, a ocorrência já foi salva e o erro é logado, não propagado.
"""
import logging
import threading

from django.conf import settings
from django.core.mail import send_mail

logger = logging.getLogger(__name__)


def _formatar_data_br(data) -> str:
    return data.strftime("%d/%m/%Y")


def montar_email_ocorrencia(ocorrencia) -> tuple[str, str]:
    """Monta (assunto, corpo) do email de notificação da ocorrência."""
    aluno = ocorrencia.aluno
    turma = ocorrencia.turma
    assunto = f"[Diário Escolar] Ocorrência registrada — {aluno.nome_completo}"
    professor = (
        ocorrencia.professor.usuario.get_full_name()
        if ocorrencia.professor and ocorrencia.professor.usuario
        else "—"
    )
    corpo = (
        f"Prezado(a) {aluno.nome_responsavel or 'responsável'},\n\n"
        f"Uma ocorrência foi registrada para o(a) aluno(a) "
        f"{aluno.nome_completo}.\n\n"
        f"Turma: {turma.nome}\n"
        f"Data: {_formatar_data_br(ocorrencia.data_ocorrencia)}\n"
        f"Status: {ocorrencia.get_status_display()}\n"
        f"Registrada por: {professor}\n\n"
        f"Descrição:\n{ocorrencia.descricao}\n\n"
        f"Esta é uma mensagem automática do Diário Escolar. "
        f"Em caso de dúvidas, procure a coordenação da escola.\n"
    )
    return assunto, corpo


def _enviar_email(assunto: str, corpo: str, email_destino: str, ocorrencia_id) -> None:
    """Faz o envio SMTP de fato. Roda na thread daemon (ou síncrono em testes).

    NUNCA levanta exceção — o erro é logado com stack trace. Em produção isto
    roda fora da request, então não há ninguém pra propagar o erro de qualquer
    forma; a ocorrência já está persistida.
    """
    try:
        send_mail(
            subject=assunto,
            message=corpo,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email_destino],
            fail_silently=False,
        )
        logger.info(
            "Ocorrência %s: email enviado para %s.", ocorrencia_id, email_destino
        )
    except Exception:
        logger.exception(
            "Ocorrência %s: falha ao enviar email para %s.",
            ocorrencia_id,
            email_destino,
        )


def notificar_responsavel_ocorrencia(ocorrencia) -> bool:
    """Notifica o responsável do aluno por email ao registrar a ocorrência.

    O assunto/corpo são montados aqui (na request, onde as relations e a
    conexão de DB estão saudáveis); o envio SMTP é disparado numa thread
    daemon pra não pendurar a resposta HTTP enquanto o provedor responde.
    Em testes (`settings.TESTING`) o envio é síncrono pra manter o
    `mail.outbox` determinístico.

    Retorna True se o envio foi disparado, False se foi pulado (aluno sem
    email de responsável). NUNCA levanta exceção — o chamador
    (perform_create) não deve ser interrompido por problema de email.
    """
    email_destino = ocorrencia.aluno.email_responsavel
    if not email_destino:
        logger.warning(
            "Ocorrência %s: aluno %s sem email de responsável — email não enviado.",
            ocorrencia.id,
            ocorrencia.aluno_id,
        )
        return False

    assunto, corpo = montar_email_ocorrencia(ocorrencia)
    args = (assunto, corpo, email_destino, ocorrencia.id)

    if getattr(settings, "TESTING", False):
        # Síncrono em testes: o locmem backend é instantâneo e a asserção
        # sobre mail.outbox precisa ser determinística (sem corrida de thread).
        _enviar_email(*args)
    else:
        # Fire-and-forget: o POST volta na hora; o email é melhor-esforço.
        threading.Thread(target=_enviar_email, args=args, daemon=True).start()
    return True
