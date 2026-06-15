"""Limpa PasswordResetToken expirados há mais que a janela de retenção.

Token de reset é one-shot e expira em 1h, mas a linha continua no banco
indefinidamente — sem cleanup, a tabela cresce a cada pedido de "esqueci
minha senha". Em prod com tráfego real essa tabela vira lixo crescente.

A janela default de **30 dias após a expiração** preserva um rastro pra
forense ("quando esse usuário pediu reset?") antes de remover. Tokens
expirados há menos que isso ficam.

Uso típico (plugado no cron do backup em `scripts/backup.sh`):

    python manage.py purge_expired_tokens

Pra inspecionar sem apagar:

    python manage.py purge_expired_tokens --dry-run

Pra mudar a janela (ex.: política de retenção mais agressiva):

    python manage.py purge_expired_tokens --dias 7
"""
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.accounts.models import PasswordResetToken


class Command(BaseCommand):
    help = (
        "Remove PasswordResetToken expirados há mais que --dias dias "
        "(default 30)."
    )

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--dias",
            type=int,
            default=30,
            help="Janela de retenção após a expiração, em dias (default: 30).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Apenas conta os tokens que seriam apagados, sem deletar.",
        )

    def handle(self, *args, **options) -> None:
        dias: int = options["dias"]
        dry_run: bool = options["dry_run"]

        if dias < 0:
            self.stderr.write("--dias precisa ser >= 0")
            return

        corte = timezone.now() - timedelta(days=dias)
        qs = PasswordResetToken.objects.filter(expira_em__lt=corte)

        total = qs.count()
        if total == 0:
            self.stdout.write("Nenhum token expirado para apagar.")
            return

        if dry_run:
            self.stdout.write(
                f"[dry-run] {total} token(s) seriam apagados "
                f"(expira_em < {corte.isoformat()})."
            )
            return

        # `delete()` no queryset envia um único DELETE SQL — sem N round-trips.
        apagados, _ = qs.delete()
        self.stdout.write(
            f"{apagados} token(s) apagado(s) (expira_em < {corte.isoformat()})."
        )
