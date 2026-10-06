"""Serviços da app comunicados — resolução de público e disparo dos emails.

Diferença essencial em relação ao email de ocorrência (um destinatário,
best-effort): aqui um clique pode gerar centenas de emails. Isso traz
quatro problemas que este módulo resolve explicitamente:

1. **Privacidade (LGPD).** Cada responsável recebe uma mensagem
   individual. Jogar todos num To/CC vazaria a lista de emails de todos
   os pais da escola pra todos os pais da escola.
2. **Deduplicação.** Irmãos matriculados na mesma escola compartilham o
   email do responsável — sem dedup, o pai de dois filhos receberia o
   mesmo aviso duas vezes.
3. **Conexão.** Abrir uma conexão por mensagem multiplicaria o handshake
   por N. Usamos uma única conexão (`get_connection`) pro lote inteiro.
4. **Rastreio.** Cada destinatário tem sua linha com o resultado, então
   uma falha parcial (cota do provedor estourada no meio do lote) fica
   visível em vez de virar um "enviado" mentiroso.

O disparo roda numa thread daemon pra não pendurar a resposta HTTP — o
mesmo padrão de `apps.ocorrencias.services`, só que aqui a duração é
proporcional ao tamanho da escola. Em testes (`settings.TESTING`) roda
síncrono pra manter `mail.outbox` determinístico.
"""
import logging
import threading

from django.conf import settings
from django.core.mail import EmailMultiAlternatives, get_connection
from django.db import transaction
from django.template.loader import render_to_string
from django.utils import timezone

from apps.common.logging import escola_context
from apps.escola.models import Aluno

from .models import Comunicado, ComunicadoDestinatario

logger = logging.getLogger(__name__)


def _normalizar_email(valor: str | None) -> str:
    """Normaliza pra comparação de duplicados.

    Lowercase + strip: `Maria@Example.com ` e `maria@example.com` são o
    mesmo endereço e não devem render dois emails pro mesmo responsável.
    """
    return (valor or "").strip().lower()


def resolver_alunos(comunicado: Comunicado):
    """Queryset dos alunos cujo responsável deve receber o comunicado.

    Sempre só alunos **ativos**: aluno transferido/desmatriculado não
    recebe aviso da escola.

    - `destino="escola"` → todos os ativos da escola.
    - `destino="turmas"` → ativos das turmas selecionadas.

    O filtro por `escola_id` é redundante no caso das turmas (o serializer
    já garante que as turmas são da escola), e é mantido de propósito como
    rede de segurança contra vazamento entre escolas.
    """
    qs = Aluno.objects.filter(escola_id=comunicado.escola_id, ativo=True)
    if comunicado.destino == Comunicado.Destino.TURMAS:
        qs = qs.filter(turma__in=comunicado.turmas.all())
    return qs.order_by("nome_completo")


def contar_previa(comunicado: Comunicado) -> dict[str, int]:
    """Conta o alcance do comunicado SEM enviar nada.

    Alimenta o diálogo de confirmação ("este comunicado vai para 142
    responsáveis") e o aviso de cadastro incompleto ("3 alunos sem email").
    `total_emails` é a contagem depois da dedup — é o número de mensagens
    que o provedor vai realmente receber, o que importa pra cota diária.
    """
    valores = resolver_alunos(comunicado).values_list(
        "email_responsavel", flat=True
    )
    emails: set[str] = set()
    total_alunos = 0
    total_sem_email = 0
    for email_responsavel in valores:
        total_alunos += 1
        email = _normalizar_email(email_responsavel)
        if email:
            emails.add(email)
        else:
            total_sem_email += 1
    return {
        "total_alunos": total_alunos,
        "total_emails": len(emails),
        "total_sem_email": total_sem_email,
    }


def montar_email_comunicado(comunicado: Comunicado, nome_responsavel: str):
    """Monta (assunto, texto plano, HTML) do comunicado.

    O plain text é fallback obrigatório (clientes que ignoram HTML por
    configuração de segurança ou leitor de tela). O HTML vem de template
    pra manter marca/estrutura editáveis sem mexer no service.

    `nome_responsavel` é por destinatário — o resto do conteúdo é igual
    pro lote todo, então o chamador monta uma vez por grupo, não por
    aluno.
    """
    assunto = f"[Diário Diniz] {comunicado.titulo}"
    saudacao = nome_responsavel or "responsável"

    texto = (
        f"Prezado(a) {saudacao},\n\n"
        f"{comunicado.titulo}\n\n"
        f"{comunicado.mensagem}\n\n"
        f"Esta é uma mensagem automática do Diário Diniz. "
        f"Em caso de dúvidas, procure a coordenação da escola.\n"
    )

    html = render_to_string(
        "comunicados/email_comunicado.html",
        {
            "comunicado": comunicado,
            "nome_responsavel": saudacao,
            "backend_url": settings.BACKEND_URL.rstrip("/"),
        },
    )
    return assunto, texto, html


def _materializar_destinatarios(comunicado: Comunicado) -> int:
    """Cria uma linha de `ComunicadoDestinatario` por aluno alcançado.

    Roda ANTES do envio: as linhas nascem `pendente` (ou `sem_email`) e
    são atualizadas conforme o provedor responde. Assim um crash no meio
    do lote deixa rastro em vez de apagar o público.

    Idempotente via `ignore_conflicts`: o unique (comunicado, aluno)
    absorve uma segunda materialização do mesmo comunicado sem estourar
    IntegrityError.

    Retorna o total de linhas pretendidas (o público do comunicado).
    """
    linhas = []
    for aluno in resolver_alunos(comunicado).only(
        "id", "nome_completo", "nome_responsavel", "email_responsavel"
    ):
        email = _normalizar_email(aluno.email_responsavel)
        linhas.append(
            ComunicadoDestinatario(
                comunicado=comunicado,
                aluno=aluno,
                email=email,
                nome_responsavel=aluno.nome_responsavel,
                status=(
                    ComunicadoDestinatario.Status.PENDENTE
                    if email
                    else ComunicadoDestinatario.Status.SEM_EMAIL
                ),
            )
        )
    ComunicadoDestinatario.objects.bulk_create(linhas, ignore_conflicts=True)
    return len(linhas)


def _agrupar_por_email(comunicado: Comunicado) -> dict[str, dict]:
    """Agrupa as linhas pendentes por endereço — a dedup propriamente dita.

    Devolve `{email: {"nome": str, "ids": [pk, ...]}}`. Um grupo recebe
    UMA mensagem; o resultado dela é aplicado a todas as linhas do grupo
    (os dois irmãos ficam `enviado`, ambos rastreáveis).

    O nome usado na saudação é o primeiro não-vazio do grupo: para irmãos
    é o mesmo responsável de qualquer forma.
    """
    grupos: dict[str, dict] = {}
    pendentes = comunicado.destinatarios.filter(
        status=ComunicadoDestinatario.Status.PENDENTE
    ).values_list("id", "email", "nome_responsavel")
    for pk, email, nome in pendentes:
        grupo = grupos.setdefault(email, {"nome": "", "ids": []})
        grupo["ids"].append(pk)
        if not grupo["nome"] and nome:
            grupo["nome"] = nome
    return grupos


def _marcar(ids: list[int], status: str, erro: str = "") -> None:
    """Aplica o resultado do envio a todas as linhas de um grupo."""
    ComunicadoDestinatario.objects.filter(id__in=ids).update(
        status=status,
        erro=erro,
        enviado_em=timezone.now() if status == ComunicadoDestinatario.Status.ENVIADO else None,
        atualizado_em=timezone.now(),
    )


def _disparar(comunicado_id: int, escola_id: int) -> None:
    """Envia o lote e consolida os contadores. NUNCA levanta exceção.

    Roda na thread daemon (ou síncrono em testes). Recebe `escola_id`
    explícito e o reinjeta no `escola_context` porque a thread não herda o
    ContextVar da request — sem isso os logs do disparo sairiam sem a
    escola carimbada.

    Uma falha em um destinatário NÃO aborta o lote: é registrada na linha
    daquele destinatário e o loop segue. Falha na própria conexão (cota
    estourada, provedor fora) derruba o lote inteiro, e aí todas as
    linhas restantes ficam `falhou` com o erro — é o que diferencia
    "email inválido do João" de "a escola estourou a cota do dia".
    """
    ctx = escola_context.set(escola_id)
    try:
        comunicado = Comunicado.objects.get(pk=comunicado_id)
        grupos = _agrupar_por_email(comunicado)

        enviados_ids: list[int] = []
        falhas = 0

        if grupos:
            # Uma conexão pro lote inteiro em vez de uma por mensagem.
            conexao = get_connection()
            try:
                conexao.open()
            except Exception as exc:
                # Nem abriu: marca tudo como falha com o motivo real em
                # vez de deixar o lote em `pendente` pra sempre.
                logger.exception(
                    "Comunicado %s: falha ao abrir conexão de email.",
                    comunicado_id,
                )
                for grupo in grupos.values():
                    _marcar(
                        grupo["ids"],
                        ComunicadoDestinatario.Status.FALHOU,
                        str(exc),
                    )
                    falhas += len(grupo["ids"])
                grupos = {}
                conexao = None

            if conexao is not None:
                try:
                    for email, grupo in grupos.items():
                        assunto, texto, html = montar_email_comunicado(
                            comunicado, grupo["nome"]
                        )
                        try:
                            msg = EmailMultiAlternatives(
                                subject=assunto,
                                body=texto,
                                from_email=settings.DEFAULT_FROM_EMAIL,
                                to=[email],
                                connection=conexao,
                            )
                            msg.attach_alternative(html, "text/html")
                            msg.send(fail_silently=False)
                        except Exception as exc:
                            logger.warning(
                                "Comunicado %s: falha ao enviar para %s: %s",
                                comunicado_id,
                                email,
                                exc,
                            )
                            _marcar(
                                grupo["ids"],
                                ComunicadoDestinatario.Status.FALHOU,
                                str(exc),
                            )
                            falhas += len(grupo["ids"])
                        else:
                            enviados_ids.extend(grupo["ids"])
                finally:
                    # Fechar a conexão nunca deve mascarar o resultado do
                    # lote: o que importa já está persistido nas linhas.
                    try:
                        conexao.close()
                    except Exception:
                        logger.warning(
                            "Comunicado %s: erro ao fechar conexão de email.",
                            comunicado_id,
                            exc_info=True,
                        )

        if enviados_ids:
            _marcar(enviados_ids, ComunicadoDestinatario.Status.ENVIADO)

        _consolidar(comunicado)
        logger.info(
            "Comunicado %s: disparo concluído (%s enviados, %s falhas).",
            comunicado_id,
            len(enviados_ids),
            falhas,
        )
    except Exception:
        # Rede de segurança: a thread não pode morrer calada. Tenta ao
        # menos tirar o comunicado de `enviando` pra UI não ficar presa.
        logger.exception("Comunicado %s: disparo abortado.", comunicado_id)
        Comunicado.objects.filter(
            pk=comunicado_id, status=Comunicado.Status.ENVIANDO
        ).update(status=Comunicado.Status.FALHOU, atualizado_em=timezone.now())
    finally:
        escola_context.reset(ctx)


def _consolidar(comunicado: Comunicado) -> None:
    """Fecha o comunicado: recalcula contadores a partir das linhas.

    Os contadores vêm da agregação real das linhas (não de variáveis
    acumuladas no loop) pra que o número exibido na UI seja sempre o que
    está no banco.

    `falhou` é reservado pro disparo que não entregou NADA tendo
    destinatários com email — assim "enviado com 3 falhas de 142" não é
    confundido com "não saiu".
    """
    Status = ComunicadoDestinatario.Status
    linhas = comunicado.destinatarios.all()
    total = linhas.count()
    enviados = linhas.filter(status=Status.ENVIADO).count()
    falhas = linhas.filter(status=Status.FALHOU).count()
    sem_email = linhas.filter(status=Status.SEM_EMAIL).count()

    com_email = total - sem_email
    status_final = (
        Comunicado.Status.FALHOU
        if com_email > 0 and enviados == 0
        else Comunicado.Status.ENVIADO
    )

    Comunicado.objects.filter(pk=comunicado.pk).update(
        status=status_final,
        enviado_em=timezone.now(),
        total_destinatarios=total,
        total_enviados=enviados,
        total_falhas=falhas,
        total_sem_email=sem_email,
        atualizado_em=timezone.now(),
    )


def enviar_comunicado(comunicado: Comunicado, usuario=None) -> bool:
    """Dispara o comunicado. Retorna False se ele não estava em rascunho.

    A transição `rascunho → enviando` é feita com um UPDATE condicional
    (`filter(status=RASCUNHO).update(...)`) e o resultado é checado: dois
    cliques simultâneos no botão "Enviar" fazem só o primeiro passar, e o
    segundo recebe False. Sem isso, a janela entre "ler status" e
    "escrever status" permitiria enviar o lote duas vezes — e email
    duplicado pra escola inteira não tem desfazer.

    O público é materializado aqui (na request, com DB saudável) e o envio
    vai pra thread daemon. Em testes o envio é síncrono.
    """
    agora = timezone.now()
    transicionou = Comunicado.objects.filter(
        pk=comunicado.pk, status=Comunicado.Status.RASCUNHO
    ).update(
        status=Comunicado.Status.ENVIANDO,
        enviado_por=usuario,
        atualizado_em=agora,
    )
    if not transicionou:
        logger.warning(
            "Comunicado %s: envio ignorado (status atual não é rascunho).",
            comunicado.pk,
        )
        return False

    comunicado.refresh_from_db()
    total = _materializar_destinatarios(comunicado)
    Comunicado.objects.filter(pk=comunicado.pk).update(
        total_destinatarios=total, atualizado_em=agora
    )

    args = (comunicado.pk, comunicado.escola_id)
    if getattr(settings, "TESTING", False):
        _disparar(*args)
    else:
        # `on_commit`: a thread lê o comunicado e os destinatários do
        # banco. Disparada antes do commit, ela poderia não encontrar as
        # linhas que esta request acabou de criar.
        transaction.on_commit(
            lambda: threading.Thread(
                target=_disparar, args=args, daemon=True
            ).start()
        )
    return True
