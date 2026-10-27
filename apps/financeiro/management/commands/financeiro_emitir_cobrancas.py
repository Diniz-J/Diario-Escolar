"""Emite no gateway as cobranças das faturas que ainda não foram emitidas.

Passo separado da geração, e não efeito dela, por dois motivos
(`FINANCEIRO.md` §6): `gerar_faturas` roda numa transação e em lote, e
pendurar N chamadas HTTP ali prenderia o lock das faturas pelo tempo do
provedor; e uma falha no meio desfaria as cobranças que já tinham sido
criadas lá, que continuariam existindo no provedor sem fatura apontando
pra elas.

Seguro de repetir: `emitir_cobranca` devolve a fatura inalterada quando
ela já tem `id_externo`, então a segunda execução só tenta o que faltou.

Uso:

    python manage.py financeiro_emitir_cobrancas
    python manage.py financeiro_emitir_cobrancas --competencia 2026-03
    python manage.py financeiro_emitir_cobrancas --escola 1 --metodo pix

Candidato a cron logo depois do `financeiro_gerar_faturas`, dia 1.
"""
from datetime import datetime

from django.core.management.base import BaseCommand, CommandError

from apps.financeiro.gateways import ErroDeGateway, gateway_configurado
from apps.financeiro.models import Fatura
from apps.financeiro.services import EmissaoRecusadaError, emitir_cobranca


class Command(BaseCommand):
    help = "Cria no gateway a cobrança das faturas em aberto sem id externo."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--competencia",
            help="Restringe a uma competência (YYYY-MM). Default: todas.",
        )
        parser.add_argument(
            "--escola",
            type=int,
            help="Restringe a uma escola (id). Default: todas.",
        )
        parser.add_argument(
            "--metodo",
            default="",
            help=(
                "Meio de pagamento (pix, boleto, cartao). Default: deixa o "
                "pagador escolher na página do provedor."
            ),
        )

    def handle(self, *args, **options) -> None:
        gateway = gateway_configurado()
        if gateway is None:
            raise CommandError(
                "Cobrança online não está configurada (falta ASAAS_API_KEY)."
            )

        # Só o que está em aberto: paga não precisa de cobrança e cancelada
        # não deve receber uma.
        qs = Fatura.objects.filter(
            id_externo="",
            status__in=[Fatura.Status.PENDENTE, Fatura.Status.VENCIDO],
        ).select_related("plano__pagador", "aluno")

        if options.get("escola"):
            qs = qs.filter(escola_id=options["escola"])
        if options.get("competencia"):
            qs = qs.filter(competencia=self._competencia(options["competencia"]))

        emitidas = falhas = 0
        for fatura in qs.order_by("competencia", "id"):
            try:
                emitir_cobranca(fatura, gateway, metodo=options["metodo"])
            except (EmissaoRecusadaError, ErroDeGateway) as exc:
                # Uma fatura que falha não pode parar o lote: o motivo mais
                # comum é cadastro incompleto de um aluno só, e abortar
                # deixaria sem cobrança a escola inteira.
                falhas += 1
                self.stderr.write(f"Fatura {fatura.pk} ({fatura.aluno}): {exc}")
                continue
            emitidas += 1

        self.stdout.write(f"{emitidas} cobrança(s) emitida(s), {falhas} falha(s).")

    @staticmethod
    def _competencia(valor: str):
        try:
            return datetime.strptime(valor, "%Y-%m").date().replace(day=1)
        except ValueError as exc:
            raise CommandError(
                f"Competência inválida: {valor!r}. Use YYYY-MM."
            ) from exc
