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

## Email de ocorrência (Brevo via HTTP API)

Quando uma ocorrência é criada, o sistema envia um email ao responsável do
aluno. O envio roda em **thread daemon** (fire-and-forget) — a request HTTP
volta na hora; o email é melhor-esforço protegido (falha não trava o
registro). Sem credencial nenhuma, o backend usa o console backend e só
loga o conteúdo do email — útil pra dev local.

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
6. Cada aluno precisa ter **email do responsável** cadastrado (campo
   obrigatório no cadastro). Alunos antigos sem responsável não recebem —
   edite-os pra preencher.

> O envio é em background com `EMAIL_TIMEOUT=10s` por segurança. Se o
> email falhar, o erro vai pro log do Render como
> `Ocorrência N: falha ao enviar email para X.` e a ocorrência fica salva.

### Quando vale SMTP de novo

Se um dia for pra plano pago do Render (`Starter`+, $7/mês), as portas
465/587 voltam a funcionar. Aí dá pra usar Gmail, Resend (com domínio),
Mailgun, etc., via SMTP — mas o caminho via anymail HTTP API continua
funcionando do mesmo jeito, então não há urgência em mudar.

## Quando migrar pra produção de verdade (cliente pagante)

- Postgres pago (Render, ou Neon/Supabase, ou RDS na AWS) — sem expiração.
- Domínio próprio com HTTPS.
- `GUNICORN_WORKERS` maior se o servidor tiver mais RAM/CPU.
- Backup automatizado agendado (ver `scripts/README.md`).
- Cache compartilhado (Redis) se rodar múltiplas réplicas — pro rate limit de
  login ser global.
