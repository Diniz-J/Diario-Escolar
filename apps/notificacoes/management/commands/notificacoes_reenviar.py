"""Reenvia as mensagens do outbox que não saíram.

Por que existe: o despacho roda numa thread daemon, e thread daemon morre
junto com o processo sem terminar. No Render, deploy e restart são
rotina, e o free tier ainda hiberna. Se o processo cai no meio, a linha
fica `pendente` e ninguém mais tenta — era exatamente esse o buraco que
o outbox abriu espaço pra fechar.

Quatro filtros, e cada um existe por um motivo:

**Origem retentável.** Só ocorrência e pagamento. Convite e link de senha
carregam token com prazo e reenviá-los entrega link morto — ver
`ORIGENS_RETENTAVEIS` em `models.py`.

**Idade mínima.** Uma linha criada há dois segundos provavelmente está
sendo enviada pela thread viva neste instante; pegá-la aqui duplicaria o
email. Mesmo raciocínio do `comunicados_retomar`, que usa 15 minutos.

**Idade máxima.** Aviso de ocorrência que chega uma semana depois não
informa, confunde. Passado o teto a linha fica como registro e para de
ser candidata; o caminho certo aí é a escola reemitir pela tela, não o
cron entregar notícia velha em silêncio.

**Teto de tentativas.** Endereço inválido falha pra sempre, e insistir
queima a cota de 300/dia do Brevo, que é compartilhada com comunicado e
ocorrência. Depois do teto a linha fica `falhou` com o erro do provedor,
que é o que a secretaria lê pra decidir o que fazer.

Uso:

    python manage.py notificacoes_reenviar
    python manage.py notificacoes_reenviar --minutos 5 --dry-run
"""
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.notificacoes.models import ORIGENS_RETENTAVEIS, Mensagem
from apps.notificacoes.services import despachar

MINUTOS_DEFAULT = 15
IDADE_MAXIMA_HORAS = 24
TETO_TENTATIVAS = 5


def pendentes(minutos: int = MINUTOS_DEFAULT):
    """Queryset das mensagens candidatas a reenvio."""
    agora = timezone.now()
    return Mensagem.objects.filter(
        status__in=[Mensagem.Status.PENDENTE, Mensagem.Status.FALHOU],
        origem__in=list(ORIGENS_RETENTAVEIS),
        tentativas__lt=TETO_TENTATIVAS,
        criado_em__lte=agora - timedelta(minutes=minutos),
        criado_em__gte=agora - timedelta(hours=IDADE_MAXIMA_HORAS),
    ).order_by("criado_em")


class Command(BaseCommand):
    help = "Reenvia mensagens do outbox que ficaram pendentes ou falharam."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--minutos",
            type=int,
            default=MINUTOS_DEFAULT,
            help=(
                "Idade mínima da mensagem, em minutos. Abaixo disso ela "
                "pode estar sendo enviada pela thread viva."
            ),
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Lista o que seria reenviado, sem enviar.",
        )

    def handle(self, *args, **options) -> None:
        candidatas = list(pendentes(options["minutos"]))
        if not candidatas:
            self.stdout.write("Nada pendente.")
            return

        if options["dry_run"]:
            for mensagem in candidatas:
                self.stdout.write(
                    f"[dry-run] {mensagem.pk} {mensagem.origem} "
                    f"{mensagem.destinatario} (tentativas: {mensagem.tentativas})"
                )
            self.stdout.write(f"{len(candidatas)} mensagem(ns) seriam reenviadas.")
            return

        # Por escola, pra que o contexto de log saia carimbado — os logs
        # são lidos por escola (ver `EscolaLogContextMiddleware`).
        por_escola: dict[int | None, list[int]] = {}
        for mensagem in candidatas:
            por_escola.setdefault(mensagem.escola_id, []).append(mensagem.pk)

        enviadas = 0
        for escola_id, ids in por_escola.items():
            enviadas += despachar(ids, escola_id)

        self.stdout.write(
            f"{enviadas} de {len(candidatas)} mensagem(ns) enviada(s)."
        )
