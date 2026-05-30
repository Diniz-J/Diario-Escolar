#!/usr/bin/env sh
# Entrypoint de produção (Render/PaaS).
#
# Aplica migrations e, se as variáveis DJANGO_SUPERUSER_* estiverem
# definidas, cria o superusuário — tudo no start do container. Isso é
# necessário porque o free tier do Render não oferece Pre-Deploy Command
# nem Shell, então não há outro lugar pra rodar esses comandos.
#
# Não é usado pelo docker-compose local (lá o `command:` do compose já
# faz o migrate). Em produção PaaS, o Dockerfile chama este script.
set -e

echo "[entrypoint] Aplicando migrations..."
python manage.py migrate --noinput

# Cria o superusuário se as credenciais vierem por env. `createsuperuser
# --noinput` lê DJANGO_SUPERUSER_USERNAME/PASSWORD/EMAIL. O `|| true`
# evita derrubar o boot quando o usuário já existe (deploys seguintes).
if [ -n "${DJANGO_SUPERUSER_USERNAME:-}" ] && [ -n "${DJANGO_SUPERUSER_PASSWORD:-}" ]; then
  echo "[entrypoint] Garantindo superusuário ${DJANGO_SUPERUSER_USERNAME}..."
  python manage.py createsuperuser --noinput || true
fi

# Backfill do audit log: dá uma entrada histórica "+ created" pros registros
# que existem ANTES de o modelo ganhar HistoricalRecords (ex.: alunos do
# seed em prod, criados antes do PR de audit log). É idempotente — só
# popula objetos que ainda não têm histórico — então rodar a cada boot é
# barato. `|| true` evita derrubar o serviço se rolar um erro pontual.
echo "[entrypoint] Backfill do audit log (populate_history)..."
python manage.py populate_history --auto || true

echo "[entrypoint] Subindo gunicorn..."
exec gunicorn config.wsgi:application \
  --bind "0.0.0.0:${PORT:-8000}" \
  --workers "${GUNICORN_WORKERS:-1}" \
  --threads "${GUNICORN_THREADS:-4}" \
  --worker-class "${GUNICORN_WORKER_CLASS:-gthread}"
