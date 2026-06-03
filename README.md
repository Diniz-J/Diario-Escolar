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
| Audit log | django-simple-history (snapshot + diff + history_user nos 9 modelos do núcleo) |
| Email transacional | django-anymail (Brevo via HTTP API — porta 443) |
| Observabilidade | sentry-sdk[django] (error tracking, gated por `SENTRY_DSN`) |

### Frontend

| Camada | Tecnologia |
|---|---|
| Build / dev server | Vite 8 |
| Framework | React 19 |
| Linguagem | TypeScript 6 |
| Estilo | Tailwind CSS 4 + shadcn/ui (paleta de marca olive/linho/ferrugem em tokens) |
| Tipografia | Geist (sans, corpo) + Fraunces (serif variável, títulos via `font-heading`) |
| Roteamento | React Router 7 |
| Estado de servidor | TanStack Query 5 |
| HTTP | axios (com interceptors de Bearer + refresh) |
| Notificações | sonner |
| Observabilidade | @sentry/react + ErrorBoundary (gated por `VITE_SENTRY_DSN`) |

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
├── DEPLOY.md                — guia de deploy (Render + Vercel) + Brevo
├── DESIGN.md                — norte visual da marca (tokens, voz, componentes, anti-patterns)
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
| `IsAdminOrDiretor` | Admin + `perfil=diretor` + `perfil=secretaria` |
| `IsAdminOrDiretorOrProfessor` | Admin + diretor + secretaria + professor + inspetor |
| `IsAdminOrDiretorOrProfessorOrInspetor` | Mesmo grupo do anterior (ver "Aliases de perfil" abaixo) |

**Aliases de perfil**: `secretaria` opera como `diretor` (faz cadastros, gerencia usuários); `inspetor` opera como `professor` (lança ocorrência e chamada). A distinção entre eles é só **rótulo de UX** — sidebar e Dashboard mostram "Secretaria"/"Inspetor" no perfil, mas o conjunto de ações é idêntico ao do par equivalente. Decisão consciente pra escala de escola pequena/média onde os papéis são fluidos no dia a dia. Quando crescer pra rede grande, os perfis já existem distintos no enum `Usuario.Perfil` — basta refinar as classes pra separar.

`ReadWritePermissionMixin` (em `apps/common/views.py`) padroniza separação read/write por ação: `list`/`retrieve` usam `READ_PERMISSION`; o restante usa `WRITE_PERMISSION`. Apps com regra uniforme (ex.: `ocorrencias`) declaram `permission_classes` direto.

Por padrão, **escrita em cadastros** (Aluno, Turma, Disciplina, Professor, Lecionamento) é restrita a admin/diretor — professor tem leitura mas não cria/edita/exclui. O frontend espelha isso via hook `usePermissoes` (esconde botões "Novo/Editar/Excluir" pra perfil professor), evitando 403 visível.

Todos os querysets são escopados à `escola` do usuário autenticado via `EscopoEscolaMixin`. Defesa contra IDOR na escrita: cada serializer com FK `escola` aplica o helper `validate_escola_do_usuario` — admin/superuser passam qualquer escola; não-admin só pode escrever na própria mesmo que envie outra explicitamente no payload.

**Auto-escopo de escola na criação** — diretor/professor/secretaria/inspetor **não precisa selecionar escola** ao criar turma, ocorrência, aluno, etc. O `AutoEscopoEscolaSerializerMixin` (em `apps/common/serializers.py`) injeta `escola` no payload via `to_internal_value` quando o usuário tem `escola_id` no JWT e o campo foi omitido. O frontend nem mostra o select de escola pra esses perfis — multi-tenant fica invisível pro cliente final. Admin global (sem escola no perfil) continua precisando especificar `escola` no payload, com 400 explícito se omitir.

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
- **Notificação por email** (`services.py`): ao criar uma ocorrência (`perform_create`), envia email ao `email_responsavel` do aluno. O disparo roda em **thread daemon** (fire-and-forget) — o POST volta na hora; o email é melhor-esforço protegido por `try/except`. Em `TESTING` o envio é síncrono pra deixar `mail.outbox` determinístico. Provedor em produção: **Brevo via HTTP API** (`django-anymail`, porta 443) — escolhido porque o free tier do Render bloqueia outbound SMTP desde set/2025. Ver [`DEPLOY.md`](./DEPLOY.md).

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

### Identidade visual

Light mode permanente com paleta de marca **Diário Diniz**: olive como cor primária (CTAs, sidebar), linho como fundo principal (papel), paper (off-white) em cards e inputs, ferrugem como accent quente (filetes, foco, indicadores), tinta + sepia como texto. Os tokens vivem em `src/index.css` como CSS variables e estão mapeados pros tokens do shadcn (`--background`, `--primary`, `--card`, etc.) — qualquer componente shadcn off-the-shelf herda automaticamente. A fonte da verdade visual da marca (tokens, voz, componentes cristalizados, anti-patterns) vive em [`DESIGN.md`](./DESIGN.md).

Tipografia mista: **Fraunces** (serif variável) em títulos via `font-heading`, **Geist** (sans) no corpo. A combinação dá tom editorial sem perder legibilidade — assinatura visual consistente entre Login, sidebar, Dashboard e todas as 8 telas de lista (Alunos, Turmas, Disciplinas, Professores, PlanosEnsino, Ocorrencias, Presenca, Tarefas), cada uma com header em Fraunces + filete ferrugem e tabelas em `bg-paper`. Detalhes e formulários ainda herdam paleta via tokens shadcn mas serão repaginados nas próximas ondas.

Status badges 100% na paleta da marca (ocorrências, tarefas, presença) — sem amber/blue/green/red genéricos do Tailwind.

Layout responsivo: a sidebar fixa (≥768px) vira um drawer (`Sheet`) com botão hamburguer abaixo de 768px. Padding e tipografia ajustam por breakpoint (`p-4 md:p-8`, `text-2xl md:text-3xl`). Headers de detalhe com muitas ações empilham até `lg` (1024px) pra evitar competição visual em tablet portrait. Tabelas escondem colunas secundárias em telas estreitas (`hidden sm:table-cell` / `md:` / `lg:`) em vez de scroll horizontal — os dados completos ficam acessíveis clicando na linha (vai pro detalhe). Funciona em celular (chamada de presença em sala) e tablet.

Soft delete UX: listagens com soft delete (Aluno) escondem inativos por padrão. Toggle `Switch` "Mostrar inativos" na `AlunosPage` inverte e mostra só os inativos com badge `[ inativo ]`. Selects de criação (ex.: nova ocorrência) ficam restritos a ativos. Telas que apenas resolvem nome de aluno em registros antigos (ocorrências, presenças, tarefas) carregam todos os alunos pra não quebrar histórico.

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
>
> Em produção, o backend também aceita origens via `CORS_ALLOWED_ORIGIN_REGEXES` (CSV de regex) — usado pra liberar os domínios dinâmicos dos preview deployments do Vercel (ex.: `^https://diario-escolar-[a-z0-9-]+\.vercel\.app$`). `CSRF_TRUSTED_ORIGINS` complementa com wildcard `https://*.vercel.app` (Django 4+).

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

**Light mode permanente no frontend** — paleta de marca olive/linho aplicada via CSS variables nos tokens do shadcn. `<meta name="color-scheme" content="light">` desabilita o force-dark-mode automático de browsers (Opera GX, Chrome auto-dark). Sem toggle de tema; adicionar dark vira um theme provider quando houver demanda comercial.

**Optimistic update na chamada de presença** — clicar P/A/J/R num aluno muda a UI imediatamente; em caso de erro, o cache é revertido via snapshot. Sensação de fluidez sem esperar round-trip do backend.

**`Lecionamento` em vez de M2M direta** — a relação professor↔disciplina virou um modelo intermediário `Lecionamento(professor, turma, disciplina)` em vez da M2M simples `Professor.disciplinas`. Isso permite saber *qual disciplina o professor dá em qual turma*, não só "quais matérias ele cobre". Granularidade necessária pra perguntas reais do diário ("quem dá Mat no 1º A?").

**Permissões refletidas na UI** — o backend é a fonte de verdade (cada ViewSet tem suas permission classes); o frontend só espelha via `usePermissoes` pra não mostrar botões que dariam 403. Escrita em cadastros é admin/diretor; professor tem leitura.

---

## Já entregue (infra, segurança, comunicação, observabilidade, produto)

- **Infra:** Docker (dev + prod), deploy no ar (Render + Vercel), backup do PostgreSQL (`scripts/`), CI no GitHub Actions.
- **Segurança:** rate limit no login (5/min), JWT blacklist + rotação de refresh, hardening de produção (CSRF trusted origins, proxy SSL, cookies secure/HSTS), guard de IDOR consistente em todos os serializers com FK `escola`.
- **Audit log:** `django-simple-history` nos 9 modelos do núcleo (Aluno, Professor, Lecionamento, Ocorrencia, RegistroPresenca, ItemPresenca, Tarefa, EntregaTarefa, PlanoEnsino, Usuario) com aba History no `/admin/` mostrando diff lado a lado. `populate_history --auto` no boot pra marco-zero dos registros pré-PR.
- **Comunicação:** notificação por email ao responsável funcional em produção via **Brevo HTTP API** (`django-anymail`) — off-thread, protegido, sem domínio próprio, 300 emails/dia free. Resend e Gmail SMTP foram tentados e falharam pelo bloqueio de SMTP outbound do Render free desde set/2025.
- **Observabilidade:** Sentry SDK no backend e frontend — captura exceções não tratadas + `logger.error/exception` + erros de render React via `<Sentry.ErrorBoundary>`. Plano free (Developer) 5k events/mês.
- **Produto:** Dashboard com métricas (4 cards) + filtro por turma; soft delete + UX completa (toggle "Mostrar inativos" + Reativar); auto-escopo de escola em criação (multi-tenant invisível pro usuário).
- **Identidade visual:** paleta de marca olive/linho/ferrugem com tokens semânticos, tipografia Fraunces + Geist em hierarquia editorial, Login + Sidebar + Dashboard repaginados em light mode permanente.

## Backlog (não implementado)

A lista priorizada por fases vive em [`CLAUDE.md`](./CLAUDE.md) (seção Roadmap). Resumo do que ainda falta:

- **Robustez:** paginação no backend (DRF `PageNumberPagination`) antes do volume real, logging estruturado JSON.
- **Produto:** exportação de relatórios (PDF/CSV/Excel), métricas avançadas no dashboard (reincidência, presença média), redesign das telas de listagem/detalhe/formulário (ondas seguintes).
- **Comunicação:** múltiplos responsáveis por aluno + telefone + flag `recebe_notificacao`, fila assíncrona dedicada (Celery/Dramatiq/RQ) quando o volume crescer, timeline do aluno (consumindo HistoricalRecords + ocorrências + presença).
- **Senhas:** trocar a própria senha, reset por e-mail (agora viável via Brevo), admin resetar senha de terceiro pela UI.
- **Dev experience:** drf-spectacular (gera client TypeScript), `repositories.py` por app, linting unificado (`ruff` + ESLint no fluxo).
- **SaaS futuro:** multi-tenancy real (middleware + RLS + billing), httpOnly cookies, LGPD formal.

> Higiene de segredos pendente (ações no painel): rotacionar `SECRET_KEY` (apareceu como 5 bytes em log do Render, JWT inseguro), rotacionar senha do banco, revogar API key antiga do Resend.
