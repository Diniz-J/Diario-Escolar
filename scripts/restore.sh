#!/usr/bin/env bash
#
# Restaura um backup do PostgreSQL gerado por scripts/backup.sh.
#
# ATENÇÃO: sobrescreve os dados atuais do banco (--clean). Use com cuidado.
#
# Uso:
#   ./scripts/restore.sh backups/diario_escolar_2026-05-26_120000.dump
#
# Variáveis (com defaults): COMPOSE_FILE, DB_SERVICE, ENV_FILE — iguais ao backup.sh.

set -euo pipefail

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.prod.yml}"
DB_SERVICE="${DB_SERVICE:-db}"
ENV_FILE="${ENV_FILE:-.env.prod}"

ARQUIVO="${1:-}"
if [ -z "$ARQUIVO" ]; then
  echo "Uso: $0 <caminho-do-dump>" >&2
  exit 1
fi
if [ ! -f "$ARQUIVO" ]; then
  echo "ERRO: arquivo não encontrado: $ARQUIVO" >&2
  exit 1
fi

if [ -f "$ENV_FILE" ]; then
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
fi

: "${DB_NAME:?Defina DB_NAME (no $ENV_FILE ou no ambiente)}"
: "${DB_USER:?Defina DB_USER (no $ENV_FILE ou no ambiente)}"
: "${DB_PASSWORD:?Defina DB_PASSWORD (no $ENV_FILE ou no ambiente)}"

echo "ATENÇÃO: isso vai SOBRESCREVER os dados de '$DB_NAME' com $ARQUIVO."
read -r -p "Digite 'CONFIRMA' para prosseguir: " RESPOSTA
if [ "$RESPOSTA" != "CONFIRMA" ]; then
  echo "Cancelado."
  exit 0
fi

echo "[restore] Restaurando $ARQUIVO em '$DB_NAME'..."

# --clean --if-exists derruba objetos antes de recriar; --no-owner evita
# erro de role inexistente; -1 roda tudo numa transação (rollback se falhar).
docker compose -f "$COMPOSE_FILE" exec -T -e PGPASSWORD="$DB_PASSWORD" "$DB_SERVICE" \
  pg_restore -U "$DB_USER" -d "$DB_NAME" --clean --if-exists --no-owner -1 < "$ARQUIVO"

echo "[restore] Concluído."
