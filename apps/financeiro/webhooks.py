"""Endpoint de webhook do Asaas — entrada da conciliação automática.

É a **única rota do projeto sem autenticação de usuário**, e por isso o
desenho aqui é mais conservador que o resto:

- **Token em comparação de tempo constante.** O header deles é
  `asaas-access-token` (não confundir com o `access_token` que nós
  mandamos pra API — sentidos opostos, ver `FINANCEIRO.md` §6).
  `compare_digest` em vez de `==` porque comparação que sai no primeiro
  byte diferente vaza o prefixo do token pra quem mede o tempo.
- **Sem token configurado, recusa.** A alternativa (aceitar quando a env
  está vazia) transformaria uma instalação mal configurada em endpoint
  aberto pra marcar fatura como paga.
- **Grava primeiro, processa depois.** O evento é persistido antes de
  qualquer regra de negócio, pra que falha de processamento não perca o
  fato. A reentrega — comportamento normal do Asaas, não erro — é barrada
  pelo `unique` em `EventoWebhook.id_evento`.
- **Responde 200 mesmo quando o processamento falha.** A doc deles avisa
  que 15 falhas consecutivas de entrega pausam a fila, e uma fila pausada
  para a conciliação da escola inteira. Falha de processamento fica
  registrada no evento (`erro`) e no log; devolver erro pro Asaas só
  trocaria um problema visível por um invisível.

O endpoint é por provedor, de propósito: um segundo gateway ganha a sua
própria rota em vez de disputar esta, e assim nenhum parsing precisa
adivinhar de quem é o corpo.
"""
import hmac
import logging

from django.conf import settings
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .gateways import ErroDeGateway, gateway_configurado
from .gateways.asaas import ler_evento
from .models import EventoWebhook, Fatura
from .notificacoes import notificar_pagamento
from .services import conciliar_cobranca

logger = logging.getLogger(__name__)

HEADER_TOKEN = "HTTP_ASAAS_ACCESS_TOKEN"


class WebhookAsaasView(APIView):
    """Recebe os eventos de cobrança do Asaas."""

    # Sem autenticação de usuário: quem chama é o provedor, e a prova de
    # origem é o token no header. `authentication_classes` vazio pra que o
    # JWT do projeto não tente ler um `Authorization` que não existe.
    authentication_classes: list = []
    permission_classes = [AllowAny]

    def post(self, request):
        if not self._token_valido(request):
            # 401 sem detalhe: a resposta não deve ajudar a descobrir se o
            # que faltou foi o token ou a configuração do servidor.
            logger.warning("Webhook do Asaas recusado: token inválido.")
            return Response(status=status.HTTP_401_UNAUTHORIZED)

        try:
            evento = ler_evento(request.data if isinstance(request.data, dict) else {})
        except ErroDeGateway as exc:
            # Corpo que não dá pra identificar não tem como ser
            # deduplicado nem reprocessado — 400 é honesto, e é raro.
            logger.warning("Webhook do Asaas com corpo inválido: %s", exc.mensagem)
            return Response(
                {"detail": exc.mensagem}, status=status.HTTP_400_BAD_REQUEST
            )

        registro, criado = EventoWebhook.objects.get_or_create(
            id_evento=evento.id_evento,
            defaults={"tipo": evento.tipo, "payload": request.data},
        )
        if not criado and registro.processado_em:
            logger.info(
                "Evento %s já processado — reentrega ignorada.", evento.id_evento
            )
            return Response({"detail": "ja processado"})

        self._processar(registro, evento)
        return Response({"detail": "recebido"})

    # ------------------------------------------------------------------ #
    # Token                                                              #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _token_valido(request) -> bool:
        esperado = getattr(settings, "ASAAS_WEBHOOK_TOKEN", "")
        if not esperado:
            logger.error(
                "Webhook do Asaas chamado sem ASAAS_WEBHOOK_TOKEN "
                "configurado — evento recusado."
            )
            return False
        recebido = request.META.get(HEADER_TOKEN, "")
        return hmac.compare_digest(recebido, esperado)

    # ------------------------------------------------------------------ #
    # Processamento                                                      #
    # ------------------------------------------------------------------ #

    def _processar(self, registro: EventoWebhook, evento) -> None:
        """Resolve a fatura, concilia e avisa o responsável.

        Nunca levanta: a exceção viraria resposta de erro pro Asaas, que
        conta como falha de entrega. O que der errado fica no `erro` do
        evento, no log e (por ele) no Sentry.
        """
        try:
            fatura = self._fatura_do_evento(evento)
            if fatura is None:
                # Evento de cobrança que não é nossa: conta Asaas
                # compartilhada com outro sistema, ou cobrança criada à mão
                # no painel deles. Registrado e encerrado, não é erro.
                registro.erro = "Fatura não encontrada para o evento."
                registro.processado_em = timezone.now()
                registro.save(
                    update_fields=["erro", "processado_em", "atualizado_em"]
                )
                logger.info(
                    "Evento %s: nenhuma fatura corresponde à cobrança %s.",
                    evento.id_evento,
                    evento.id_cobranca,
                )
                return

            registro.fatura = fatura
            gateway = gateway_configurado()
            if gateway is None:
                raise ErroDeGateway(
                    "Evento recebido mas o gateway não está configurado."
                )

            pagamento = conciliar_cobranca(fatura, gateway)
            if pagamento is not None:
                fatura.refresh_from_db()
                notificar_pagamento(fatura, pagamento)

            registro.erro = ""
            registro.processado_em = timezone.now()
        except Exception as exc:
            logger.exception(
                "Evento %s: falha ao processar (cobrança %s).",
                evento.id_evento,
                evento.id_cobranca,
            )
            # `processado_em` fica nulo de propósito: é o que distingue o
            # que falhou do que foi tratado, e o que permite reprocessar.
            registro.erro = str(exc)[:1000]

        registro.save(
            update_fields=["fatura", "erro", "processado_em", "atualizado_em"]
        )

    @staticmethod
    def _fatura_do_evento(evento) -> Fatura | None:
        """Acha a fatura do evento: pelo `id_externo`, ou pela nossa referência.

        O caminho normal é o `id_externo` — a fatura aponta pra cobrança
        desde a emissão. A referência existe pro caso de recuperação: se a
        cobrança foi criada lá e a gravação do `id_externo` aqui falhou no
        meio, é o único jeito de reencontrar a fatura.

        A referência **não** é aceita sozinha. A conta do Asaas pode ser
        compartilhada com outro sistema cujo `externalReference` também
        seja numérico, e aí um "42" deles casaria com a nossa fatura 42 e
        conciliaria dinheiro que não é dela. Só vale quando a fatura aponta
        pra esta cobrança ou ainda não aponta pra nenhuma — o segundo caso
        é o da recuperação, e é o resíduo de risco que sobra: aceitável
        porque exige conta compartilhada, referência numérica e fatura sem
        cobrança ao mesmo tempo.
        """
        fatura = Fatura.objects.filter(id_externo=evento.id_cobranca).first()
        if fatura is not None:
            return fatura

        if not evento.referencia_externa.isdigit():
            return None
        candidata = Fatura.objects.filter(
            pk=int(evento.referencia_externa)
        ).first()
        if candidata is not None and candidata.id_externo == "":
            return candidata
        return None
