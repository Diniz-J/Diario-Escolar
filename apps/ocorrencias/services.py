"""Serviços da app ocorrencias — lógica que não pertence à view nem ao model.

Hoje: notificação por email ao responsável do aluno quando uma ocorrência
é registrada. O envio roda fora do caminho da request (thread daemon) pra
não pendurar a resposta HTTP enquanto o SMTP responde; é protegido — se o
email falhar, a ocorrência já foi salva e o erro é logado, não propagado.

Quem recebe vem de `apps.portal.destinatarios` — os vínculos
`ResponsavelAluno`, com fallback pro campo de texto do aluno quando não
há vínculo nenhum. Um aluno pode ter mais de um responsável (mãe e pai),
e nesse caso sai uma mensagem individual pra cada: endereço de um não
aparece pro outro. Ver `RESPONSAVEIS.md`.

O email é multipart (texto + HTML): clientes modernos veem o HTML com o
header de marca e o info box; clientes minimalistas (ou leitores
acessíveis) veem o fallback em texto puro.
"""
import logging
import threading

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string

from apps.common.logging import escola_context
from apps.portal.destinatarios import destinatarios_do_aluno

logger = logging.getLogger(__name__)


def _formatar_data_br(data) -> str:
    return data.strftime("%d/%m/%Y")


def _professor_nome(ocorrencia) -> str:
    if ocorrencia.professor and ocorrencia.professor.usuario:
        return ocorrencia.professor.usuario.get_full_name() or "—"
    return "—"


def montar_email_ocorrencia(
    ocorrencia, nome_responsavel: str = ""
) -> tuple[str, str, str]:
    """Monta (assunto, texto plano, HTML) do email de notificação.

    Plain text é fallback obrigatório: alguns clientes ignoram HTML por
    config de segurança/leitor de tela. O HTML é gerado via template
    Django pra deixar a marca/estrutura editáveis sem mexer no service.

    `nome_responsavel` é por destinatário — com mãe e pai vinculados, cada
    um é saudado pelo próprio nome. Vazio cai no nome do cadastro do aluno
    e, na falta dele, em "responsável".
    """
    aluno = ocorrencia.aluno
    turma = ocorrencia.turma
    assunto = f"[Diário Diniz] Ocorrência registrada — {aluno.nome_completo}"
    professor = _professor_nome(ocorrencia)
    data_br = _formatar_data_br(ocorrencia.data_ocorrencia)
    status_display = ocorrencia.get_status_display()
    saudacao = nome_responsavel or aluno.nome_responsavel or "responsável"

    texto = (
        f"Prezado(a) {saudacao},\n\n"
        f"Uma ocorrência foi registrada para o(a) aluno(a) "
        f"{aluno.nome_completo}.\n\n"
        f"Turma: {turma.nome}\n"
        f"Data: {data_br}\n"
        f"Status: {status_display}\n"
        f"Registrada por: {professor}\n\n"
        f"Descrição:\n{ocorrencia.descricao}\n\n"
        f"Esta é uma mensagem automática do Diário Diniz. "
        f"Em caso de dúvidas, procure a coordenação da escola.\n"
    )

    html = render_to_string(
        "ocorrencias/email_ocorrencia.html",
        {
            "ocorrencia": ocorrencia,
            "aluno": aluno,
            "turma": turma,
            "nome_responsavel": saudacao,
            "professor_nome": professor,
            "data_br": data_br,
            "status_display": status_display,
            "backend_url": settings.BACKEND_URL.rstrip("/"),
        },
    )
    return assunto, texto, html


def _enviar_mensagens(mensagens: list[tuple], ocorrencia_id, escola_id) -> None:
    """Faz o envio SMTP/API de fato. Roda na thread daemon (ou síncrono em testes).

    Recebe uma mensagem **por destinatário**, já montada: com mãe e pai
    vinculados saem dois emails individuais, nunca um com os dois no `to`
    — endereço de um responsável não é dado do outro (LGPD), e é o mesmo
    princípio que o comunicado já segue.

    Multipart: texto plano + alternativa HTML. NUNCA levanta exceção — o
    erro é logado com stack trace e o loop segue pro próximo destinatário,
    pra que o email inválido da mãe não impeça o do pai. Em produção isto
    roda fora da request, então não há ninguém pra propagar o erro de
    qualquer forma; a ocorrência já está persistida.

    Recebe `escola_id` explícito e o reinjeta no `escola_context`: a thread
    daemon não herda o ContextVar da request, então sem isto os logs de
    envio sairiam sem a escola carimbada.
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
                    "Ocorrência %s: falha ao enviar email para %s.",
                    ocorrencia_id,
                    email_destino,
                )
            else:
                logger.info(
                    "Ocorrência %s: email enviado para %s.",
                    ocorrencia_id,
                    email_destino,
                )
    finally:
        # Limpa o contexto: no caminho síncrono (testes) a thread é
        # reaproveitada, então o escola_id não pode vazar pro próximo log.
        escola_context.reset(ctx)


def notificar_responsavel_ocorrencia(ocorrencia) -> int:
    """Notifica os responsáveis do aluno por email ao registrar a ocorrência.

    Quem recebe vem de `apps.portal.destinatarios` — os vínculos, com
    fallback pro campo de texto do aluno quando não há vínculo nenhum. Um
    aluno com mãe e pai cadastrados gera duas mensagens individuais.

    O assunto/corpo são montados aqui (na request, onde as relations e a
    conexão de DB estão saudáveis); o envio SMTP é disparado numa thread
    daemon pra não pendurar a resposta HTTP enquanto o provedor responde.
    Em testes (`settings.TESTING`) o envio é síncrono pra manter o
    `mail.outbox` determinístico.

    Retorna quantas mensagens foram disparadas (0 = não havia para onde
    mandar). NUNCA levanta exceção — o chamador (perform_create) não deve
    ser interrompido por problema de email.
    """
    destinatarios = destinatarios_do_aluno(ocorrencia.aluno)
    if not destinatarios:
        logger.warning(
            "Ocorrência %s: aluno %s sem responsável com email — "
            "email não enviado.",
            ocorrencia.id,
            ocorrencia.aluno_id,
        )
        return 0

    mensagens = [
        (*montar_email_ocorrencia(ocorrencia, destinatario.nome), destinatario.email)
        for destinatario in destinatarios
    ]
    args = (mensagens, ocorrencia.id, ocorrencia.escola_id)

    if getattr(settings, "TESTING", False):
        # Síncrono em testes: o locmem backend é instantâneo e a asserção
        # sobre mail.outbox precisa ser determinística (sem corrida de thread).
        _enviar_mensagens(*args)
    else:
        # Fire-and-forget: o POST volta na hora; o email é melhor-esforço.
        threading.Thread(target=_enviar_mensagens, args=args, daemon=True).start()
    return len(mensagens)
