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

from django.conf import settings
from django.template.loader import render_to_string

from apps.notificacoes.models import Mensagem
from apps.notificacoes.services import enviar as enviar_notificacao
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



def notificar_responsavel_ocorrencia(ocorrencia) -> int:
    """Notifica os responsáveis do aluno por email ao registrar a ocorrência.

    Quem recebe vem de `apps.portal.destinatarios` — os vínculos, com
    fallback pro campo de texto do aluno quando não há vínculo nenhum. Um
    aluno com mãe e pai cadastrados gera duas mensagens individuais.

    O assunto/corpo são montados aqui (na request, onde as relations e a
    conexão de DB estão saudáveis) e entregues ao outbox
    (`apps/notificacoes`), que grava cada mensagem como pendente e só
    então despacha — em thread daemon, pra não pendurar a resposta HTTP,
    e síncrono em `settings.TESTING` pra manter o `mail.outbox`
    determinístico.

    Retorna quantas mensagens foram **registradas** (0 = não havia para
    onde mandar). O desfecho de cada envio fica na linha do outbox, que
    é onde a escola consulta se o responsável foi mesmo avisado. NUNCA levanta exceção — o chamador (perform_create) não deve
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
    # Passa pelo outbox (`apps/notificacoes`): a mensagem é gravada como
    # pendente ANTES da tentativa, então o envio que morrer junto com o
    # processo — deploy e restart são rotina no Render — deixa linha pro
    # command de retentativa achar. Antes disto, a falha sumia num log.
    return enviar_notificacao(
        mensagens,
        origem=Mensagem.Origem.OCORRENCIA,
        escola_id=ocorrencia.escola_id,
        referencia_id=ocorrencia.pk,
    )
