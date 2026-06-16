"""Logging estruturado em JSON para o Diário Escolar.

Uma linha = um objeto JSON, pensado pra ser indexável pela plataforma de
logs (Render/Sentry/etc.) em vez de texto corrido. Campos fixos: `ts`,
`level`, `logger`, `msg`; mais `exc`/`stack` quando há exceção. Qualquer
campo passado via `extra={...}` no log entra como chave de primeiro nível
— é o que permite enriquecer com `escola_id`, `request_id`, etc. sem
mexer no formatter.
"""
import json
import logging
from contextvars import ContextVar
from datetime import datetime, timezone

# Escola da request atual, propagada via ContextVar (isolado por
# request/thread). Alimentado pelo `EscolaLogContextMiddleware` a partir do
# claim `escola_id` do JWT; lido pelo `EscolaLogFilter` pra carimbar todo
# log da request. Fora de uma request autenticada fica None.
escola_context: ContextVar["int | None"] = ContextVar("escola_id", default=None)


class EscolaLogFilter(logging.Filter):
    """Carimba `escola_id` em todo LogRecord, lido do ContextVar da request.

    Permite fatiar o log total por escola num sistema multi-tenant. Fora de
    uma request (tarefas de sistema, anônimo) o campo sai como None.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        record.escola_id = escola_context.get()
        return True


# Atributos padrão de um LogRecord. Tudo que NÃO está aqui foi passado
# via `extra={...}` e deve ir pro JSON como campo estruturado.
_ATRIBUTOS_PADRAO = frozenset(
    logging.makeLogRecord({}).__dict__.keys()
) | {"message", "asctime", "taskName"}


class JsonFormatter(logging.Formatter):
    """Serializa cada LogRecord como uma linha JSON."""

    def format(self, record: logging.LogRecord) -> str:
        dados = {
            "ts": datetime.fromtimestamp(
                record.created, tz=timezone.utc
            ).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }

        # Campos extras (logger.info("...", extra={"escola_id": 5})).
        for chave, valor in record.__dict__.items():
            if chave not in _ATRIBUTOS_PADRAO and not chave.startswith("_"):
                dados[chave] = valor

        # Exceção: stack trace completo num único campo.
        if record.exc_info:
            dados["exc"] = self.formatException(record.exc_info)
        if record.stack_info:
            dados["stack"] = self.formatStack(record.stack_info)

        # `default=str` garante que tipos não-serializáveis (datetime,
        # Decimal, UUID) não derrubem o log — viram string em vez de erro.
        return json.dumps(dados, ensure_ascii=False, default=str)
