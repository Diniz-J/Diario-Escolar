"""Gera as faturas de uma competência a partir dos planos ativos.

Este é o motor da recorrência. A decisão de ter a recorrência do nosso
lado (e não assinatura nativa do gateway) está no `FINANCEIRO.md` §2.1;
a de usar cron em vez de Celery, no §2.2 — o projeto não tem fila, e o
que garante a idempotência é a constraint de banco, não o agendador.

**Seguro de repetir.** Rodar duas vezes no mesmo mês não duplica nada: a
segunda execução encontra as faturas já criadas e as conta como
ignoradas. É o que permite deixar no cron sem medo e re-rodar à mão
depois de uma falha parcial.

Uso:

    python manage.py financeiro_gerar_faturas                       # mês corrente
    python manage.py financeiro_gerar_faturas --competencia 2026-04
    python manage.py financeiro_gerar_faturas --escola 1
    python manage.py financeiro_gerar_faturas --dry-run

Candidato a cron no dia 1 de cada mês.
"""
from datetime import date, datetime

from django.core.management.base import BaseCommand, CommandError

from apps.financeiro.services import gerar_faturas


class Command(BaseCommand):
    help = "Gera as faturas da competência para os planos de cobrança ativos."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--competencia",
            help="Mês de referência no formato YYYY-MM. Default: mês corrente.",
        )
        parser.add_argument(
            "--escola",
            type=int,
            help="Restringe a uma escola (id). Default: todas.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Mostra o que seria criado, sem escrever no banco.",
        )

    def handle(self, *args, **options) -> None:
        competencia = self._resolver_competencia(options.get("competencia"))
        resultado = gerar_faturas(
            competencia,
            escola_id=options.get("escola"),
            dry_run=options["dry_run"],
        )

        prefixo = "[dry-run] " if options["dry_run"] else ""
        self.stdout.write(
            f"{prefixo}Competência {resultado.competencia:%m/%Y}: "
            f"{resultado.criadas} fatura(s) criada(s), "
            f"{resultado.ignoradas} já existente(s), "
            f"{resultado.planos_considerados} plano(s) considerado(s)."
        )
        if resultado.alunos_com_plano_concorrente:
            # Não é erro: é a virada de contrato no meio do mês. Fica
            # visível porque a escola precisa saber qual plano cobrou.
            self.stdout.write(
                self.style.WARNING(
                    "Alunos com mais de um plano cobrindo o mês (cobrados pelo "
                    "contrato mais antigo, conforme FINANCEIRO.md §2.8): "
                    + ", ".join(
                        str(i) for i in resultado.alunos_com_plano_concorrente
                    )
                )
            )

    @staticmethod
    def _resolver_competencia(valor: str | None) -> date:
        if not valor:
            return date.today().replace(day=1)
        try:
            return datetime.strptime(valor, "%Y-%m").date().replace(day=1)
        except ValueError as exc:
            raise CommandError(
                f"Competência inválida: {valor!r}. Use o formato YYYY-MM "
                "(ex.: 2026-04)."
            ) from exc
