"""Outbox de email — o registro do que o sistema tentou mandar.

Por que existe: quatro caminhos (ocorrência, pagamento, convite do portal
e link de senha) disparavam email numa thread daemon e não deixavam
rastro nenhum. Falha de envio virava uma linha de log no Sentry, então a
escola não tinha como saber que o responsável nunca foi avisado da
ocorrência — nem a secretaria, nem o pai. Este modelo é esse rastro, e é
também o que torna a retentativa possível: sem linha gravada não há o que
retomar.

**Não** substitui o `ComunicadoDestinatario`. Aquele é o outbox do
comunicado em lote e tem semântica mais rica (unique por
`(comunicado, aluno, responsavel)`, materialização idempotente, agregado
com estado próprio). Está em produção com lote de 150 e reescrevê-lo pra
caber aqui seria risco sem ganho — ver `comunicados_retomar`.
"""
from django.db import models

from apps.common.models import TimeStampedModel


class Mensagem(TimeStampedModel):
    """Uma mensagem por destinatário, gravada ANTES da tentativa de envio.

    Herda `TimeStampedModel` e **não** `BaseModelEscopado`, apesar de ter
    `escola`: lá o campo é obrigatório, e o link de redefinição de senha
    do admin global não tem escola nenhuma (`Usuario.escola` é opcional).
    Forçar a base escopada deixaria justamente o caminho de recuperação
    de conta sem rastro.
    """

    class Status(models.TextChoices):
        PENDENTE = "pendente", "Pendente"
        ENVIADO = "enviado", "Enviado"
        FALHOU = "falhou", "Falhou"

    class Origem(models.TextChoices):
        OCORRENCIA = "ocorrencia", "Ocorrência"
        PAGAMENTO = "pagamento", "Pagamento"
        CONVITE_PORTAL = "convite_portal", "Convite do portal"
        SENHA = "senha", "Redefinição de senha"

    escola = models.ForeignKey(
        "escola.Escola",
        on_delete=models.PROTECT,
        related_name="+",
        null=True,
        blank=True,
    )
    origem = models.CharField(max_length=20, choices=Origem.choices)
    # Id do objeto que motivou a mensagem (ocorrência, fatura, convite).
    # Não é FK nem GenericForeignKey de propósito: as origens moram em
    # apps diferentes, e `contenttypes` traria uma tabela e um join pra
    # responder "de qual ocorrência era este email", que é a única
    # pergunta que se faz aqui. Sem FK também não há `PROTECT` segurando
    # a limpeza do histórico.
    referencia_id = models.PositiveIntegerField(null=True, blank=True)

    destinatario = models.EmailField()
    assunto = models.CharField(max_length=255)
    corpo_texto = models.TextField()
    corpo_html = models.TextField(blank=True)

    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.PENDENTE,
        db_index=True,
    )
    # Mensagem do provedor quando falhou. É o que distingue "email
    # inválido" (não adianta retentar) de "cota estourada" (adianta).
    erro = models.TextField(blank=True)
    tentativas = models.PositiveSmallIntegerField(default=0)
    enviado_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "mensagem"
        verbose_name_plural = "mensagens"
        ordering = ["-criado_em"]
        indexes = [
            # O caminho da retentativa: status + idade. Sem ele o command
            # varre a tabela inteira a cada execução do cron.
            models.Index(
                fields=["status", "criado_em"], name="mensagem_status_criado"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.get_origem_display()} para {self.destinatario}"


# Quais origens o command de retentativa pode reenviar.
#
# **Ocorrência e pagamento são avisos**: chegar vinte minutos atrasado
# não muda nada, então retentar é puro ganho.
#
# **Convite do portal e link de senha carregam token com prazo**, e aí
# reenviar é pior que não reenviar. No convite o `emitir_link` apaga a
# linha do `ConviteResponsavel` quando o envio falha (convite que nunca
# saiu não pode aparecer como "expirado" pra quem nunca o recebeu), então
# o reenvio entregaria um link cujo token já não existe. No de senha o
# token vale uma hora, e o cron pode rodar depois disso — o responsável
# clicaria num link morto e concluiria que o sistema está quebrado, em
# vez de simplesmente pedir outro.
#
# As duas continuam sendo **gravadas** no outbox: o rastro de que se
# tentou avisar alguém vale mesmo quando o reenvio não vale.
ORIGENS_RETENTAVEIS = frozenset(
    {Mensagem.Origem.OCORRENCIA, Mensagem.Origem.PAGAMENTO}
)
