"""Move faturas pendentes com vencimento passado para `vencido`.

Existe pra que "quem está inadimplente" seja uma pergunta que o banco
responde — filtro e contagem por `status` — e não um cálculo que só
acontece na leitura de cada fatura. `Fatura.esta_vencida()` continua
sendo a verdade do momento e cobre o dia em que o cron não rodou.

Seguro de repetir: só toca em `pendente`, então a segunda execução do
dia não faz nada.

Uso:

    python manage.py financeiro_marcar_vencidas
    python manage.py financeiro_marcar_vencidas --escola 1

Candidato a cron diário, de manhã.
"""
from django.core.management.base import BaseCommand

from apps.financeiro.services import marcar_vencidas


class Command(BaseCommand):
    help = "Marca como vencidas as faturas pendentes com vencimento passado."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--escola",
            type=int,
            help="Restringe a uma escola (id). Default: todas.",
        )

    def handle(self, *args, **options) -> None:
        total = marcar_vencidas(escola_id=options.get("escola"))
        self.stdout.write(f"{total} fatura(s) marcada(s) como vencida(s).")
