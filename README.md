# Diário Escolar

API REST para registro escolar — controle de ocorrências, presença e gestão de turmas.

Construído com Django 5.2 + Django REST Framework. Arquitetura single-tenant com estrutura preparada para evolução SaaS sem retrofit doloroso.

---

## Stack

| Camada | Tecnologia |
|---|---|
| Framework | Django 5.2 + Django REST Framework |
| Banco de dados | PostgreSQL (driver `psycopg` 3) |
| Autenticação | SimpleJWT (Bearer token, claims customizados) |
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

Quatro classes granulares definidas em `apps/common/permissions.py`, combinadas por ViewSet:

| Classe | Acesso |
|---|---|
| `IsAdmin` | Superuser Django ou `perfil=admin` |
| `IsAdminOrDiretor` | Admin + `perfil=diretor` |
| `IsAdminOrDiretorOrProfessor` | Admin + diretor + `perfil=professor` |
| `IsAdminOrDiretorOrProfessorOrInspetor` | Acima + `perfil=inspetor` (leitura em domínios de monitoramento) |

`ReadWritePermissionMixin` (em `apps/common/views.py`) padroniza a separação read/write por ação: `list`/`retrieve` usam `READ_PERMISSION`; demais usam `WRITE_PERMISSION`. Apps com regra uniforme (ex.: `ocorrencias`) usam `permission_classes` direto.

Leitura usa a permissão mais ampla; escrita usa a mais restrita. Todos os querysets são escopados à `escola` do usuário autenticado via `EscopoEscolaMixin`. Defesa contra IDOR na escrita: serializers de `ocorrencias` e `presenca` recusam payload com `escola` divergente da do usuário (admin/superuser bypassam).

### Multi-tenancy

Single-tenant hoje. A base abstrata `BaseModelEscopado` (FK `escola` + timestamps em todos os modelos de domínio) foi desenhada para ativar row-level tenancy sem refatoração quando o sistema escalar para SaaS.

### Autenticação JWT

Endpoints públicos:
- `POST /api/v1/auth/token/` — troca username/password por par `access` + `refresh`.
- `POST /api/v1/auth/token/refresh/` — gera novo `access` a partir de um `refresh` válido.

O `access` carrega claims customizados (`escola_id`, `perfil`) para que o frontend leia o escopo sem precisar de requests extras.

**Trade-off conhecido:** se admin trocar escola/perfil do usuário, os JWTs já emitidos continuam refletindo o estado anterior. Como `TokenRefreshView` propaga claims do refresh para o novo access, a janela real de staleness é o `REFRESH_TOKEN_LIFETIME` (7 dias por default), não o `ACCESS_TOKEN_LIFETIME` (1h). Invalidação imediata exige token blacklist server-side — fora do escopo do MVP.

---

## Estrutura do projeto

```
Diario-Escolar/
├── config/               — configurações Django (settings, urls, wsgi, asgi)
├── apps/
│   ├── common/           — base abstrata, validators, permissões, mixins reutilizáveis
│   ├── accounts/         — Usuario (AbstractUser) + perfis de acesso + JWT customizado
│   ├── escola/           — Escola, Turma, Disciplina, Aluno, Professor
│   ├── ocorrencias/      — Ocorrencia
│   └── presenca/         — RegistroPresenca + ItemPresenca
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
- `ReadWritePermissionMixin` — padroniza permissão por ação (READ vs WRITE)
- Permissões granulares por perfil (`IsAdmin`, `IsAdminOrDiretor`, `IsAdminOrDiretorOrProfessor`, `IsAdminOrDiretorOrProfessorOrInspetor`)
- Validator de CNPJ com dígito verificador

### `apps/accounts`
- `Usuario` estendendo `AbstractUser`
- Perfis: `admin`, `diretor`, `professor`, `secretaria`, `inspetor`
- FK opcional para `Escola`
- CRUD via API (`UsuarioViewSet`), restrito a admin e diretor
- `UsuarioTokenObtainPairView` + `UsuarioTokenObtainPairSerializer` (JWT com `escola_id` e `perfil` no payload)

### `apps/escola`
- `Escola` — tenant root; CNPJ validado; remoção protegida enquanto houver dados vinculados
- `Turma` — turno (`matutino`/`vespertino`/`noturno`/`integral`) + ano letivo; única por `(escola, nome, ano_letivo)`
- `Disciplina` — matéria oferecida; única por `(escola, nome)`
- `Aluno` — não loga; identificado por nome + `matricula` única por escola; invariante turma/escola validada
- `Professor` — OneToOne com `Usuario` (`perfil=professor`); M2M com `Disciplina`; invariante `usuario.escola == professor.escola`
- CRUD completo via API para todos os modelos acima
- Filtros declarativos (django-filter) + busca por nome/matrícula

### `apps/ocorrencias`
- `Ocorrencia` — turma + aluno + professor opcional + descrição + data + status (`aberta`/`em_andamento`/`resolvida`/`arquivada`)
- Invariantes em `clean()` e serializer: `aluno.escola == escola`, `aluno.turma == turma` (snapshot atual), `professor.escola == escola`, `data <= hoje`
- Permissão uniforme `admin/diretor/professor` em todas as ações — colegas auxiliam a resolver registros uns dos outros
- Guard de IDOR no payload `escola`

### `apps/presenca`
- `RegistroPresenca` — chamada de uma turma num dia, única por `(escola, turma, data)`; `professor` opcional
- `ItemPresenca` — status individual por aluno (`P`/`A`/`J`/`R`: presente, ausente, justificado, retardatário). `CASCADE` no `registro` (único cascade do projeto)
- Auto-geração: criar `RegistroPresenca` via API gera `ItemPresenca(status=P)` para cada aluno ativo da turma em transação atômica
- `ItemPresenca.save()` força `escola_id = registro.escola_id` (coerência defensiva)
- `ItemPresencaViewSet` não expõe POST/DELETE — ciclo de vida pertence ao registro pai
- Leitura inclui inspetor; escrita admin/diretor/professor

### Roteamento `/api/v1/` + JWT
- Todos os endpoints versionados sob `/api/v1/`
- Autenticação Bearer obrigatória (exceto `/auth/token/` e `/auth/token/refresh/`)
- Claims customizados no JWT (`escola_id`, `perfil`)

---

## O que está planejado

| Etapa | Escopo |
|---|---|
| **Backlog** | `repositories.py` e `services.py` em cada app, Docker + docker-compose, drf-spectacular (Swagger/OpenAPI), linting (black + isort + flake8), token blacklist server-side |

---

## Endpoints

```
POST   /api/v1/auth/token/          — obter JWT (access + refresh)
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

GET|POST        /api/v1/registros-presenca/
GET|PUT|DELETE  /api/v1/registros-presenca/{id}/

GET             /api/v1/itens-presenca/
GET|PATCH|PUT   /api/v1/itens-presenca/{id}/
```

> Todos os endpoints (exceto `/auth/token/` e `/auth/token/refresh/`) exigem `Authorization: Bearer <access_token>`. O queryset retornado é sempre escopado à escola do usuário autenticado.

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

**`on_delete=PROTECT` em todas as FKs de tenant** — deletar uma `Escola` com registros filhos levanta `ProtectedError`. A remoção exige limpar dependentes ou desativar via `Escola.ativa=False`. Única exceção: `ItemPresenca.registro` usa `CASCADE` porque itens são filhos do ciclo de vida do registro.

**Alunos não logam** — identificados por nome e matrícula. Não têm conta `Usuario`.

**Sem middleware de tenant por enquanto** — o isolamento é feito por queryset escopado (`EscopoEscolaMixin`). Middleware, Postgres RLS e billing são trabalho de um PR focado quando/se o sistema virar SaaS.

**JWT com claims customizados** — `access` carrega `escola_id` e `perfil` para que o frontend não precise de request adicional após o login. Como o `TokenRefreshView` propaga claims do refresh, mudanças de escola/perfil só refletem após o `REFRESH_TOKEN_LIFETIME` (7 dias) expirar — trade-off aceito no MVP.
