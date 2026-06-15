#!/usr/bin/env bash
#
# Backup do banco PostgreSQL do Diário Escolar.
#
# Gera um dump comprimido (formato custom do pg_dump, restaurável com
# pg_restore) na pasta ./backups e remove dumps mais antigos que
# RETENTION_DAYS. Pensado para rodar no servidor de produção, onde o
# Postgres sobe via docker-compose.prod.yml.
#
# Uso:
#   ./scripts/backup.sh
#
# Variáveis de ambiente (com defaults):
#   COMPOSE_FILE     arquivo compose (default: docker-compose.prod.yml)
#   DB_SERVICE       nome do serviço do banco no compose (default: db)
#   BACKEND_SERVICE  nome do serviço do backend no compose (default: backend)
#   BACKUP_DIR       pasta destino (default: ./backups)
#   RETENTION_DAYS   dias a manter (default: 7)
#   PURGE_TOKENS     "1" pra rodar purge_expired_tokens após o dump
#                    (default: 1 — desligue com PURGE_TOKENS=0)
#   ENV_FILE         arquivo de env com DB_* (default: .env.prod)
#
# As credenciais (DB_NAME, DB_USER, DB_PASSWORD) são lidas do ENV_FILE.

set -euo pipefail

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.prod.yml}"
DB_SERVICE="${DB_SERVICE:-db}"
BACKEND_SERVICE="${BACKEND_SERVICE:-backend}"
BACKUP_DIR="${BACKUP_DIR:-./backups}"
RETENTION_DAYS="${RETENTION_DAYS:-7}"
PURGE_TOKENS="${PURGE_TOKENS:-1}"
ENV_FILE="${ENV_FILE:-.env.prod}"

# Carrega as credenciais do banco a partir do arquivo de env, se existir.
if [ -f "$ENV_FILE" ]; then
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
fi

: "${DB_NAME:?Defina DB_NAME (no $ENV_FILE ou no ambiente)}"
: "${DB_USER:?Defina DB_USER (no $ENV_FILE ou no ambiente)}"
: "${DB_PASSWORD:?Defina DB_PASSWORD (no $ENV_FILE ou no ambiente)}"

mkdir -p "$BACKUP_DIR"

TIMESTAMP="$(date +%Y-%m-%d_%H%M%S)"
ARQUIVO="$BACKUP_DIR/diario_escolar_${TIMESTAMP}.dump"

echo "[backup] Gerando dump de '$DB_NAME' -> $ARQUIVO"

# -Fc = formato custom (comprimido, restaurável seletivamente com pg_restore).
# PGPASSWORD passado por -e garante autenticação independente do pg_hba.
docker compose -f "$COMPOSE_FILE" exec -T -e PGPASSWORD="$DB_PASSWORD" "$DB_SERVICE" \
  pg_dump -U "$DB_USER" -d "$DB_NAME" -Fc > "$ARQUIVO"

# Falha cedo se o dump saiu vazio (erro silencioso de conexão, p.ex.).
if [ ! -s "$ARQUIVO" ]; then
  echo "[backup] ERRO: dump vazio — removendo $ARQUIVO" >&2
  rm -f "$ARQUIVO"
  exit 1
fi

TAMANHO="$(du -h "$ARQUIVO" | cut -f1)"
echo "[backup] OK ($TAMANHO)"

# Retenção: apaga dumps com mais de RETENTION_DAYS dias.
echo "[backup] Limpando dumps com mais de ${RETENTION_DAYS} dias"
find "$BACKUP_DIR" -name "diario_escolar_*.dump" -type f \
  -mtime "+${RETENTION_DAYS}" -print -delete

# Limpeza de tokens de redefinição de senha expirados — evita que a
# tabela cresça indefinidamente em prod. Idempotente; falha não invalida
# o backup (já feito acima). Desligue com PURGE_TOKENS=0.
if [ "$PURGE_TOKENS" = "1" ]; then
  echo "[backup] Limpando PasswordResetToken expirados (>30d)"
  if ! docker compose -f "$COMPOSE_FILE" exec -T "$BACKEND_SERVICE" \
      python manage.py purge_expired_tokens; then
    echo "[backup] AVISO: purge_expired_tokens falhou (backup já está OK)" >&2
  fi
fi

echo "[backup] Concluído."
