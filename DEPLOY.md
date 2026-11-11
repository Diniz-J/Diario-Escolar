# Deploy de demonstração

Guia para subir uma demo grátis: **backend no Render** (web service + Postgres)
e **frontend no Vercel**. O backend roda via Docker (o `Dockerfile` do repo).

> Configuração portável: o app lê a porta de `$PORT` e o banco de
> `DATABASE_URL` — padrões usados por Render, Fly, Railway e AWS. Migrar de
> provedor depois não exige mudar o código, só recriar os serviços.

---

## Parte 1 — Backend no Render

### 1.1. Criar o banco PostgreSQL

1. No painel do Render: **New > PostgreSQL**.
2. Name: `diario-db`. Region: a mais próxima (ex.: Ohio/US East). Plan: **Free**.
3. Create. Aguarde provisionar.
4. Na página do banco, copie a **Internal Database URL** (começa com
   `postgres://...`). É ela que o backend vai usar (conexão interna, mais
   rápida e sem expor o banco na internet).

> O Postgres free do Render expira depois de ~90 dias. Para demo serve; para
> produção do cliente, use um plano pago ou um banco gerenciado externo.

### 1.2. Criar o web service

1. **New > Web Service** > conecte o repositório do GitHub (`Diario-Escolar`).
2. Configurações:
   - **Language/Runtime:** `Docker` (o Render detecta o `Dockerfile`).
   - **Branch:** `main`.
   - **Region:** a MESMA do banco (pra usar a Internal URL).
   - **Plan:** Free.
3. **Pre-Deploy Command** (roda antes de cada deploy, aplica migrations):
   ```
   python manage.py migrate
   ```
4. Não precisa definir Start Command — o `CMD` do Dockerfile já sobe o gunicorn
   escutando em `$PORT`.

### 1.3. Variáveis de ambiente (aba Environment)

Adicione:

| Key | Value |
|---|---|
| `DATABASE_URL` | cole a Internal Database URL do passo 1.1 |
| `SECRET_KEY` | gere uma forte (veja abaixo) |
| `DEBUG` | `False` |
| `SECURE_SSL` | `True` (o Render serve HTTPS) |
| `ALLOWED_HOSTS` | o domínio do serviço, ex.: `diario-backend.onrender.com` |
| `CSRF_TRUSTED_ORIGINS` | `https://diario-backend.onrender.com` |
| `CORS_ALLOWED_ORIGINS` | a URL do frontend no Vercel (preencher depois da Parte 2) |
| `FRONTEND_URL` | a URL do frontend, ex.: `https://diario-escolar.vercel.app` |
| `BACKEND_URL` | a URL deste serviço, ex.: `https://diario-backend.onrender.com` |
| `TAREFAS_TOKEN` | segredo que autoriza o disparo das tarefas periódicas (ver seção própria) |

> **`FRONTEND_URL` não é cosmético.** É a base do link de redefinição de senha
> e do link do convite do portal do responsável — os dois são montados no
> backend e enviados por email. Com ela errada, o pai recebe um convite que
> aponta pro lugar errado, e o erro só aparece do lado de quem clicou.
> `BACKEND_URL` é a base da logo dentro dos emails; errada, o email chega sem
> imagem, o que é cosmético. Os dois têm default apontando pro ambiente de
> demonstração, então **esquecer de setar não quebra o boot** — quebra o link.

Gerar `SECRET_KEY` (rode local):
```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

> O domínio exato (`*.onrender.com`) aparece depois do primeiro deploy. Pode
> criar com um valor provisório e ajustar `ALLOWED_HOSTS`/`CSRF_TRUSTED_ORIGINS`
> assim que souber a URL.

### 1.4. Primeiro deploy e superusuário

1. Salve — o Render builda a imagem e sobe. Acompanhe os logs.
2. Quando estiver "Live", crie o superusuário pelo **Shell** do Render
   (aba Shell do serviço):
   ```
   python manage.py createsuperuser
   ```
3. Teste: `https://<seu-backend>.onrender.com/admin/` deve abrir o admin.

> O serviço free **hiberna** após ~15 min sem acesso; a primeira requisição
> seguinte demora ~30-50s pra acordar.

---

## Parte 2 — Frontend no Vercel

1. No Vercel: **Add New > Project** > importe o mesmo repositório.
2. Configurações:
   - **Root Directory:** `frontend`.
   - **Framework Preset:** Vite (deve detectar sozinho).
   - **Build Command:** `npm run build` (padrão).
   - **Output Directory:** `dist` (padrão).
3. **Environment Variables:**
   | Key | Value |
   |---|---|
   | `VITE_API_URL` | `https://<seu-backend>.onrender.com/api/v1` |
4. Deploy. A URL final será algo como `https://diario-escolar.vercel.app`.

O `frontend/vercel.json` já cuida do roteamento de SPA (refresh em rotas como
`/presenca/3` não dá 404).

---

## Parte 3 — Ligar os dois (CORS)

Depois que o frontend tiver URL no Vercel:

1. Volte ao Render > backend > Environment.
2. Ajuste `CORS_ALLOWED_ORIGINS` para a URL do Vercel, ex.:
   `https://diario-escolar.vercel.app`
3. Salve — o Render redeploya. Pronto: o front conversa com o back.

---

## Checklist final

- [ ] `/admin/` do backend abre e loga com o superusuário.
- [ ] O frontend no Vercel carrega a tela de login.
- [ ] Login no frontend funciona (token vem do backend).
- [ ] Criar/listar dados funciona (CORS ok).
- [ ] `GET /api/v1/health/` responde `200` (o banco está de pé).
- [ ] `FRONTEND_URL` aponta pro frontend certo — é a base dos links de email.
- [ ] Um reset de senha chega na caixa de entrada e o link abre a tela certa.

Depois do básico, por frente (cada uma tem seção própria abaixo):

- [ ] Email saindo pelo Brevo (`EMAIL_BACKEND` + `ANYMAIL_BREVO_API_KEY` + `DEFAULT_FROM_EMAIL`).
- [ ] `SENTRY_DSN` no Render e `VITE_SENTRY_DSN` no Vercel.
- [ ] `TAREFAS_TOKEN` no servidor e os dois secrets do workflow no GitHub.
- [ ] Envs do Asaas e webhook cadastrado, **se** a escola for cobrar online.
- [ ] Contas do portal semeadas e o primeiro convite mandado pra você mesmo.

## Email transacional (Brevo via HTTP API)

Cinco coisas saem por email, e todas pelo mesmo backend:

| O quê | Quando |
|---|---|
| Ocorrência | na criação, aos responsáveis do aluno (thread daemon) |
| Comunicado | no disparo explícito, em lote (ver seção seguinte) |
| Redefinição de senha | pedido do próprio usuário, ou disparado pela direção |
| Convite do portal | pela tela `/responsaveis` ou pelo command de lote |
| Pagamento recebido | quando o webhook do gateway concilia a fatura |

O envio roda em **thread daemon** (fire-and-forget): a request HTTP volta na
hora e o email é melhor-esforço protegido por `try/except` — falha de envio
não trava o registro.

**Mas falha não se perde mais.** Quatro desses caminhos (ocorrência,
pagamento, convite do portal e link de senha) gravam uma `Mensagem` em
`apps/notificacoes` **antes** de tentar enviar, e carimbam o resultado
depois. É essa ordem que faz o rastro sobreviver ao processo que morre no
meio — rotina no free tier. O que falhou volta pela tarefa `email`, abaixo,
ou pelo `manage.py notificacoes_reenviar`.

Duas coisas que o outbox **não** cobre, de propósito: o comunicado em lote,
que tem outbox próprio (`ComunicadoDestinatario`) e retomada própria; e o
reenvio do que carrega token — convite e link de senha ficam gravados, mas
não são retentados, porque o token já foi invalidado ou já expirou e o
reenvio entregaria um link morto.

Sem credencial nenhuma, o backend usa o console backend e só loga o conteúdo
do email — útil pra dev local.

### Por que Brevo (e não SMTP)?

O free tier do Render **bloqueia outbound SMTP** nas portas 25/465/587
desde setembro de 2025. Qualquer tentativa com Gmail/SendGrid/Mailgun via
SMTP retorna `Network is unreachable`. A saída é usar HTTP API (porta
443, sempre liberada) — `django-anymail` faz essa ponte mantendo o
`send_mail` do Django igual no código.

Por que Brevo (ex-Sendinblue):

- 300 emails/dia grátis pra sempre.
- **Não exige domínio próprio** — basta verificar um endereço de email
  como remetente (ex.: o próprio Gmail pessoal).
- API key é tudo que precisa.

Se um dia quiser trocar pra SendGrid/Mailgun/Postmark, é só mudar a env
`EMAIL_BACKEND` pro backend correspondente do anymail e a chave — o
código de envio não muda.

### Setup passo-a-passo

1. Crie conta em **brevo.com** com o email que vai ser o remetente.
2. Confirme o email (link enviado pelo Brevo).
3. **Senders, Domains & Dedicated IPs → Senders**: clica **Add a sender**,
   preenche nome + email, confirma pelo link que chega.
4. **SMTP & API → API Keys**: clica **Generate a new API key**, dá um nome
   (ex.: `Diário Escolar`) e copia o valor (`xkeysib-...`). **Não dá pra
   ver de novo depois**; se perder, gere outra.
5. No Render, defina/atualize as envs:
   ```
   EMAIL_BACKEND=anymail.backends.brevo.EmailBackend
   ANYMAIL_BREVO_API_KEY=xkeysib-<sua chave>
   DEFAULT_FROM_EMAIL=Diário Escolar <seu-email-verificado@gmail.com>
   ```
   Pode remover as envs antigas de SMTP (`EMAIL_HOST`, `EMAIL_PORT`,
   `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS`) — anymail
   ignora.
6. O destino do email é o **vínculo** `ResponsavelAluno`, não o campo de
   texto do aluno: um aluno com mãe e pai vinculados gera **duas mensagens
   individuais**, cada uma saudada pelo nome de quem recebe, e a falha de uma
   não cala a outra. O `Aluno.email_responsavel` é fallback, e dispara por
   **ausência de vínculo**, nunca por ausência de destino — se disparasse por
   falta de destino, o opt-out (`Responsavel.recebe_notificacao`) viraria
   nada. Ver [`RESPONSAVEIS.md`](./RESPONSAVEIS.md) §4.1. Aluno sem nenhum
   dos dois não recebe, e isso fica como aviso no log.

> O envio é em background com `EMAIL_TIMEOUT=10s` por segurança. Se o
> email falhar, o erro vai pro log do Render como
> `Ocorrência N: falha ao enviar email para X.` e a ocorrência fica salva.

### Quando vale SMTP de novo

Se um dia for pra plano pago do Render (`Starter`+, $7/mês), as portas
465/587 voltam a funcionar. Aí dá pra usar Gmail, Resend (com domínio),
Mailgun, etc., via SMTP — mas o caminho via anymail HTTP API continua
funcionando do mesmo jeito, então não há urgência em mudar.

## Comunicados: retomar lote interrompido

Os comunicados (avisos aos responsáveis) são enviados em lote por uma
**thread daemon**, e thread daemon morre junto com o processo. No Render,
deploy e restart de container são rotina — então um lote grande pode ser
cortado no meio: parte dos responsáveis recebe, o resto fica `pendente` e
o comunicado fica parado em `enviando`.

Para retomar (não reenvia para quem já recebeu — só pega as linhas
`pendente`):

```bash
# no Shell do Render, ou local com DATABASE_URL apontando pra prod
python manage.py comunicados_retomar            # parados há 15min+
python manage.py comunicados_retomar --dry-run  # só lista
python manage.py comunicados_retomar --id 42    # um específico
```

O disparo carimba sinal de vida a cada 25 emails, então um lote saudável
nunca é confundido com um travado. Sem nada travado o comando não faz
nada, o que o torna seguro de agendar. A tarefa `comunicados` do workflow
é exatamente isso, mas a agenda dela está **desligada** por ora (ver a
seção seguinte), então hoje a retomada é manual.

Para saber quem recebeu, a página do comunicado tem o log de entrega por
aluno (enviado / falhou / sem email cadastrado), com a mensagem de erro do
provedor em cada falha — é ali que a cota estourada do Brevo aparece.

## Financeiro: cobrança online (gateway Asaas)

O módulo financeiro **funciona sem gateway**: a escola cadastra o plano de
cada aluno, as faturas são geradas, e a secretaria registra o Pix que caiu na
conta ou o dinheiro que entrou no balcão. É assim que ele opera hoje, em todo
ambiente. A cobrança online é integração, não dependência.

Pra ligar a emissão de boleto/Pix, quatro envs no Render — todas opcionais:

| Key | Value |
|---|---|
| `ASAAS_API_KEY` | chave da API do Asaas. Sem ela, a tela mostra "cobrança online não está configurada" e o resto do módulo segue igual |
| `ASAAS_BASE_URL` | `https://api-sandbox.asaas.com/v3` (default) ou a de produção |
| `ASAAS_TIMEOUT` | segundos; default `10`, curto porque a emissão roda dentro de uma request da secretaria |
| `ASAAS_WEBHOOK_TOKEN` | o `authToken` do cadastro do hook no painel deles |

> **Chave e ambiente andam juntos.** Chave de sandbox com a URL de produção
> (ou o contrário) devolve 401 `invalid_environment`. E `ASAAS_WEBHOOK_TOKEN`
> **não é** a API key: é um segredo separado, que você escolhe ao cadastrar o
> webhook — a documentação deles é explícita nisso.

Depois das envs, cadastre o webhook no painel do Asaas apontando pra:

```
POST https://<seu-backend>/api/v1/financeiro/webhooks/asaas/
```

com o mesmo `authToken` que entrou em `ASAAS_WEBHOOK_TOKEN`. É a **única
rota sem autenticação do projeto**: o token é comparado com
`compare_digest`, o evento é gravado antes de ser processado, e o valor é
**reconsultado no provedor antes de qualquer escrita de dinheiro** — o token
prova quem mandou, não quanto entrou.

O endpoint responde **200 mesmo quando o processamento falha**, de propósito:
15 falhas consecutivas pausam a fila de entrega do Asaas, e uma fila pausada
para a conciliação da escola inteira. O que falhou fica registrado no
`EventoWebhook` e no Sentry.

## Tarefas periódicas (quem dispara os commands)

O projeto **não tinha agendador em ambiente nenhum** — por isso
`comunicados_retomar` e os três commands do financeiro existiam sem nunca
rodar. Quem dispara hoje é um workflow agendado no GitHub Actions
(`.github/workflows/tarefas.yml`), que faz uma chamada HTTP autenticada
pra `POST /api/v1/tarefas/executar/?tarefas=<apelidos>`.

Por que Actions e não cron no Render: é gratuito, não entra provedor novo,
o repo já usa Actions, e a chamada ainda **acorda o serviço que hiberna**
no free tier. E o workflow **não** tem acesso ao banco: rodar `manage.py`
de lá exigiria o `DATABASE_URL` de produção nos secrets do GitHub, o que
poria o CI alcançando o banco da escola — bem pior que uma rota com token.

### Ligar (três valores)

1. No servidor, defina a env `TAREFAS_TOKEN` com um segredo forte:
   ```bash
   python -c "import secrets; print(secrets.token_urlsafe(32))"
   ```
   Com ela vazia a rota **recusa tudo** — é o default, e é o estado certo
   pra quem clonou o projeto.
2. No GitHub, em **Settings → Secrets and variables → Actions**, crie:
   - `BACKEND_URL` — raiz do backend, **sem barra no fim**.
   - `TAREFAS_TOKEN` — exatamente o mesmo valor do passo 1.

Sem os dois secrets o job termina avisando em vez de falhar vermelho,
porque repo clonado sem secrets é o estado normal. O custo disso é que **o
silêncio não aparece como vermelho**: se a mensalidade não for gerada no
dia 1, confira primeiro se os secrets existem.

### O que roda, e quando

| Agenda (UTC) | Apelidos | O que faz |
|---|---|---|
| `11 7 * * *` | `vencidas,tokens` | marca fatura vencida e limpa token de redefinição expirado |
| `11 6 1 * *` | `faturas` | gera as faturas da competência |
| `41 6 1 * *` | `cobrancas` | emite as cobranças no gateway, meia hora depois |
| ~~`3,18,33,48 * * * *`~~ | `email,comunicados` | **desligada** — reenvio do outbox e retomada de comunicado |

**A agenda de 15 minutos está comentada** (nov/2026). Enquanto os secrets
não existem o job sai limpo sem fazer nada, e naquela cadência eram ~96
execuções verdes por dia enchendo a aba Actions — barato, mas soterra
falha de CI de verdade no meio da lista. Religar é descomentar uma linha
no workflow; o `case` do job já mapeia essa agenda, então não há segundo
lugar pra mexer.

O que ela fazia sai pelo disparo manual (**Run workflow**, que já vem com
`email,comunicados`) ou pelo command direto. Isso **não** atrasa email: o
envio é inline no momento do evento, e essa tarefa só retenta o que
falhou — que fica gravado na `Mensagem` de qualquer jeito.

**Os minutos são quebrados de propósito.** O GitHub avisa que workflow
agendado na virada da hora atrasa sob carga da plataforma, e é nela que
todo mundo agenda. A intenção é a mesma que o `FINANCEIRO.md` §2.2
registrava pra um crontab comum: dia 1 de manhã, emissão meia hora depois
da geração.

A emissão é entrada **separada** da geração porque `gerar_faturas` roda em
transação e em lote: pendurar N chamadas HTTP ali prenderia o lock das
faturas pelo tempo do provedor.

Pra disparar à mão, a aba Actions tem **Run workflow** com o campo de
apelidos (`workflow_dispatch`). O parâmetro `?tarefas=` é obrigatório na
rota — com o financeiro na lista, um disparo sem recorte explícito seria
fácil de errar.

### Num servidor com crontab próprio

Quando o backend sair do Render pra um VPS, as mesmas tarefas viram linhas
de crontab chamando o command direto, e o workflow pode ser desligado:

```cron
*/15 * * * * cd /app && python manage.py notificacoes_reenviar
*/15 * * * * cd /app && python manage.py comunicados_retomar
0 4 * * *    cd /app && python manage.py financeiro_marcar_vencidas
0 4 * * 0    cd /app && python manage.py purge_expired_tokens
0 6 1 * *    cd /app && python manage.py financeiro_gerar_faturas
30 6 1 * *   cd /app && python manage.py financeiro_emitir_cobrancas
```

Todos são idempotentes e seguros de repetir. Os do financeiro aceitam
`--escola-id`, e a geração e a emissão aceitam `--competencia YYYY-MM` e
`--dry-run`.

## Portal do responsável: primeiro convite

A conta do responsável **só existe por convite da escola** — não há
auto-registro. Depois do deploy:

1. Confira que `FRONTEND_URL` aponta pro frontend certo: é a base do link
   que vai no email.
2. Semeie as contas a partir dos alunos que já têm email de responsável
   cadastrado (idempotente, deduplica irmãos pelo email, inclui aluno
   inativo, pula aluno sem email):
   ```bash
   python manage.py portal_semear_responsaveis --dry-run
   python manage.py portal_semear_responsaveis
   ```
   A conta nasce **sem senha utilizável**: o acesso vem do convite.
3. Convide pela tela `/responsaveis` (botão Convidar, um a um) ou em lote:
   ```bash
   python manage.py portal_convidar_responsaveis --dry-run
   python manage.py portal_convidar_responsaveis --limite 50
   ```
   O `--limite` existe porque a cota de 300 emails/dia do Brevo é
   **compartilhada** com os comunicados e as ocorrências: convidar a escola
   toda num dia pode consumir a cota e calar os avisos.

> Mande o primeiro convite **pra você mesmo**, como conta de teste, antes de
> mandar pra uma família.

## Observabilidade (Sentry)

Os logs do Render somem quando o serviço hiberna no free tier — então
quando algo quebra em produção a gente perde o stack trace antes de
conseguir ler. Sentry resolve isso: captura cada exceção não tratada,
cada erro 500 e cada `logger.error()`/`logger.exception()` do app
(inclusive o que rola no envio assíncrono de email), persiste do lado
deles e ainda manda email/Slack quando aparece coisa nova.

O free tier do Sentry (Developer) aceita 5k events/mês — bem mais do
que um app de 1 escola gera. Não cobra mesmo se passar do limite: ele
só para de aceitar até o reset do mês.

### Setup passo-a-passo

1. Crie conta em **sentry.io**.
2. **Create Project → Django**, dê um nome (ex.: `diario-escolar-backend`).
   Sentry mostra o **DSN** (link `https://xxxxx@oNNN.ingest.sentry.io/NNN`).
   Copie.
3. No Render, adicione as envs:
   ```
   SENTRY_DSN=https://xxxxx@oNNN.ingest.sentry.io/NNN
   SENTRY_ENVIRONMENT=production
   ```
   Salva → o serviço redeploya com o SDK ativo.
4. **Create Project → React** (outro projeto, dentro da mesma org).
   Pegue o DSN dele (separado do backend, pra você filtrar erros front
   vs back nos painéis).
5. No Vercel, adicione as envs (scope: **Production**):
   ```
   VITE_SENTRY_DSN=<dsn do projeto React>
   VITE_SENTRY_ENVIRONMENT=production
   ```
   Force um redeploy (envs `VITE_*` são build-time — não pegam só com
   salvar; precisa de novo build).

### Teste de fumaça

Após o redeploy, dispare um erro 500 proposital pra confirmar que o
SDK está capturando: bata em qualquer endpoint inexistente com path
mal-formado ou crie uma view temporária com `raise Exception("test")`.
Em ~10s o evento aparece no painel do Sentry. Apague a view depois.

> Sem `SENTRY_DSN` no Render (ou `VITE_SENTRY_DSN` no Vercel), o SDK
> fica inerte — dev local funciona normal sem precisar de chave.

## Quando migrar pra produção de verdade (cliente pagante)

- Postgres pago (Render, ou Neon/Supabase, ou RDS na AWS) — sem expiração.
- Domínio próprio com HTTPS.
- `GUNICORN_WORKERS` maior se o servidor tiver mais RAM/CPU.
- Backup automatizado agendado (ver `scripts/README.md`).
- Cache compartilhado (Redis) se rodar múltiplas réplicas — pro rate limit de
  login ser global.
- **Passar as tarefas periódicas pro crontab do sistema** (seção acima) e
  desligar o workflow do Actions — some a dependência do GitHub pra que a
  mensalidade seja gerada, e o disparo deixa de passar por uma rota pública
  com token.
- Rotacionar `SECRET_KEY` e a senha do banco ao nascer o ambiente novo —
  trocar segredo é barato no dia zero e caro depois, com sessão de gente
  dentro.
- Fila de broker (Celery/Dramatiq/RQ) **se** o volume justificar: hoje o
  outbox cobre retry e histórico sem Redis nem segundo processo, que é o que
  o free tier não dá. O que a fila resolveria e o outbox não é tirar o PDF
  do WeasyPrint de dentro da request.
