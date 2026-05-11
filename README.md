# Diário Escolar

API REST para registro escolar — controle de ocorrências, presença e gestão de turmas.

Construído com Django 5.2 + Django REST Framework. Arquitetura single-tenant com estrutura preparada para evolução SaaS sem retrofit doloroso.

---

## Stack

| Camada | Tecnologia |
|---|---|
| Framework | Django 5.2 + Django REST Framework |
| Banco de dados | PostgreSQL (driver `psycopg` 3) |
| Autenticação | SimpleJWT (Bearer token) |
| Filtros | django-filter |
| Configuração | python-decouple (`.env`) |
| CORS | django-cors-headers |

---

## Arquitetura

Cada app de domínio segue o mesmo padrão de camadas (inspirado no layout Go RESTful usado em produção):

```
apps/<dominio>/
├── models.py        — estrutura de dados e invariantes
├── serializers.py   — validação HTTP e representação JSON
├── views.py         — handlers HTTP (DRF ViewSets)
├── urls.py          — registro de rotas
├── admin.py         — interface administrativa
├── repositories.py  — (planejado) queries ORM isoladas
├── services.py      — (planejado) lógica de negócio
└── migrations/      — histórico versionado do schema
```

### Modelo de permissões

Três níveis granulares definidos em `apps/common/permissions.py`, combinados por ViewSet:

| Classe | Acesso |
|---|---|
| `IsAdmin` | Superuser Django ou `perfil=admin` |
| `IsAdminOrDiretor` | Admin + `perfil=diretor` |
| `IsAdminOrDiretorOrProfessor` | Admin + diretor + `perfil=professor` |

Leitura (`list`/`retrieve`) usa a permissão mais ampla; escrita (`create`/`update`/`destroy`) usa a mais restrita. Todos os querysets são escopados à `escola` do usuário autenticado.

### Multi-tenancy

Single-tenant hoje. A base abstrata `BaseModelEscopado` (FK `escola` + timestamps em todos os modelos de domínio) foi desenhada para ativar row-level tenancy sem refatoração quando o sistema escalar para SaaS.

---

## Estrutura do projeto

```
Diario-Escolar/
├── config/               — configurações Django (settings, urls, wsgi, asgi)
├── apps/
│   ├── common/           — base abstrata, validators, permissões reutilizáveis
│   ├── accounts/         — Usuario (AbstractUser) + perfis de acesso
│   ├── escola/           — Escola, Turma, Disciplina, Aluno, Professor
│   ├── ocorrencias/      — (planejado) Ocorrencia
│   └── presenca/         — (planejado) RegistroPresenca + ItemPresenca
├── manage.py
├── requirements.txt
└── .env.example
```

---

## O que está implementado

### `apps/common`
- `TimeStampedModel` — `criado_em` / `atualizado_em` automáticos
- `BaseModelEscopado` — base abstrata com FK `escola` para todos os modelos de domínio
- `EscopoEscolaMixin` — filtra querysets automaticamente pela escola do usuário logado
- Permissões granulares por perfil (`IsAdmin`, `IsAdminOrDiretor`, `IsAdminOrDiretorOrProfessor`)
- Validator de CNPJ com dígito verificador

### `apps/accounts`
- `Usuario` estendendo `AbstractUser`
- Perfis: `admin`, `diretor`, `professor`, `secretaria`, `inspetor`
- FK opcional para `Escola` (obrigatória para usuários não-superuser no futuro SaaS)
- CRUD via API (`UsuarioViewSet`), restrito a admin e diretor

### `apps/escola`
- `Escola` — tenant root; CNPJ validado; remoção protegida enquanto houver dados vinculados
- `Turma` — turno (`matutino`/`vespertino`/`noturno`/`integral`) + ano letivo; única por `(escola, nome, ano_letivo)`
- `Disciplina` — matéria oferecida; única por `(escola, nome)`
- `Aluno` — não loga; identificado por nome + `matricula` única por escola; invariante turma/escola validada
- `Professor` — OneToOne com `Usuario` (`perfil=professor`); M2M com `Disciplina`; invariante `usuario.escola == professor.escola`
- CRUD completo via API para todos os modelos acima
- Filtros declarativos (django-filter) + busca por nome/matrícula

---

## O que está planejado

| Etapa | Escopo |
|---|---|
| **Etapa 4** | App `ocorrencias` — `Ocorrencia` (turma + aluno + professor opcional + status: `aberta`/`em_andamento`/`resolvida`/`arquivada`) |
| **Etapa 5** | App `presenca` — `RegistroPresenca` (turma + data, único por dia) + `ItemPresenca` (status: `P`/`A`/`J` por aluno) |
| **Etapa 6** | URLs versionadas `/api/v1/` + JWT (`/api/v1/auth/token/` obtain e refresh) |
| **Etapa 7** | README de operação inicial |
| **Backlog** | `repositories.py` e `services.py` em cada app, Docker + docker-compose, drf-spectacular (Swagger/OpenAPI), linting (black + isort + flake8) |

---

## Endpoints planejados

```
POST   /api/v1/auth/token/          — obter JWT
POST   /api/v1/auth/token/refresh/  — renovar JWT

GET|POST        /api/v1/usuarios/
GET|PUT|DELETE  /api/v1/usuarios/{id}/

GET|POST        /api/v1/escolas/
GET|PUT|DELETE  /api/v1/escolas/{id}/

GET|POST        /api/v1/turmas/
GET|PUT|DELETE  /api/v1/turmas/{id}/

GET|POST        /api/v1/disciplinas/
GET|PUT|DELETE  /api/v1/disciplinas/{id}/

GET|POST        /api/v1/alunos/
GET|PUT|DELETE  /api/v1/alunos/{id}/

GET|POST        /api/v1/professores/
GET|PUT|DELETE  /api/v1/professores/{id}/

GET|POST        /api/v1/ocorrencias/
GET|PUT|DELETE  /api/v1/ocorrencias/{id}/

GET|POST        /api/v1/presenca/
GET|PUT|DELETE  /api/v1/presenca/{id}/
```

> Todos os endpoints exigem autenticação Bearer. O queryset retornado é sempre escopado à escola do usuário autenticado.

---

## Setup local

**Requisitos:** Python 3.12+, PostgreSQL 15+

```bash
# 1. ambiente virtual
python -m venv .venv
.venv\Scripts\activate        # Windows PowerShell
# source .venv/bin/activate   # Linux / macOS

# 2. dependências
pip install -r requirements.txt

# 3. variáveis de ambiente
copy .env.example .env
# editar .env com as credenciais reais do PostgreSQL

# 4. criar o banco (no PostgreSQL)
# CREATE DATABASE diario_escolar;

# 5. aplicar migrations
python manage.py migrate

# 6. criar superusuário
python manage.py createsuperuser

# 7. rodar o servidor
python manage.py runserver
```

---

## Fluxo de desenvolvimento

```
feature/* → develop → main
```

- Todo desenvolvimento começa em `feature/<nome>`
- PR obrigatório para `develop`
- Quando `develop` está estável, PR `develop → main`
- Antes de abrir PR: `python manage.py check && python manage.py test`
- Migrations geradas via `makemigrations` e versionadas no mesmo commit da mudança de model

---

## Decisões de design

**Primary keys como `BigAutoField`** — app interno autenticado; autorização por `escola` já protege contra IDOR; FKs leves importam quando `Usuario` é referenciado em vários lugares. Se um dia UUID for necessário, usar UUIDv7 (time-ordered, RFC 9562).

**`on_delete=PROTECT` em todas as FKs de tenant** — deletar uma `Escola` com registros filhos levanta `ProtectedError`. A remoção exige limpar dependentes ou desativar via `Escola.ativa=False`.

**Alunos não logam** — identificados por nome e matrícula. Não têm conta `Usuario`.

**Sem middleware de tenant por enquanto** — o isolamento é feito por queryset escopado (`EscopoEscolaMixin`). Middleware, Postgres RLS e billing são trabalho de um PR focado quando/se o sistema virar SaaS.
