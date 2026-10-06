"""Retoma comunicados cujo disparo travou no meio do lote.

Por que isto existe: o envio roda numa **thread daemon**, e thread daemon
morre junto com o processo sem finalizar. No Render, deploy e restart de
container são rotina. Se o processo cai no meio de um lote de 150 emails,
parte das linhas fica `enviado`, o resto fica `pendente`, e o comunicado
fica parado em `enviando` — estado que não é editável nem reenviável pela
API (o `enviar` devolve 409 por não estar em rascunho).

Sem este comando o registro só saía desse estado com UPDATE manual no
banco, e os responsáveis que faltavam nunca receberiam o comunicado.

**Não duplica email.** `_disparar` reagrupa apenas as linhas que ainda
estão `pendente` (ver `_agrupar_por_email`), então quem já recebeu é
ignorado. É essa propriedade que torna a retomada segura.

Uso:

    python manage.py comunicados_retomar              # parados há 15min+
    python manage.py comunicados_retomar --minutos 60
    python manage.py comunicados_retomar --dry-run
    python manage.py comunicados_retomar --id 42      # um específico

Bom candidato a cron (a cada 10–15 min). Sem nada travado, não faz nada.
"""
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.comunicados.models import Comunicado, ComunicadoDestinatario
from apps.comunicados.services import _disparar

# Default conservador. O disparo carimba `atualizado_em` a cada 25 grupos
# (ver `_HEARTBEAT_CADA`), então um lote saudável, mesmo grande, nunca
# fica 15 minutos sem sinal de vida. Silêncio além disso = travou.
MINUTOS_DEFAULT = 15


class Command(BaseCommand):
    help = "Retoma comunicados cujo disparo travou (status `enviando` sem progresso)."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--minutos",
            type=int,
            default=MINUTOS_DEFAULT,
            help=(
                "Quantos minutos sem progresso para considerar travado "
                f"(default: {MINUTOS_DEFAULT})."
            ),
        )
        parser.add_argument(
            "--id",
            type=int,
            default=None,
            help="Retoma um comunicado específico, ignorando o tempo sem progresso.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Só lista o que seria retomado, sem enviar nada.",
        )

    def handle(self, *args, **options) -> None:
        minutos = options["minutos"]
        comunicado_id = options["id"]
        dry_run = options["dry_run"]

        candidatos = Comunicado.objects.filter(status=Comunicado.Status.ENVIANDO)
        if comunicado_id is not None:
            candidatos = candidatos.filter(pk=comunicado_id)
        else:
            limite = timezone.now() - timedelta(minutes=minutos)
            candidatos = candidatos.filter(atualizado_em__lt=limite)

        candidatos = list(candidatos.order_by("criado_em"))

        if not candidatos:
            self.stdout.write("Nenhum comunicado travado.")
            return

        for comunicado in candidatos:
            pendentes = comunicado.destinatarios.filter(
                status=ComunicadoDestinatario.Status.PENDENTE
            ).count()
            rotulo = (
                f"#{comunicado.pk} \"{comunicado.titulo}\" "
                f"(escola {comunicado.escola_id}, {pendentes} pendentes, "
                f"sem progresso desde {comunicado.atualizado_em:%d/%m %H:%M})"
            )

            if dry_run:
                self.stdout.write(f"[dry-run] retomaria {rotulo}")
                continue

            # Claim otimista: o UPDATE só passa se `atualizado_em` ainda
            # for o valor que lemos. Impede que duas execuções do comando
            # (cron sobreposto, operador rodando à mão junto) processem o
            # mesmo comunicado em paralelo e enviem em dobro.
            reivindicou = Comunicado.objects.filter(
                pk=comunicado.pk,
                status=Comunicado.Status.ENVIANDO,
                atualizado_em=comunicado.atualizado_em,
            ).update(atualizado_em=timezone.now())
            if not reivindicou:
                self.stdout.write(
                    self.style.WARNING(
                        f"Pulando {rotulo}: outro processo assumiu."
                    )
                )
                continue

            self.stdout.write(f"Retomando {rotulo}...")
            # Síncrono de propósito: num comando de CLI/cron queremos o
            # processo vivo até o fim do lote. `_disparar` nunca levanta e
            # consolida os contadores no final.
            _disparar(comunicado.pk, comunicado.escola_id)

            comunicado.refresh_from_db()
            self.stdout.write(
                self.style.SUCCESS(
                    f"  #{comunicado.pk} → {comunicado.status} "
                    f"({comunicado.total_enviados} enviados, "
                    f"{comunicado.total_falhas} falhas, "
                    f"{comunicado.total_sem_email} sem email)"
                )
            )
