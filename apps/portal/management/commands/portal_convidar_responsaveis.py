"""Envia o convite do portal em lote — onboarding inicial da escola.

Por que comando e não botão "convidar todos": o Brevo free entrega 300
emails/dia, **compartilhados com os comunicados e as ocorrências**. Uma
escola inteira são centenas de convites; um botão esgotaria a cota do dia e
derrubaria os comunicados junto (`PORTAL.md`, seção 2).

Por isso:

- `--limite` (padrão 100) deixa folga na cota pro resto do dia.
- **Retoma de onde parou**: só pega conta ativa, sem senha e sem convite
  pendente. Rodar de novo no dia seguinte continua dos que faltam, sem
  repetir ninguém. Convite que falhou no envio é invalidado
  (`emitir_link`), então volta pra fila.
- **Para no primeiro erro de envio.** O erro típico aqui é cota estourada
  ou provedor fora; insistir só queimaria tentativas.

Uso:

    python manage.py portal_convidar_responsaveis --dry-run
    python manage.py portal_convidar_responsaveis --escola-id 1 --limite 50
"""
from django.contrib.auth.hashers import UNUSABLE_PASSWORD_PREFIX
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Exists, OuterRef
from django.utils import timezone

from apps.portal.models import ConviteResponsavel, Responsavel
from apps.portal.services import emitir_link

LIMITE_PADRAO = 100


def fila_de_convites(escola_id=None):
    """Contas que ainda precisam de convite, em ordem estável."""
    pendente = ConviteResponsavel.objects.filter(
        responsavel=OuterRef("pk"),
        usado_em__isnull=True,
        expira_em__gt=timezone.now(),
    )
    qs = (
        Responsavel.objects.select_related("escola")
        .filter(ativo=True, password__startswith=UNUSABLE_PASSWORD_PREFIX)
        .exclude(Exists(pendente))
        .order_by("id")
    )
    if escola_id is not None:
        qs = qs.filter(escola_id=escola_id)
    return qs


class Command(BaseCommand):
    help = "Envia convites do portal em lote, respeitando um limite por execução."

    def add_arguments(self, parser) -> None:
        parser.add_argument("--escola-id", type=int, default=None)
        parser.add_argument(
            "--limite",
            type=int,
            default=LIMITE_PADRAO,
            help=f"Máximo de convites nesta execução. Padrão: {LIMITE_PADRAO}.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Só lista quem seria convidado, sem enviar nada.",
        )

    def handle(self, *args, **opts) -> None:
        if opts["limite"] < 1:
            raise CommandError("--limite precisa ser pelo menos 1.")

        fila = fila_de_convites(opts["escola_id"])
        total = fila.count()
        lote = list(fila[: opts["limite"]])

        if opts["dry_run"]:
            for r in lote:
                self.stdout.write(f"  convidaria {r.email} ({r.escola.nome})")
            self.stdout.write(
                f"Dry run: {len(lote)} de {total} na fila. Nada foi enviado."
            )
            return

        enviados = 0
        for responsavel in lote:
            try:
                emitir_link(responsavel, ConviteResponsavel.Finalidade.CONVITE)
            except Exception as exc:
                # Sai com erro (código != 0) pra quem roda por cron perceber.
                raise CommandError(
                    f"{enviados} convite(s) enviado(s); envio falhou em "
                    f"{responsavel.email}: {exc}. Lote interrompido, "
                    f"{total - enviados} ainda na fila — rode de novo depois."
                ) from exc
            enviados += 1

        self.stdout.write(
            f"{enviados} convite(s) enviado(s). {total - enviados} ainda na fila."
        )
