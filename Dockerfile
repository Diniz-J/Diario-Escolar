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

# Dependências de sistema do WeasyPrint (renderização do boletim em PDF).
# `libpango-1.0-0` + `libpangoft2-1.0-0` cobrem layout/fontes. `libharfbuzz0b`
# cobre shaping. `fonts-dejavu` garante fonte padrão pra evitar boletim
# em "tofu" quando o sistema tá sem fontes. Versão >= 60 do WeasyPrint
# não precisa mais de libcairo. Cleanup do apt lists pra manter a
# imagem leve.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libharfbuzz0b \
    fonts-dejavu \
    && rm -rf /var/lib/apt/lists/*

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

# Sobe via entrypoint: aplica migrations (+ superusuário opcional via env)
# e então o gunicorn. Necessário no free tier do Render, que não tem
# Pre-Deploy Command nem Shell. Concorrência e porta vêm de env
# (GUNICORN_*, PORT) — ver entrypoint.sh. O compose local não usa este
# CMD (lá o `command:` do compose sobrescreve e faz o migrate).
CMD ["sh", "entrypoint.sh"]
