# Diário Escolar

Aplicação web para registro escolar — gestão disciplinar (ocorrências, com notificação por email ao responsável), presença, tarefas, planos de ensino, boletim e cadastros (alunos, turmas, disciplinas, professores).

Monorepo:

- **Backend** — Django 5.2 + Django REST Framework, autenticação JWT, PostgreSQL.
- **Frontend** — React 19 + Vite + TypeScript, Tailwind 4 + shadcn/ui, TanStack Query.

Arquitetura single-tenant com base abstrata desenhada para escalar a row-level multi-tenancy (SaaS) sem retrofit doloroso.

**Status:** publicado em ambiente de demonstração — backend (Docker) no Render, frontend no Vercel, Postgres gerenciado. Dockerizado, com CI (GitHub Actions), backup do banco e deploy reproduzível. Ver [`DEPLOY.md`](./DEPLOY.md).

---

## Stack

### Backend

| Camada | Tecnologia |
|---|---|
| Framework | Django 5.2 + Django REST Framework |
| Banco de dados | PostgreSQL (driver `psycopg` 3) |
| Autenticação | SimpleJWT (Bearer token, claims customizados) |
| Filtros | django-filter |
| Configuração | python-decouple (`.env`) |
| CORS | django-cors-headers |

### Frontend

| Camada | Tecnologia |
|---|---|
| Build / dev server | Vite 8 |
| Framework | React 19 |
| Linguagem | TypeScript 6 |
| Estilo | Tailwind CSS 4 + shadcn/ui (preset radix-nova) |
| Roteamento | React Router 7 |
| Estado de servidor | TanStack Query 5 |
| HTTP | axios (com interceptors de Bearer + refresh) |
| Notificações | sonner |

---

## Estrutura do projeto

```
Diario-Escolar/
├── config/                  — settings, urls, wsgi, asgi do Django
├── apps/
│   ├── common/              — base abstrata, validators, permissões, mixins reutilizáveis
│   ├── accounts/            — Usuario (AbstractUser) + perfis + JWT customizado
│   ├── escola/              — Escola, Turma, Disciplina, Aluno, Professor, Lecionamento
│   ├── ocorrencias/         — Ocorrencia + services.py (email ao responsável)
│   ├── presenca/            — RegistroPresenca + ItemPresenca
│   ├── tarefas/             — Tarefa + EntregaTarefa
│   ├── planos_ensino/       — PlanoEnsino
│   └── boletins/            — agregação on-the-fly (sem modelo; services.py)
├── frontend/                — app React (Vite + TypeScript)
│   ├── src/
│   │   ├── components/      — AppLayout (sidebar + drawer mobile), ProtectedRoute, ui/* (shadcn)
│   │   ├── features/        — domínio por pasta: auth, alunos, turmas, escolas,
│   │   │                     professores, lecionamentos, disciplinas, dashboard,
│   │   │                     ocorrencias, presenca, tarefas, planos-ensino,
│   │   │                     boletins, usuarios
│   │   ├── lib/             — api (axios + interceptors), queryClient, utils
│   │   ├── pages/           — Login, Dashboard, Alunos, Turmas (+ detalhe),
│   │   │                     Disciplinas, Professores, PlanosEnsino (+ detalhe),
│   │   │                     Ocorrencias (+ detalhe), Presenca (+ detalhe),
│   │   │                     Tarefas (+ detalhe), Boletim, 404
│   │   ├── routes.tsx       — mapa central de rotas
│   │   ├── types/api.ts     — interfaces que casam com os serializers do backend
│   │   ├── App.tsx          — providers globais (Query, Auth, Toaster)
│   │   └── main.tsx         — entry point + BrowserRouter
│   ├── Dockerfile           — build do front (Node) → nginx
│   ├── nginx.conf           — serve o SPA + proxy /api, /admin, /static
│   ├── vercel.json          — rewrite de SPA (deploy no Vercel)
│   ├── components.json      — config do shadcn/ui CLI
│   ├── package.json
│   └── vite.config.ts
├── .github/workflows/ci.yml — CI: testes do backend + build do frontend
├── scripts/                 — backup.sh / restore.sh do Postgres + README
├── Dockerfile               — backend multi-stage (dev/prod), gunicorn
├── entrypoint.sh            — prod: migrate + superusuário no boot, depois gunicorn
├── docker-compose.yml       — ambiente de desenvolvimento (hot reload)
├── docker-compose.prod.yml  — ambiente de produção (gunicorn + nginx)
├── DEPLOY.md                — guia de deploy (Render + Vercel) + Resend
├── CLAUDE.md                — guia pra agentes de IA (guardrails + mapa + roadmap)
├── manage.py
├── requirements.txt
├── .env.example
└── .env.prod.example        — modelo do env de produção
```

---

## Backend

### Modelo de permissões

Quatro classes granulares em `apps/common/permissions.py`, combinadas por ViewSet:

| Classe | Acesso |
|---|---|
| `IsAdmin` | Superuser Django ou `perfil=admin` |
| `IsAdminOrDiretor` | Admin + `perfil=diretor` |
| `IsAdminOrDiretorOrProfessor` | Admin + diretor + `perfil=professor` |
| `IsAdminOrDiretorOrProfessorOrInspetor` | Acima + `perfil=inspetor` (leitura em domínios de monitoramento) |

`ReadWritePermissionMixin` (em `apps/common/views.py`) padroniza separação read/write por ação: `list`/`retrieve` usam `READ_PERMISSION`; o restante usa `WRITE_PERMISSION`. Apps com regra uniforme (ex.: `ocorrencias`) declaram `permission_classes` direto.

Por padrão, **escrita em cadastros** (Aluno, Turma, Disciplina, Professor, Lecionamento) é restrita a admin/diretor — professor tem leitura mas não cria/edita/exclui. O frontend espelha isso via hook `usePermissoes` (esconde botões "Novo/Editar/Excluir" pra perfil professor), evitando 403 visível.

Todos os querysets são escopados à `escola` do usuário autenticado via `EscopoEscolaMixin`. Defesa contra IDOR na escrita: serializers de `ocorrencias` e `presenca` recusam payload com `escola` divergente da do usuário (admin/superuser bypassam).

### Multi-tenancy

Single-tenant hoje. A base abstrata `BaseModelEscopado` (FK `escola` + timestamps em todos os modelos de domínio) foi desenhada para ativar row-level tenancy sem refatoração quando o sistema escalar para SaaS.

### Autenticação JWT

Endpoints de autenticação:

- `POST /api/v1/auth/token/` — troca username/password por par `access` + `refresh`. **Rate limit de 5/min por IP** (anti-brute-force, via `ScopedRateThrottle`).
- `POST /api/v1/auth/token/refresh/` — gera novo `access` a partir de um `refresh` válido (rotação ativada: emite refresh novo e blacklista o anterior).
- `POST /api/v1/auth/logout/` — invalida (blacklist) o refresh enviado. Logout efetivo.

O `access` carrega claims customizados para o frontend ler sem requests extras:

- `escola_id`, `perfil` — escopo de tenancy e perfil de acesso.
- `username`, `first_name`, `last_name` — identificação humana (saudação na UI).

`ROTATE_REFRESH_TOKENS` + `BLACKLIST_AFTER_ROTATION` (app `token_blacklist`) reduzem a janela de um refresh roubado. A staleness de claims (se admin troca escola/perfil) ainda dura até o `REFRESH_TOKEN_LIFETIME` (7 dias), pois o refresh propaga claims pro novo access.

### Apps do backend

Cada app de domínio segue o mesmo layout (`models.py`, `serializers.py`, `views.py`, `urls.py`, `admin.py`, `migrations/`, `tests/`). `repositories.py` e `services.py` estão planejados (no backlog).

**`apps/common`**
- `TimeStampedModel` — `criado_em` / `atualizado_em` automáticos.
- `BaseModelEscopado` — base abstrata com FK `escola`.
- `EscopoEscolaMixin` — filtra queryset pela escola do usuário.
- `ReadWritePermissionMixin` — padroniza permissão por ação.
- Validator de CNPJ com dígito verificador.

**`apps/accounts`**
- `Usuario` estendendo `AbstractUser` com `perfil` (admin/diretor/professor/secretaria/inspetor) + FK opcional para `Escola`.
- CRUD via `/api/v1/usuarios/` (admin e diretor). O serializer expõe `escola` (necessário para o frontend criar Professor com escola alinhada).
- `UsuarioTokenObtainPairView` + `UsuarioTokenObtainPairSerializer` injetando os claims customizados.

**`apps/escola`**
- `Escola` — tenant root; CNPJ validado; remoção protegida.
- `Turma` — turno + ano letivo; única por `(escola, nome, ano_letivo)`.
- `Disciplina` — única por `(escola, nome)`; campo `ativa`. Migration semeia 14 disciplinas BNCC comuns por escola (idempotente via `get_or_create`).
- `Aluno` — não loga; identificado por matrícula única por escola; invariante turma/escola validada. Tem `nome_responsavel` + `email_responsavel` (obrigatórios no cadastro via serializer; `blank` no banco pra não quebrar alunos antigos) — usados pra notificar o responsável de ocorrências. **`DELETE` faz soft delete** (marca `ativo=False`) para preservar histórico de ocorrências/presença.
- `Professor` — OneToOne com `Usuario` (`perfil=professor`); campo `ativo`; invariante `usuario.escola == professor.escola`. **`DELETE` faz soft delete** (`ativo=False`).
- `Lecionamento` — vínculo granular **professor × turma × disciplina** (substituiu a antiga M2M `Professor.disciplinas`). Permite responder "quais turmas o prof X dá?" e "quem leciona Mat no 1º A?". `ano_letivo` derivado da turma; unique `(professor, turma, disciplina)`; `clean()` valida escola alinhada nos três.
- CRUD completo para todos via API, filtros declarativos + busca por nome/matrícula.

**`apps/tarefas`**
- `Tarefa` — turma + disciplina + professor + título + descrição + `data_lancamento` + `prazo` opcional + `vale_nota` + `nota_maxima` + `peso`.
- `EntregaTarefa` — `entregue` + `data_entrega` + `nota` + `observacao` por aluno.
- Status calculado server-side (pendente/atrasada/entregue). Leitura inclui inspetor; escrita admin/diretor/professor.

**`apps/planos_ensino`**
- `PlanoEnsino` — ementa, conteúdo programático, objetivos gerais/específicos, habilidades BNCC, carga horária, metodologia, recursos, avaliação, `ativo`. Único por `(escola, turma, disciplina, ano_letivo)` com invariantes cruzadas. Casca criada num dialog enxuto; campos longos preenchidos na tela de detalhe.

**`apps/boletins`**
- Sem modelo próprio. `services.py` agrega frequência + notas + ocorrências on-the-fly; `BoletimAlunoView` (APIView) expõe `GET /boletins/aluno/<id>/`. Justificado (J) conta como presença efetiva no cálculo de frequência.

**`apps/ocorrencias`**
- `Ocorrencia` — turma + aluno + professor opcional + descrição + data + status (`aberta`/`em_andamento`/`resolvida`/`arquivada`).
- Invariantes em `clean()` e serializer: `aluno.escola == escola`, `aluno.turma == turma` (snapshot atual), `professor.escola == escola`, `data <= hoje`.
- Permissão uniforme `admin/diretor/professor` — colegas auxiliam a resolver registros uns dos outros.
- Guard de IDOR no payload `escola`.
- **Notificação por email** (`services.py`): ao criar uma ocorrência (`perform_create`), envia email ao `email_responsavel` do aluno com os dados. Síncrono e protegido (try/except) — se o email falhar, a ocorrência é salva mesmo assim; aluno sem responsável é pulado (log). Provedor: SMTP via env (Resend em produção) — ver `DEPLOY.md`.

**`apps/presenca`**
- `RegistroPresenca` — chamada de uma turma num dia; única por `(escola, turma, data)`; `professor` opcional.
- `ItemPresenca` — status individual por aluno (`P`/`A`/`J`/`R`: presente, ausente, justificado, retardatário). `CASCADE` no `registro` (único cascade do projeto).
- Auto-geração: criar `RegistroPresenca` gera `ItemPresenca(status=P)` para cada aluno ativo da turma em transação atômica.
- `ItemPresenca.save()` força `escola_id = registro.escola_id` (coerência defensiva).
- `ItemPresencaViewSet` não expõe POST/DELETE — ciclo de vida pertence ao registro pai.
- Leitura inclui inspetor; escrita admin/diretor/professor.

### Endpoints

```
POST   /api/v1/auth/token/          — obter JWT (access + refresh); rate limit 5/min
POST   /api/v1/auth/token/refresh/  — renovar JWT (rotaciona o refresh)
POST   /api/v1/auth/logout/         — blacklist do refresh (logout efetivo)

GET|POST        /api/v1/usuarios/
GET|PUT|PATCH|DELETE /api/v1/usuarios/{id}/

GET|POST        /api/v1/escolas/
GET|PUT|PATCH|DELETE /api/v1/escolas/{id}/

GET|POST        /api/v1/turmas/
GET|PUT|PATCH|DELETE /api/v1/turmas/{id}/

GET|POST        /api/v1/disciplinas/
GET|PUT|PATCH|DELETE /api/v1/disciplinas/{id}/

GET|POST        /api/v1/alunos/                          (DELETE faz soft delete)
GET|PUT|PATCH|DELETE /api/v1/alunos/{id}/

GET|POST        /api/v1/professores/                     (DELETE faz soft delete)
GET|PUT|PATCH|DELETE /api/v1/professores/{id}/

GET|POST        /api/v1/lecionamentos/
GET|PUT|PATCH|DELETE /api/v1/lecionamentos/{id}/

GET|POST        /api/v1/ocorrencias/
GET|PUT|PATCH|DELETE /api/v1/ocorrencias/{id}/

GET|POST        /api/v1/planos-ensino/
GET|PUT|PATCH|DELETE /api/v1/planos-ensino/{id}/

GET|POST        /api/v1/registros-presenca/
GET|PUT|PATCH|DELETE /api/v1/registros-presenca/{id}/

GET             /api/v1/itens-presenca/
GET|PATCH|PUT   /api/v1/itens-presenca/{id}/

GET|POST        /api/v1/tarefas/
GET|PUT|PATCH|DELETE /api/v1/tarefas/{id}/

GET|POST        /api/v1/entregas-tarefa/
GET|PUT|PATCH|DELETE /api/v1/entregas-tarefa/{id}/

GET             /api/v1/boletins/aluno/{aluno_id}/        (agregação read-only)
```

> Todos os endpoints (exceto `/auth/token/` e `/auth/token/refresh/`) exigem `Authorization: Bearer <access_token>`. O queryset retornado é sempre escopado à escola do usuário autenticado.

---

## Frontend

Single-Page Application em React 19 + TypeScript que consome a API REST do backend. Roda em `http://localhost:5173/` em desenvolvimento.

### Páginas

| Rota | Descrição |
|---|---|
| `/login` | Autenticação contra `/auth/token/` |
| `/dashboard` | Saudação personalizada + filtro por turma + cards de métricas (ocorrências em aberto, alunos ativos, última chamada por turma, últimas ocorrências). Cada card é clicável |
| `/alunos` | CRUD de alunos com busca por nome/matrícula; linha clicável abre o boletim |
| `/turmas` | CRUD de turmas com contagem de alunos por turma |
| `/turmas/:id` | Detalhe da turma com lista de alunos vinculados |
| `/disciplinas` | CRUD de disciplinas |
| `/professores` | CRUD de professores (cria Usuario + Professor + Lecionamentos); soft delete; badges de turmas e disciplinas |
| `/planos-ensino` | Lista de planos com status (preenchido/em branco/inativo) |
| `/planos-ensino/:id` | Editor longo em seções (Programação / Execução / Situação) |
| `/ocorrencias` | Lista ordenada por status (abertas → arquivadas) + data desc; filtro por status |
| `/ocorrencias/:id` | Detalhe com botões rápidos de mudança de status; editar/excluir num dropdown discreto |
| `/presenca` | Lista de chamadas por turma e data |
| `/presenca/:id` | Tela da chamada com resumo P/A/J/R e edição inline por aluno (optimistic update) |
| `/tarefas` | Lista de tarefas com busca |
| `/tarefas/:id` | Detalhe com resumo de entregas e marcação por aluno |
| `/boletim/:alunoId` | Boletim agregado do aluno (frequência + notas + ocorrências) com layout de impressão |

Botões de criação/edição/exclusão em cadastros (Alunos, Turmas, Disciplinas, Professores) só aparecem para admin/diretor — controlado por `usePermissoes`.

### Camadas

- **`features/auth`** — `AuthProvider` com login/logout, decode do JWT (jwt-decode), tokenStorage em `localStorage`, `useAuth` hook.
- **`lib/api.ts`** — instância única do axios. Request interceptor injeta `Authorization: Bearer`. Response interceptor detecta 401 → chama `/auth/token/refresh/` → refaz request original (com promise compartilhada para evitar thundering herd em queries paralelas).
- **`lib/queryClient.ts`** — TanStack Query configurado com `staleTime` 30s, retry desabilitado pra 401/403.
- **`features/<dominio>/hooks.ts`** — `useXxx`, `useCreate`, `useUpdate`, `useDelete` com invalidação automática de cache + toasts via sonner.
- **`components/ui/`** — código copiado pelo shadcn CLI (Button, Input, Card, Dialog, Table, Select, DropdownMenu, Sonner, AlertDialog, etc.). Editável livremente.

### Tema e responsividade

Dark mode permanente (`<html class="dark">`), com paleta um pouco mais clara que o default do shadcn-nova. Toggle de light/dark não exposto (decisão de UI).

Layout responsivo: a sidebar fixa (≥768px) vira um drawer (`Sheet`) com botão hamburguer abaixo de 768px. Padding e tipografia ajustam por breakpoint (`p-4 md:p-8`, `text-2xl md:text-3xl`). Tabelas escondem colunas secundárias em telas estreitas (`hidden sm:table-cell` / `md:` / `lg:`) em vez de scroll horizontal — os dados completos ficam acessíveis clicando na linha (vai pro detalhe). Funciona em celular (chamada de presença em sala) e tablet.

---

## Setup local

**Requisitos:** Python 3.12+, PostgreSQL 15+, Node.js 22+ (ou via Docker), npm 11+.

### Backend

```bash
# 1. ambiente virtual
python -m venv .venv
.venv\Scripts\activate        # Windows PowerShell
# source .venv/bin/activate   # Linux / macOS

# 2. dependências
pip install -r requirements.txt

# 3. variáveis de ambiente
copy .env.example .env
# editar .env (DB_*, SECRET_KEY, CORS_ALLOWED_ORIGINS=http://localhost:5173)

# 4. criar o banco (no PostgreSQL)
# CREATE DATABASE diario_escolar;

# 5. aplicar migrations
python manage.py migrate

# 6. criar superusuário
python manage.py createsuperuser

# 7. rodar o servidor (porta 8000)
python manage.py runserver
```

### Frontend

```bash
cd frontend

# 1. dependências
npm install

# 2. variáveis de ambiente
copy .env.example .env
# default já aponta pra VITE_API_URL=http://localhost:8000/api/v1

# 3. servidor de desenvolvimento (porta 5173)
npm run dev
```

Para build de produção: `npm run build` (saída em `frontend/dist/`).

> O backend precisa estar com `CORS_ALLOWED_ORIGINS=http://localhost:5173` no `.env` para o frontend conseguir autenticar.

---

## Fluxo de desenvolvimento

```
feature/* → develop → main
```

- Todo desenvolvimento começa em `feature/<nome>` (ou `docs/`, `chore/`, etc.).
- PR obrigatório para `develop`. Quando `develop` está estável, PR `develop → main`.
- Antes de abrir PR backend: `python manage.py check && python manage.py test`.
- Antes de abrir PR frontend: `npm --prefix frontend run build`.
- Migrations geradas via `makemigrations` e versionadas no mesmo commit da mudança de model.

---

## Decisões de design

**Primary keys como `BigAutoField`** — app interno autenticado; autorização por `escola` já protege contra IDOR; FKs leves importam quando `Usuario` é referenciado em vários lugares. Se um dia UUID for necessário, usar UUIDv7 (time-ordered, RFC 9562).

**`on_delete=PROTECT` em todas as FKs de tenant** — deletar uma `Escola` com registros filhos levanta `ProtectedError`. A remoção exige limpar dependentes ou desativar via `Escola.ativa=False`. Única exceção: `ItemPresenca.registro` usa `CASCADE` porque itens são filhos do ciclo de vida do registro.

**Soft delete em `Aluno`** — `DELETE /api/v1/alunos/{id}/` marca `ativo=False` em vez de remover a linha. Preserva histórico de ocorrências e presença vinculados ao aluno, que têm valor de auditoria escolar. Frontend pode filtrar inativos com `?ativo=true`.

**Alunos não logam** — identificados por nome e matrícula. Não têm conta `Usuario`.

**Sem middleware de tenant por enquanto** — o isolamento é feito por queryset escopado (`EscopoEscolaMixin`). Middleware, Postgres RLS e billing são trabalho de um PR focado quando/se o sistema virar SaaS.

**JWT com claims customizados** — `access` carrega `escola_id`, `perfil`, `username`, `first_name`, `last_name` para que o frontend não precise de request adicional após o login. Como o `TokenRefreshView` propaga claims do refresh, mudanças nesses dados só refletem após o `REFRESH_TOKEN_LIFETIME` (7 dias) expirar — trade-off aceito no MVP.

**Dark mode permanente no frontend** — sem toggle. O `<html class="dark">` é fixado no `index.html` para evitar flash de tema light no carregamento. Decisão de UI; pode ser revertida adicionando um theme provider quando houver demanda.

**Optimistic update na chamada de presença** — clicar P/A/J/R num aluno muda a UI imediatamente; em caso de erro, o cache é revertido via snapshot. Sensação de fluidez sem esperar round-trip do backend.

**`Lecionamento` em vez de M2M direta** — a relação professor↔disciplina virou um modelo intermediário `Lecionamento(professor, turma, disciplina)` em vez da M2M simples `Professor.disciplinas`. Isso permite saber *qual disciplina o professor dá em qual turma*, não só "quais matérias ele cobre". Granularidade necessária pra perguntas reais do diário ("quem dá Mat no 1º A?").

**Permissões refletidas na UI** — o backend é a fonte de verdade (cada ViewSet tem suas permission classes); o frontend só espelha via `usePermissoes` pra não mostrar botões que dariam 403. Escrita em cadastros é admin/diretor; professor tem leitura.

---

## Já entregue (infra, segurança e comunicação)

- **Infra:** Docker (dev + prod), deploy no ar (Render + Vercel), backup do PostgreSQL (`scripts/`), CI no GitHub Actions.
- **Segurança:** rate limit no login, JWT blacklist + rotação de refresh, hardening de produção (CSRF trusted origins, proxy SSL, cookies secure/HSTS).
- **Comunicação:** notificação por email ao responsável quando uma ocorrência é criada (síncrono, via Resend).

## Backlog (não implementado)

A lista priorizada por fases vive em [`CLAUDE.md`](./CLAUDE.md) (seção Roadmap). Resumo do que ainda falta:

- **Robustez:** paginação no backend (DRF `PageNumberPagination`), audit log (`django-simple-history`), observabilidade (Sentry + logging estruturado).
- **Produto:** exportação de relatórios (PDF/CSV/Excel), métricas avançadas no dashboard (reincidência, presença média).
- **Comunicação:** múltiplos responsáveis por aluno, fila assíncrona de email (Celery/Redis) quando o volume crescer, timeline do aluno.
- **Senhas:** trocar a própria senha, reset por e-mail, admin resetar senha de terceiro pela UI.
- **Dev experience:** drf-spectacular (gera client TypeScript), `repositories.py` por app, linting unificado (`ruff` + ESLint no fluxo).
- **SaaS futuro:** multi-tenancy real (middleware + RLS + billing), httpOnly cookies, LGPD formal.

> Pra enviar email pros responsáveis de verdade (não só modo teste), falta **verificar um domínio no Resend** e trocar o `DEFAULT_FROM_EMAIL`.
