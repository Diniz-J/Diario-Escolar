"""Endpoint que dispara as tarefas periódicas do projeto.

**Por que isto existe.** Nada no projeto dispara tarefa periódica: não
há cron no Render nem workflow agendado. Por isso o `comunicados_retomar`
era um comando que ninguém rodava, os três commands do financeiro estão
parados como pendência operacional e a retentativa do outbox nasceria
morta. Um workflow agendado do GitHub Actions chama esta rota, e o
Actions agendado é gratuito — não entra provedor novo, e a chamada ainda
acorda o serviço que hiberna no free tier.

**É a segunda rota sem autenticação de usuário do projeto**, e a primeira
que *executa* algo em vez de só receber dado. Daí o desenho:

- **Lista de permissão, nunca o nome que vier no corpo.** `TAREFAS` mapeia
  um apelido pra um management command fixo. Aceitar o nome da request
  seria entregar `call_command` com entrada externa — qualquer command do
  projeto e do Django, incluindo os de dados de demonstração.
- **Token em comparação de tempo constante**, mesmo motivo do webhook do
  Asaas: `==` sai no primeiro byte diferente e vaza o prefixo pra quem
  mede o tempo.
- **Sem token configurado, recusa.** Aceitar quando a env está vazia
  transformaria instalação mal configurada em endpoint aberto pra
  disparar cobrança.
- **Uma tarefa que falha não impede as outras.** O corpo da resposta diz
  o desfecho de cada uma; a falha de `gerar_faturas` não pode cancelar a
  retentativa de email.

A rota responde o resultado de cada tarefa em JSON, porque é isso que
aparece no log do Actions — e é só ali que alguém vai olhar quando algo
parar de rodar.
"""
import hmac
import io
import logging

from django.conf import settings
from django.core.management import call_command
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

logger = logging.getLogger(__name__)

HEADER_TOKEN = "HTTP_X_TAREFAS_TOKEN"

# Apelido → management command. **Fixo.** Ver o docstring: o nome nunca
# vem da request.
TAREFAS: dict[str, str] = {
    "email": "notificacoes_reenviar",
    "comunicados": "comunicados_retomar",
    # Financeiro e limpeza de token entraram aqui pela mesma razão do
    # email: os commands existem desde as fatias do `FINANCEIRO.md` e
    # nunca rodaram, porque não havia gatilho em ambiente nenhum.
    "faturas": "financeiro_gerar_faturas",
    "cobrancas": "financeiro_emitir_cobrancas",
    "vencidas": "financeiro_marcar_vencidas",
    "tokens": "purge_expired_tokens",
}


class ExecutarTarefasView(APIView):
    """`POST /api/v1/tarefas/executar/?tarefas=email,comunicados`.

    O parâmetro `tarefas` é obrigatório — ver `_tarefas_pedidas`.
    """

    authentication_classes: list = []
    permission_classes = [AllowAny]

    def post(self, request):
        if not self._token_valido(request):
            # 401 sem detalhe: a resposta não deve ajudar a descobrir se
            # faltou token ou se o servidor está sem configuração.
            logger.warning("Execução de tarefas recusada: token inválido.")
            return Response(status=status.HTTP_401_UNAUTHORIZED)

        pedidas = self._tarefas_pedidas(request)
        if pedidas is None:
            return Response(
                {
                    "detail": (
                        "Informe `?tarefas=` com um ou mais apelidos "
                        "conhecidos."
                    ),
                    "disponiveis": sorted(TAREFAS),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        resultados = {}
        for apelido in pedidas:
            resultados[apelido] = self._executar(TAREFAS[apelido])
        return Response({"resultados": resultados}, status=status.HTTP_200_OK)

    def _token_valido(self, request) -> bool:
        esperado = getattr(settings, "TAREFAS_TOKEN", "") or ""
        if not esperado:
            logger.error(
                "TAREFAS_TOKEN não configurado — execução de tarefas "
                "recusada. Sem isto a rota ficaria aberta."
            )
            return False
        recebido = request.META.get(HEADER_TOKEN, "")
        return hmac.compare_digest(recebido, esperado)

    @staticmethod
    def _tarefas_pedidas(request) -> list[str] | None:
        """Lê `?tarefas=a,b`. **Obrigatório** — sem default de "todas".

        Rodar tudo por omissão era aceitável enquanto a lista só tinha
        reenvio de email, que é idempotente e barato. Com o financeiro
        dentro deixou de ser: `emitir_cobrancas` cria cobrança de verdade
        no provedor, e um workflow que esquecesse o parâmetro emitiria a
        cada quinze minutos. O parâmetro ausente agora é erro, que é
        barulhento e reversível, em vez de um default que gasta dinheiro.

        Devolve None pra parâmetro ausente ou com apelido desconhecido —
        recusar o lote inteiro é melhor que rodar metade em silêncio,
        porque quem escreveu o workflow errado precisa ver o erro.
        """
        bruto = request.query_params.get("tarefas", "").strip()
        if not bruto:
            return None
        pedidas = [parte.strip() for parte in bruto.split(",") if parte.strip()]
        if any(apelido not in TAREFAS for apelido in pedidas):
            return None
        return sorted(set(pedidas))

    @staticmethod
    def _executar(command: str) -> dict:
        """Roda o command e devolve o desfecho, sem deixar exceção subir."""
        saida = io.StringIO()
        try:
            call_command(command, stdout=saida, stderr=saida)
        except Exception as exc:
            logger.exception("Tarefa %s falhou.", command)
            return {"ok": False, "erro": str(exc)[:500]}
        return {"ok": True, "saida": saida.getvalue().strip()[:2000]}
