"""Serviços da app ocorrencias — lógica que não pertence à view nem ao model.

Hoje: notificação por email ao responsável do aluno quando uma ocorrência
é registrada. Envio síncrono e protegido — se o email falhar, a ocorrência
já foi salva e o erro é logado, não propagado (não trava o cadastro).
"""
import logging

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


def notificar_responsavel_ocorrencia(ocorrencia) -> bool:
    """Envia o email da ocorrência ao responsável do aluno.

    Retorna True se o email foi disparado, False se foi pulado (aluno sem
    email de responsável) ou se houve falha. NUNCA levanta exceção — o
    chamador (perform_create) não deve ser interrompido por problema de
    email; a ocorrência já está persistida.
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
    try:
        send_mail(
            subject=assunto,
            message=corpo,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email_destino],
            fail_silently=False,
        )
        logger.info(
            "Ocorrência %s: email enviado para %s.", ocorrencia.id, email_destino
        )
        return True
    except Exception:
        # Log com stack trace, mas não propaga — a ocorrência já foi salva.
        logger.exception(
            "Ocorrência %s: falha ao enviar email para %s.",
            ocorrencia.id,
            email_destino,
        )
        return False
