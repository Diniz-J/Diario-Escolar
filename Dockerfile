# Dockerfile do backend Django — multi-stage.
#
# Estágios:
#   base  — dependências Python instaladas + código copiado (comum aos dois).
#   dev   — usado pelo docker-compose.yml; o comando (runserver) vem do compose.
#   prod  — usado pelo docker-compose.prod.yml; roda collectstatic e sobe gunicorn.
#
# psycopg[binary] já traz o driver compilado, então não precisamos de
# gcc/libpq-dev no sistema — a imagem fica mais leve.

FROM python:3.12-slim AS base

# PYTHONUNBUFFERED: logs saem na hora (sem buffer) — essencial pra ver
# logs em container. PYTHONDONTWRITEBYTECODE: não gera .pyc no container.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# ---------------------------------------------------------------------------
# Desenvolvimento: imagem fica pronta; o docker-compose define o comando
# (migrate + runserver) e monta o código como volume para hot reload.
FROM base AS dev

# ---------------------------------------------------------------------------
# Produção: coleta estáticos no build e sobe via gunicorn.
FROM base AS prod

# collectstatic precisa que o settings importe sem erro — passamos valores
# falsos só para esse passo (não conecta no banco, não usa a SECRET real).
RUN SECRET_KEY=build-only-collectstatic \
    DB_NAME=build DB_USER=build DB_PASSWORD=build \
    python manage.py collectstatic --noinput

# 3 workers é um ponto de partida razoável; ajuste conforme a CPU do host.
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3"]
