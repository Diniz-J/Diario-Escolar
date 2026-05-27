# Scripts de backup do PostgreSQL

Backup e restauração do banco do Diário Escolar em produção (Postgres
rodando via `docker-compose.prod.yml`).

> Pré-requisito: o ambiente de produção do Docker deve estar de pé
> (`docker compose -f docker-compose.prod.yml up -d`) e o `.env.prod`
> preenchido. Os scripts leem `DB_NAME`, `DB_USER`, `DB_PASSWORD` dele.

## Fazer um backup

```bash
./scripts/backup.sh
```

Gera `backups/diario_escolar_AAAA-MM-DD_HHMMSS.dump` (formato custom do
pg_dump, comprimido) e apaga dumps com mais de `RETENTION_DAYS` dias
(padrão 7). A pasta `backups/` não é versionada.

Ajustes por variável de ambiente:

```bash
RETENTION_DAYS=14 BACKUP_DIR=/var/backups/diario ./scripts/backup.sh
```

## Restaurar um backup

```bash
./scripts/restore.sh backups/diario_escolar_2026-05-26_120000.dump
```

Pede confirmação (`CONFIRMA`) porque **sobrescreve** os dados atuais.

## Agendar backup diário (servidor Linux)

Como os scripts rodam via Docker, o agendamento fica no **cron do host**.
Exemplo: backup todo dia às 2h da manhã.

```bash
crontab -e
```

Adicione (ajuste o caminho do projeto):

```cron
0 2 * * * cd /caminho/para/Diario-Escolar && ./scripts/backup.sh >> /var/log/diario-backup.log 2>&1
```

- `0 2 * * *` = 02:00 todos os dias.
- A saída vai pra um log pra você auditar se rodou.

## Recomendações de produção

1. **Teste o restore.** Backup que nunca foi restaurado não é backup. Faça
   um teste de restauração num banco vazio pelo menos uma vez.
2. **Leve os dumps pra fora do servidor.** Um backup no mesmo disco do banco
   não protege contra perda do disco/servidor. Sincronize a pasta `backups/`
   pra um storage externo (S3, Backblaze, rsync pra outra máquina) — pode ser
   uma segunda linha no cron com `aws s3 sync` / `rclone`.
3. **Monitore.** Confira o log periodicamente; um backup que falha calado é
   pior que não ter backup.
