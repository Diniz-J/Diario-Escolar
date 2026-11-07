# Diário Escolar

Aplicação web para registro escolar — gestão disciplinar (ocorrências, com
notificação por email ao responsável), presença, avaliações e notas, diário de
classe, comunicados aos responsáveis, planos de ensino, boletim, mensalidade
(contas a receber) e cadastros (alunos, turmas, disciplinas, professores).

Tem também um **portal de leitura para o responsável** sob `/portal`, com
autenticação própria: o pai acompanha comunicados, boletim, ocorrências,
mensalidades e o mural de materiais dos filhos vinculados. O aluno não loga, e
o portal não escreve nada — ver [`PORTAL.md`](./PORTAL.md).

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
| Import/export | django-import-export + tablib[xlsx] (planilhas CSV/XLSX via API) |
| PDF | WeasyPrint (boletim, diário de aula, relatórios — síncrono na request) |
| Gateway de cobrança | httpx (client próprio e fino do Asaas; não existe SDK Python maduro) |

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
| Testes | vitest + jsdom + @testing-library/react + MSW (mock de rede) |

---

## Estrutura do projeto

```
Diario-Escolar/
├── config/                  — settings, urls, wsgi, asgi do Django
├── apps/
│   ├── common/              — base abstrata, validators, permissões, mixins reutilizáveis
│   ├── accounts/            — Usuario (AbstractUser) + perfis + JWT customizado
│   ├── escola/              — Escola, Turma, Disciplina, Aluno, Professor, Lecionamento
│   ├── ocorrencias/         — Ocorrencia + services.py (email aos responsáveis)
│   ├── presenca/            — RegistroPresenca + ItemPresenca
│   ├── avaliacao/           — PeriodoAvaliativo, Avaliacao, NotaAvaliacao, NotaPeriodo
│   ├── tarefas/             — esqueleto vazio (feature removida; ver apps/avaliacao)
│   ├── comunicados/         — Comunicado + ComunicadoDestinatario (avisos por email)
│   ├── portal/              — Responsavel + ResponsavelAluno + ConviteResponsavel
│   │                          + destinatarios.py (origem única de quem recebe email)
│   ├── materiais/           — Material (mural do professor pra turma: texto + link)
│   ├── notificacoes/        — outbox de email (Mensagem) + rota das tarefas periódicas
│   ├── financeiro/          — PlanoCobranca, Fatura, FaturaItem, Pagamento, EventoWebhook
│   │                          + gateways/ (Asaas) + webhook de conciliação
│   ├── planos_ensino/       — PlanoEnsino
│   ├── boletins/            — agregação on-the-fly (sem modelo; services.py)
│   ├── timeline/            — timeline do aluno (sem modelo; services.py)
│   ├── aulas/               — RegistroAula (diário de classe) + projeção de agenda
│   └── relatorios/          — relatórios operacionais em PDF/CSV/XLSX (sem modelo)
├── frontend/                — app React (Vite + TypeScript)
│   ├── src/
│   │   ├── components/      — AppLayout (sidebar + drawer mobile), ProtectedRoute,
│   │   │                      AlertaOpcoesIndisponiveis, ui/* (shadcn)
│   │   ├── features/        — domínio por pasta: auth, alunos, turmas, escolas,
│   │   │                      professores, lecionamentos, disciplinas, dashboard,
│   │   │                      ocorrencias, presenca, comunicados, planos-ensino,
│   │   │                      boletins, usuarios, avaliacoes, periodos-avaliativos,
│   │   │                      notas-finais, aulas, materiais, responsaveis,
│   │   │                      financeiro, relatorios, timeline, import-export, portal
│   │   ├── lib/             — api (axios + interceptors), queryClient, datas,
│   │   │                      download (baixa arquivo autenticado via Blob), utils
│   │   ├── pages/           — as telas do staff (ver "Páginas" abaixo)
│   │   ├── portal/          — árvore do responsável: PortalApp, PortalLayout,
│   │   │                      PortalRoutes + pages/ (chunk próprio via React.lazy)
│   │   ├── test/            — harness dos testes de componente (vitest + jsdom
│   │   │                      + testing-library + MSW): render.tsx, autenticar.ts,
│   │   │                      servidor.ts, setup.ts
│   │   ├── routes.tsx       — mapa central de rotas
│   │   ├── types/api.ts     — interfaces que casam com os serializers do backend
│   │   ├── App.tsx          — providers globais (Query, Auth, Toaster) + split /portal
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
├── DEPLOY.md                — guia de deploy (Render + Vercel) + Brevo + cron
├── DESIGN.md                — norte visual da marca (tokens, voz, componentes, anti-patterns)
├── CLAUDE.md                — guia pra agentes de IA (guardrails + mapa + roadmap)
├── PORTAL.md                — desenho do portal do responsável (decisões + segurança)
├── RESPONSAVEIS.md          — convergência do responsável (vínculo, opt-out, destino do email)
├── FINANCEIRO.md            — desenho do financeiro (invariantes, gateway, webhook)
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
| `IsAdminOrDiretor` | Admin + `perfil=diretor` + `perfil=secretaria` + `perfil=coordenador` |
| `IsAdminOrDiretorOrProfessor` | Admin + diretor + secretaria + coordenador + professor + inspetor |
| `IsAdminOrDiretorOrProfessorOrInspetor` | Mesmo grupo do anterior (ver "Aliases de perfil" abaixo) |

**Aliases de perfil**: `secretaria` e `coordenador` operam como `diretor` (fazem cadastros, gerenciam usuários); `inspetor` opera como `professor` (lança ocorrência e chamada). A distinção entre eles é só **rótulo de UX** — sidebar e Dashboard mostram "Secretaria"/"Coordenador"/"Inspetor" no perfil, mas o conjunto de ações é idêntico ao do par equivalente. Decisão consciente pra escala de escola pequena/média onde os papéis são fluidos no dia a dia. Quando crescer pra rede grande, os perfis já existem distintos no enum `Usuario.Perfil` — basta refinar as classes pra separar.

`ReadWritePermissionMixin` (em `apps/common/views.py`) padroniza separação read/write por ação: `list`/`retrieve` usam `READ_PERMISSION`; o restante usa `WRITE_PERMISSION`. Apps com regra uniforme (ex.: `ocorrencias`) declaram `permission_classes` direto.

`FiltroEscopoObrigatorioMixin` (mesmo arquivo) protege os endpoints **matriz** (`NotaAvaliacao`, `NotaPeriodo`, `ItemPresenca`) — uma linha por (aluno × avaliação) / (aluno × chamada). O `list` é recusado (400) sem um filtro de escopo (`?avaliacao=`, `?registro=`, etc.). As telas que os consomem (lançamento de notas em lote, chamada) sempre passam o filtro e precisam de todos os alunos de uma vez, então a escolha foi **limitar a carga por escopo em vez de paginar** — evita varredura de dezenas de milhares de linhas sem quebrar a UX.

Por padrão, **escrita em cadastros** (Aluno, Turma, Disciplina, Professor, Lecionamento) é restrita a admin/diretor — professor tem leitura mas não cria/edita/exclui. O frontend espelha isso via hook `usePermissoes` (esconde botões "Novo/Editar/Excluir" pra perfil professor), evitando 403 visível.

Todos os querysets são escopados à `escola` do usuário autenticado via `EscopoEscolaMixin`. Defesa contra IDOR na escrita: cada serializer com FK `escola` aplica o helper `validate_escola_do_usuario` — admin/superuser passam qualquer escola; não-admin só pode escrever na própria mesmo que envie outra explicitamente no payload.

**Auto-escopo de escola na criação** — diretor/professor/secretaria/coordenador/inspetor **não precisa selecionar escola** ao criar turma, ocorrência, aluno, etc. O `AutoEscopoEscolaSerializerMixin` (em `apps/common/serializers.py`) injeta `escola` no payload via `to_internal_value` quando o usuário tem `escola_id` no JWT e o campo foi omitido. O frontend nem mostra o select de escola pra esses perfis — multi-tenant fica invisível pro cliente final. Admin global (sem escola no perfil) continua precisando especificar `escola` no payload, com 400 explícito se omitir.

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

Cada app de domínio segue o mesmo layout (`models.py`, `serializers.py`, `views.py`, `urls.py`, `admin.py`, `migrations/`, `tests/`). `services.py` aparece onde a regra não cabe no serializer nem na view — `ocorrencias` (email), `comunicados` (lote), `financeiro` (o que escreve dinheiro), `aulas` (agenda), e nas três apps sem modelo (`boletins`, `timeline`, `relatorios`), onde ele *é* a app. `repositories.py` segue no backlog: a camada só se paga quando houver query compartilhada entre services, o que ainda não aconteceu.

**`apps/common`**
- `TimeStampedModel` — `criado_em` / `atualizado_em` automáticos.
- `BaseModelEscopado` — base abstrata com FK `escola`.
- `EscopoEscolaMixin` — filtra queryset pela escola do usuário.
- `ReadWritePermissionMixin` — padroniza permissão por ação.
- `FiltroEscopoObrigatorioMixin` — recusa (400) o `list` dos endpoints matriz sem filtro de escopo. Levanta `ImproperlyConfigured` se `FILTROS_ESCOPO` ficar vazio; não afeta `retrieve` nem actions custom.
- `serializers.py` — `AutoEscopoEscolaSerializerMixin` (injeta a escola do JWT no payload, antes dos validators, inclusive do `UniqueTogether`) e `validate_escola_do_usuario` (guard de IDOR). Aplicados nos nove serializers com FK `escola`, substituindo o copy-paste que havia em quatro deles.
- `middleware.py` — contexto de escola no log estruturado (`EscolaLogContextMiddleware`) e captura de 4xx no Sentry (`SentryHttpErrorMiddleware`, ignora 401 por default).
- `health.py` — `ping` (liveness, sem I/O) e `health` (readiness, `SELECT 1`; 503 se o Postgres caiu). Públicos, pra load balancer e uptime monitor.
- `pdf.py` — render WeasyPrint, caminho da logo e slug ASCII do nome de arquivo, compartilhados pelos três PDFs do projeto (boletim, diário de aula, relatórios).
- `planilha.py` — **neutralização de fórmula** em CSV/XLSX. Excel e LibreOffice executam qualquer célula iniciada em `=`, `+`, `-` ou `@` ao abrir o arquivo, e o conteúdo exportado aqui é escrito por gente (descrição de ocorrência, título de avaliação, nome vindo de importação de terceiro). As células saem prefixadas com apóstrofo, que o Excel lê como "isto é texto" e não exibe. `desneutralizar_formula` é a contraparte, usada na leitura do import de migração, que é round-trip — sem ela o marcador seria gravado no banco na volta e cada ciclo acumularia mais um.
- Validator de CNPJ com dígito verificador.

**`apps/accounts`**
- `Usuario` estendendo `AbstractUser` com `perfil` (admin/diretor/professor/secretaria/coordenador/inspetor) + FK opcional para `Escola`.
- CRUD via `/api/v1/usuarios/` (admin e nível-diretor, o que inclui secretaria e coordenador). O serializer expõe `escola` (necessário para o frontend criar Professor com escola alinhada) e `senha_definida`, porque conta criada pela tela nasce **sem senha utilizável** (`set_unusable_password()`): "existe" e "já entra" são estados diferentes, e sem o sinal a secretaria reenviaria link a esmo.
- `UsuarioTokenObtainPairView` + `UsuarioTokenObtainPairSerializer` injetando os claims customizados.
- **Fluxo de senha completo**: público (`/auth/password/reset/request|confirm/`), próprio usuário logado (`/auth/password/change/`) e action de direção (`POST /usuarios/<id>/enviar-reset-senha/`), que dispara o mesmo link em nome do alvo — com guard de IDOR inline, porque não-admin só dispara reset pra alguém da própria escola. Toda a plumbing reusa `PasswordResetToken.gerar()` + `services.enviar_link_redefinicao()`.
- **A direção gere os próprios pares na própria escola** (decisão de out/2026): o movimento é lateral, já que secretaria, coordenador e diretor são aliases uns dos outros, então o que se ganha tomando uma dessas contas é persistência, não alcance — e `Usuario` é auditado. As linhas que **não** se mexem, cada uma com teste travando os dois lados: `perfil=admin` nem criado nem promovido (é o que separa lateral de escalada); `escola` admin-only no update (pulo de tenant), e na criação presa à escola do autor; `password` admin-only no update (o caminho da direção é o link de reset, que vai pro email do alvo); a conta do admin global intocável por não-admin; e ninguém muda o próprio perfil nem se desativa (dentro da escola não sobraria quem destrancasse).

**`apps/escola`**
- `Escola` — tenant root; CNPJ validado; remoção protegida.
- `Turma` — turno + ano letivo; única por `(escola, nome, ano_letivo)`.
- `Disciplina` — única por `(escola, nome)`; campo `ativa`. Migration semeia 14 disciplinas BNCC comuns por escola (idempotente via `get_or_create`).
- `Aluno` — não loga; identificado por matrícula única por escola; invariante turma/escola validada. Tem `nome_responsavel` + `email_responsavel` (obrigatórios no cadastro via serializer; `blank` no banco pra não quebrar alunos antigos) — entrada do cadastro e **fallback** de notificação: o destino do email são os vínculos `ResponsavelAluno`, e o campo só é usado quando o aluno não tem vínculo nenhum (ver `apps/portal/destinatarios.py`). Responsável vinculado pode recusar notificação (`Responsavel.recebe_notificacao`) sem perder o acesso ao portal. **`DELETE` faz soft delete** (marca `ativo=False`) para preservar histórico de ocorrências/presença.
- `Professor` — OneToOne com `Usuario` (`perfil=professor`); campo `ativo`; invariante `usuario.escola == professor.escola`. **`DELETE` faz soft delete** (`ativo=False`).
- `Lecionamento` — vínculo granular **professor × turma × disciplina** (substituiu a antiga M2M `Professor.disciplinas`). Permite responder "quais turmas o prof X dá?" e "quem leciona Mat no 1º A?". `ano_letivo` derivado da turma; unique `(professor, turma, disciplina)`; `clean()` valida escola alinhada nos três. Campo `dias_semana` (`ArrayField` de inteiros, 0=segunda…6=domingo) registra a grade horária — base pra projetar os slots do diário de aula.
- CRUD completo para todos via API, filtros declarativos + busca por nome/matrícula.

**`apps/tarefas`** — **esqueleto vazio.** `Tarefa` e `EntregaTarefa` foram removidos: a frente virou `apps/avaliacao` (PR #72), com os dados migrados em `avaliacao.0003_migrar_tarefas` (`Tarefa(vale_nota=True)` virou `Avaliacao`; sem nota foi descartada por decisão de produto). O diretório e o registro em `INSTALLED_APPS` seguem existindo só pra resolver as migrations históricas — não há model, view, rota nem tela.

**`apps/planos_ensino`**
- `PlanoEnsino` — ementa, conteúdo programático, objetivos gerais/específicos, habilidades BNCC, carga horária, metodologia, recursos, avaliação, `ativo`. Único por `(escola, turma, disciplina, ano_letivo)` com invariantes cruzadas. Casca criada num dialog enxuto; campos longos preenchidos na tela de detalhe.

**`apps/boletins`**
- Sem modelo próprio. `services.py` agrega frequência + notas + ocorrências on-the-fly; `BoletimAlunoView` (APIView) expõe `GET /boletins/aluno/<id>/`. Justificado (J) conta como presença efetiva no cálculo de frequência.

**`apps/timeline`**
- Sem modelo próprio, molde do `boletins`: `services.py` mescla três origens (ocorrências, presença e as mudanças de cadastro que o audit log guarda) numa lista ordenada por data desc, e `TimelineAlunoView` serve `GET /timeline/aluno/<id>/?data_inicio=&data_fim=`. Só JSON — o que a escola arquiva sai pelos relatórios.
- **Presença entra pelo que NÃO é presença**: o item `P` fica fora (200 "veio à aula" por ano afogam as cinco linhas que importam) e `J`/`R` entram como evento. É uma régua **deliberadamente diferente** da frequência, onde os dois contam como presença efetiva: a pergunta aqui é "o que aconteceu", e chegar atrasado aconteceu. Tem teste travando os dois lados pra ninguém "consertar" a divergência.
- O histórico do simple-history é lido inteiro e filtrado em Python: cada evento nasce da comparação com a entrada anterior, e filtrar no banco deixaria de fora justamente a entrada imediatamente antes da janela.
- `CAMPOS_CADASTRAIS` é **lista de permissão** (`turma`, `ativo`, `matricula`, `nome_completo`), não "tudo menos X" — `nome_responsavel`/`email_responsavel` ficam fora de propósito, porque a tela é lida por professor e inspetor e contato de responsável é nível-direção no resto do sistema.
- Teto de linhas com flag `truncado` na resposta: timeline cortada em silêncio faria a direção concluir que não houve mais nada.

**`apps/ocorrencias`**
- `Ocorrencia` — turma + aluno + professor opcional + descrição + data + status (`aberta`/`em_andamento`/`resolvida`/`arquivada`).
- Invariantes em `clean()` e serializer: `aluno.escola == escola`, `aluno.turma == turma` (snapshot atual), `professor.escola == escola`, `data <= hoje`.
- Permissão uniforme `admin/diretor/professor` — colegas auxiliam a resolver registros uns dos outros.
- Guard de IDOR no payload `escola`.
- **Notificação por email** (`services.py`): ao criar uma ocorrência (`perform_create`), envia email a **cada responsável** do aluno — a lista vem de `apps/portal/destinatarios.py` (vínculos `ResponsavelAluno`, com fallback pro campo de texto do aluno quando não há vínculo). Mãe e pai cadastrados recebem mensagens individuais, cada uma saudada pelo próprio nome; a falha de um endereço não cala o outro. O disparo roda em **thread daemon** (fire-and-forget) — o POST volta na hora; o email é melhor-esforço protegido por `try/except`. Em `TESTING` o envio é síncrono pra deixar `mail.outbox` determinístico. Provedor em produção: **Brevo via HTTP API** (`django-anymail`, porta 443) — escolhido porque o free tier do Render bloqueia outbound SMTP desde set/2025. Ver [`DEPLOY.md`](./DEPLOY.md).

**`apps/comunicados`**
- `Comunicado` — aviso institucional enviado por email aos responsáveis (reunião de pais, feriado, campanha). Título + mensagem + `destino` (`escola` = todos os responsáveis de alunos ativos / `turmas` = só as turmas selecionadas, via M2M) + `status` (`rascunho` → `enviando` → `enviado`/`falhou`). Auditado (simple-history, incluindo a M2M).
- **Dois passos, de propósito**: salvar cria/edita **rascunho e nunca envia**; o disparo é a action explícita `POST /comunicados/{id}/enviar/`. Depois do disparo o comunicado fica imutável (editar/excluir devolve 400) — é o registro do que chegou à caixa de entrada dos pais. Email não tem "desfazer".
- `ComunicadoDestinatario` — uma linha por **(aluno, responsável)** alcançado, com snapshot do email/nome no momento do disparo e o resultado (`pendente`/`enviado`/`falhou`/`sem_email`) + mensagem de erro do provedor. Criada **antes** do envio, pra que um crash no meio do lote deixe rastro. Responde "o responsável do João recebeu?" — e com mãe e pai vinculados responde pelos dois separadamente ("a mãe recebeu, o pai falhou"). Aluno sem destino nenhum gera uma única linha `sem_email`. A FK do responsável é nullable: linha de comunicado disparado antes dos vínculos existirem, ou vinda do fallback, fica com `NULL` e segue legível pelo snapshot. O unique é `(comunicado, aluno, responsavel)` com `nulls_distinct=False` — sem isso duas linhas com `NULL` passariam e a idempotência da materialização quebraria justo no caminho do fallback.
- **Privacidade (LGPD)**: cada responsável recebe uma mensagem individual. Um `To`/`CC` coletivo vazaria a lista de emails de todos os pais da escola para todos os pais da escola.
- **Deduplicação por endereço normalizado** (lowercase + strip): irmãos matriculados na mesma escola compartilham o responsável e receberiam o aviso duas vezes. As duas linhas de log continuam existindo e recebem o mesmo resultado.
- **Conexão única** (`get_connection`) para o lote inteiro, em vez de um handshake por mensagem.
- **Trava anti-duplo-clique**: a transição `rascunho → enviando` é um `UPDATE` condicional com rowcount checado. Dois cliques simultâneos: só o primeiro dispara, o segundo recebe **409**.
- Tolerância a falha: a recusa de um destinatário não aborta o lote (fica registrada na linha dele); falha ao **abrir** a conexão — cenário real do free tier do Brevo, 300 emails/dia — marca todas as linhas com o motivo do provedor e o comunicado vira `falhou`. `falhou` é reservado pro disparo que não entregou nada: "enviado com 3 falhas de 142" continua `enviado`.
- Permissão: **leitura** para nível-diretor + professor/inspetor (o corpo docente acompanha o que foi comunicado); **escrita e envio** só para nível-diretor. Guard de IDOR no payload `escola`.
- `filter_queryset` é aplicado só no `list`: o `get_object()` do DRF também o chama, e isso fazia `GET /comunicados/{id}/destinatarios/?status=sem_email` devolver 400 (o filtro da viewset comparava um status de *destinatário* com os status de *comunicado*).
- Envio em **thread daemon** (via `transaction.on_commit`, pra thread não correr com o commit da request); síncrono em `TESTING`. Mesmo provedor das ocorrências (Brevo via HTTP API).
- **Lock por grupo no envio (`_reivindicar`).** `_disparar` monta os grupos uma vez em memória e depois itera, então dois executores (a thread original e o `comunicados_retomar`) poderiam iterar conjuntos sobrepostos e enviar em dobro. Antes de cada envio, as linhas do grupo são reivindicadas com um `UPDATE` condicional em `pendente` → `enviando`; só um executor consegue. É a garantia real contra duplo envio em massa — o heartbeat sozinho só tornava improvável, e com margem pequena (o anymail usa `requests_timeout` de 30s, então 25 emails podem levar 12,5min contra um limite de 15min).
- **Linha indeterminada.** Uma linha que *fica* em `enviando` significa "não sabemos se o email saiu" (processo morreu entre o claim e a confirmação). **Nunca é reenviada automaticamente**: pra aviso em massa, duplicar é pior que faltar. Aparece no log como "Não confirmado" e a tela sugere a escola confirmar com aqueles responsáveis. Por isso `falhou` exige `indeterminados == 0`: dizer "não entregou nada" quando parte pode ter entregado seria mentira.
- **Recuperação de falha.** Se a materialização do público falhar, o comunicado **volta pra rascunho** (nada foi enviado ainda) em vez de ficar preso em `enviando` — estado que não é editável nem reenviável. Se o processo morrer no meio do lote (deploy/restart, já que thread daemon não sobrevive ao shutdown), `python manage.py comunicados_retomar` retoma de onde parou: `_disparar` reagrupa só as linhas `pendente`, então ninguém recebe duas vezes. O disparo carimba `atualizado_em` a cada 25 emails, o que permite distinguir um lote travado de um lote grande em curso e impede retomada concorrente (o comando ainda faz claim otimista por cima disso). Ver [`DEPLOY.md`](./DEPLOY.md).

**`apps/portal`** — portal do responsável. Desenho completo, decisões e invariantes de segurança em [`PORTAL.md`](./PORTAL.md); a convergência com o email de ocorrência, em [`RESPONSAVEIS.md`](./RESPONSAVEIS.md).
- `Responsavel` herda `AbstractBaseUser` **sem** ser `AUTH_USER_MODEL` (o projeto só tem um, `accounts.Usuario`): ganha hash de senha e `last_login`, mas não passa pelos backends de auth do Django, então o `is_active` da base é irrelevante — quem manda é o campo `ativo`. Email normalizado no `save()` (lowercase + strip), unique por `(escola, email)`.
- `ResponsavelAluno` — vínculo M2M que resolve "múltiplos responsáveis". `PROTECT` nos dois lados, `clean()` exige escola igual, auditado. É o modelo que decide quem vê os dados de quem.
- `ConviteResponsavel` — conta só existe por convite da escola. Sem auto-registro: qualquer pessoa poderia se declarar responsável de qualquer aluno, e matrícula é previsível (vetor de enumeração). Convite individual na UI + `manage.py portal_convidar_responsaveis` pra lote.
- `destinatarios.py` — **origem única de quem recebe email** (ocorrência, comunicado e aviso de pagamento chamam de lá): resolve pelos vínculos, pula conta inativa ou com `recebe_notificacao=False`, e só cai no `Aluno.email_responsavel` quando o aluno não tem vínculo **nenhum**. O fallback dispara por ausência de **vínculo**, nunca por ausência de destino — senão o opt-out viraria nada (`RESPONSAVEIS.md` §4.1).
- `recebe_notificacao` é opt-out de email e é **separado de `ativo`** de propósito: quem pede silêncio continua consultando o boletim no portal.
- **Autenticação isolada** sob `/api/v1/portal/auth/`: tokens com claims `tipo=responsavel` e `responsavel_id`, e **cada lado recusa o token do outro**, com teste nos dois sentidos. O risco não é óbvio e está documentado: o SimpleJWT resolve o claim de id contra o `AUTH_USER_MODEL`, então um token de `Responsavel` de pk N apresentado num endpoint de staff carregaria o `Usuario` de pk N.
- **Leituras** em `leituras.py`, todas partindo dos vínculos (`filhos_do`), nunca do id da URL: filhos, detalhe, boletim, ocorrências, materiais, faturas, comunicados e períodos.
- **Escrita do staff** em `views_staff.py` (`IsAdminOrDiretor`, escopado por escola): cadastro de conta e criação/remoção de vínculo (sem `PUT`/`PATCH`). O guard do vínculo tem **duas camadas** — o `clean()` exige os dois lados na mesma escola, e o serializer checa **cada lado contra a escola de quem está logado**; sem a segunda, um par consistente de outra escola passaria, porque o `clean()` não teria o que reclamar.
- Aluno desativado não corta o acesso: o responsável mantém o histórico (boletim, faturas), mas para de receber comunicado novo e o mural fica vazio.

**`apps/presenca`**
- `RegistroPresenca` — chamada de uma turma num dia; única por `(escola, turma, data)`; `professor` opcional.
- `ItemPresenca` — status individual por aluno (`P`/`A`/`J`/`R`: presente, ausente, justificado, retardatário). `CASCADE` no `registro` (único cascade do projeto).
- Auto-geração: criar `RegistroPresenca` gera `ItemPresenca(status=P)` para cada aluno ativo da turma em transação atômica.
- `ItemPresenca.save()` força `escola_id = registro.escola_id` (coerência defensiva).
- `ItemPresencaViewSet` não expõe POST/DELETE — ciclo de vida pertence ao registro pai.
- Leitura inclui inspetor; escrita admin/diretor/professor.

**`apps/avaliacao`**
- `PeriodoAvaliativo` — bimestre/trimestre/semestre modelado como faixa `[data_inicio, data_fim]` em vez de "número do bimestre", pra acomodar qualquer divisão sem refatorar. Unique por `(escola, nome, ano_letivo)` e por `(escola, ordem, ano_letivo)`; `clean()` impede sobreposição de datas. A property `estado` sai anotada com `Exists(...)` no viewset.
- `Avaliacao` — prova, trabalho ou atividade de uma turma+disciplina, alocada num período **pela data**. Toda avaliação vale nota (sucedeu o antigo `Tarefa`; "o que foi dado em aula" virou `apps/aulas`). Contadores de total de alunos e notas lançadas vêm de `annotate`, não de `SerializerMethodField` — eram dois `COUNT(*)` por linha.
- `NotaAvaliacao` — nota individual por aluno, auto-gerada (uma por aluno ativo da turma) na criação da avaliação. `nota=NULL` significa "ainda não lançada".
- `NotaPeriodo` — média final por (aluno × disciplina × período). **Digitada manualmente**: o sistema não calcula média. A escola decide a régua (ponderada, recuperação, conselho) fora do sistema e lança o resultado. Frequência é a única agregação automática, porque é objetiva e sem regra de negócio.
- Lançamento em lote usa `bulk_create_with_history`/`bulk_update_with_history` (preservam audit log): o `.save()` em loop custava 30 UPDATEs + 30 INSERTs de histórico numa turma de 30.
- `NotaAvaliacao` e `NotaPeriodo` são endpoints **matriz** (uma linha por aluno × avaliação) e exigem filtro de escopo no `list` — ver `FiltroEscopoObrigatorioMixin` acima. O `/historico/` de uma nota é limitado, porque nota muito editada viraria lista enorme.
- Permissão: leitura pro corpo docente inteiro (inclui inspetor); escrita de período é nível-direção, escrita de avaliação e nota inclui professor.

**`apps/aulas`**
- `RegistroAula` — diário de classe: o conteúdo programático efetivamente ministrado numa aula. Turma + disciplina + professor + data + `conteudo` (texto livre) + `status` (`rascunho` → `lancado` → `conferido`) + `conferido_por`/`conferido_em` (visto da direção). Único por `(escola, turma, disciplina, data)`. Auditado.
- Invariantes em `clean()`/serializer: escola alinhada (turma/disciplina/professor), **`Lecionamento` ativo obrigatório** pro trio, data não-futura, conteúdo exigido ao lançar.
- Viewset escopado: direção (admin/diretor/secretaria/coordenador) vê a escola inteira; professor/inspetor só os próprios registros. `perform_create` bloqueia (403) o professor que tenta lançar em nome de outro.
- Action `conferir` (só direção): `lancado → conferido`, grava quem/quando. O serializer recusa `status=conferido` (sem auto-conferência); aula conferida trava edição.
- Action `agenda` (`?turma=&disciplina=&mes=YYYY-MM`): projeta os slots do mês a partir de `dias_semana` do `Lecionamento`, on-the-fly via `services.py` (sem tabela). Navega mês a mês; ignora feriados na v1.
- Action `pdf` (`?professor=&data_inicio=&data_fim=&status=`): o diário impresso, com espaço de assinatura. Front entregue — diário do professor em `/diario`, ficha 360º do professor em `/professores/:id` (tabs Diário/Lecionamentos/Ocorrências/Dados) e card de pendência de conferência no dashboard.

**`apps/notificacoes`**
- `Mensagem` — uma linha por destinatário, gravada como `pendente` **antes** da tentativa de envio e carimbada depois. É essa ordem que faz o rastro sobreviver ao processo que morre no meio do envio, que é rotina no free tier do Render.
- Existe porque quatro caminhos disparavam email em thread daemon e não deixavam rastro nenhum (ocorrência, pagamento, convite do portal e link de senha): falha virava uma linha de log, e a escola não tinha como saber que o responsável nunca foi avisado.
- **Não** substitui o `ComunicadoDestinatario`. Aquele é o outbox do comunicado em lote, tem semântica mais rica (unique por `(comunicado, aluno, responsavel)`, materialização idempotente) e está em produção com lote de 150 — dobrá-lo pra caber num modelo genérico seria risco sem ganho.
- Não herda `BaseModelEscopado` apesar de ter `escola`: na base o campo é obrigatório, e o reset de senha do admin global não tem escola, então a base deixaria justamente o caminho de recuperação de conta sem rastro.
- `ORIGENS_RETENTAVEIS` **exclui o que carrega token**: convite reenviado carrega token que o `emitir_link` já apagou, e link de senha reenviado depois de uma hora chega morto. Os dois continuam **gravados** — o rastro vale onde o reenvio não vale.
- `tarefas.py` — `POST /api/v1/tarefas/executar/?tarefas=...`, a rota que o workflow agendado chama. Segunda rota sem autenticação de usuário do projeto e a primeira que *executa* algo, então: lista de permissão mapeando apelido a command fixo (aceitar o nome vindo da request seria `call_command` com entrada externa), token em `compare_digest` como no webhook do Asaas, recusa quando a env está vazia, e falha de uma tarefa não cancela as outras.
- `transaction.on_commit` aqui **não é precaução**: a thread lê as linhas de volta, então disparada antes do commit não encontraria o que a request acabou de gravar.

**`apps/materiais`**
- `Material` — mural do professor pra turma: turma + disciplina + professor + título + descrição + **link** (só `http`/`https`). Sem upload: não existe `FileField`/`MEDIA_ROOT` no projeto e o disco do Render é efêmero, então anexo exigiria object storage. Auditado.
- Mesmo molde do `RegistroAula`: `Lecionamento` ativo obrigatório, professor só vê/edita os próprios e não publica em nome de outro (403), direção vê a escola toda. `DELETE` faz soft delete (`ativo=False`).
- O portal lê em `/portal/alunos/<id>/materiais/` — só a turma atual do filho; filho desativado vê lista vazia.

**`apps/financeiro`** — contas a receber da mensalidade. Desenho, invariantes e pegadinhas em [`FINANCEIRO.md`](./FINANCEIRO.md).
- `PlanoCobranca` (contrato do aluno: valor, dia de vencimento, desconto, multa/juros, vigência, `pagador`), `Fatura` (uma competência do contrato), `FaturaItem` (detalhamento, `CASCADE` como o `ItemPresenca`), `Pagamento` (conciliação) e `EventoWebhook`. Os quatro primeiros são auditados.
- **A emissão de boleto/Pix não é nossa** — é do gateway (Asaas). Aqui fica o contas a receber e a conciliação; e o módulo **funciona sem gateway**: a escola que recebe Pix na conta e dinheiro na secretaria registra `Pagamento` manual.
- O valor é **congelado na geração**: reajuste em maio não reescreve a fatura de março.
- O unique é `(aluno, competencia)` e **não** `(plano, competencia)` — senão a troca de plano no meio do mês geraria duas faturas da mesma competência e cobraria o aluno duas vezes. É a única razão de `Fatura.aluno` ser desnormalizado. Na virada de contrato, cobra o plano **mais antigo** que pega a competência, decidido na aplicação: deixar o unique de banco decidir faria o valor do boleto depender da ordem de inserção.
- Multa e juros são **método** (`Fatura.encargos(hoje)`), não campo, e os percentuais moram no plano porque são cláusula de contrato — mudar a env não reescreve contrato assinado.
- `valor_pago`/`status` são escritos pelo `services.py`, nunca pelo `save()` do `Pagamento` (quebraria em bulk e esconderia o momento em que o dinheiro muda o estado da fatura). O recálculo substitui o incremento: é idempotente e se autocorrige. Tem teste travando.
- Dinheiro é sempre `DecimalField`, com arredondamento comercial (`ROUND_HALF_UP`) centralizado em `arredondar_dinheiro()`.
- `services.py` concentra `gerar_faturas` (idempotente), `emitir_cobranca`, `registrar_pagamento`/`estornar_pagamento` (em transação, com `select_for_update`) e `marcar_vencidas`. Três management commands pra cron — ver [`DEPLOY.md`](./DEPLOY.md).
- A emissão é passo **separado** da geração: a geração é transacional e em lote, e pendurar HTTP ali prenderia o lock pelo tempo do provedor.
- O **webhook** (`POST /financeiro/webhooks/asaas/`) é a única rota sem autenticação do projeto: token em `compare_digest`, evento gravado antes de processado (unique no id do evento, **não** escopado por escola porque o tenant só se descobre depois) e **reconsulta ao provedor antes de escrever dinheiro** — o token prova quem mandou, não quanto entrou. Responde 200 mesmo quando o processamento falha, porque 15 falhas consecutivas pausam a fila deles e param a escola inteira.
- API **só direção** (`IsAdminOrDiretor` uniforme; professor e inspetor levam 403 até na leitura). O que mexe em dinheiro é read-only na API: `status`/`valor_pago`/`data_pagamento` pertencem ao service, `id_externo`/`link_pagamento` ao gateway. `DELETE` cancela a fatura, desativa o plano, apaga o item e **estorna** o pagamento.

**`apps/relatorios`**
- Sem modelo próprio, mesmo molde do `boletins`: `services.py` agrega on-the-fly e `exportacao.py` concentra a mecânica comum (valida o formato, monta a planilha com tablib, neutraliza fórmula, devolve o download). Cada relatório serve seus formatos no mesmo recorte (`?formato=`) — uma rota por formato multiplicaria roteamento e filtro à toa.
- **Frequência por turma** (`GET /relatorios/frequencia/`): percentual por aluno na janela, com alerta de quem está abaixo dos 75% da LDB. Os contadores saem como agregados condicionais anotados sobre o `Aluno` (um JOIN, `Count` com `filter` por status) em vez de uma consulta por aluno — numa turma de 35 isso seria 35 queries, e o relatório existe justamente pra turma inteira. Mesma régua de presença do boletim (P/R/J contam; só A é falta), com teste comparando as duas pra não divergirem.
- **Métricas do dashboard** (`GET /relatorios/dashboard/?turma=`): presença média e reincidência de ocorrências, em três queries fixas. Mora aqui porque a régua de presença efetiva é desta app — uma terceira cópia dela é exatamente o que o teste de não-divergência boletim × relatório existe pra impedir. Janela fixa de 30 dias, **não exposta por parâmetro** (a tela não tem seletor de período). Reincidente é quem tem 2 ou mais ocorrências na janela, contado em Python sobre uma lista de contadores por aluno: em SQL exigiria `HAVING` sobre anotação dentro de `aggregate`, e a lista dá de graça o total de alunos envolvidos que o card usa na sublinha. Único relatório que serve só JSON — ninguém baixa dashboard em PDF. Usuário sem escola e não-admin recebe **zerado, não 403**: um 4xx aqui derrubaria a tela toda.
- **Ocorrências** (`GET /ocorrencias/exportar/`) e **cadastral de alunos** (`GET /alunos/relatorio/`) são actions do viewset que já tem o filtro e o escopo, então o arquivo sai com o mesmo recorte da tela; só o agrupamento, as linhas e o template moram aqui. O cadastral é **separado do `/alunos/export/`**: aquele é o serviço de migração em massa (admin global + flag `importacao_em_lote_habilitada`), este é a lista que a escola tira de si mesma (nível-diretor, sem flag).
- Turma de outra escola responde 404, não 403 — a resposta não confirma que o id existe. O nome da turma no cabeçalho do PDF sai dos dados encontrados, nunca do `?turma=` recebido, senão um id alheio imprimiria o nome da turma de outra escola num relatório vazio.
- Os PDFs têm teto de linhas: o recorte pode ser um ano letivo ou a escola inteira, o WeasyPrint é síncrono na request e um documento de dez mil blocos derruba o worker no free tier. O erro aponta qual filtro estreitar e manda pro CSV/XLSX, que não têm teto porque o custo é linear.

### Endpoints

```
POST   /api/v1/auth/token/          — obter JWT (access + refresh); rate limit 5/min
POST   /api/v1/auth/token/refresh/  — renovar JWT (rotaciona o refresh)
POST   /api/v1/auth/logout/         — blacklist do refresh (logout efetivo)
POST   /api/v1/auth/password/reset/request/   — pede o link de redefinição (público)
POST   /api/v1/auth/password/reset/confirm/   — redefine com o token do link (público)
POST   /api/v1/auth/password/change/          — troca a própria senha (logado)

POST   /api/v1/tarefas/executar/    — dispara os commands periódicos (?tarefas=, token em header)

GET    /api/v1/ping/                — liveness (público)
GET    /api/v1/health/              — readiness, checa o banco (público)

GET|POST        /api/v1/usuarios/
GET|PUT|PATCH|DELETE /api/v1/usuarios/{id}/
POST            /api/v1/usuarios/{id}/enviar-reset-senha/  (direção dispara o link)

GET|POST        /api/v1/escolas/
GET|PUT|PATCH|DELETE /api/v1/escolas/{id}/

GET|POST        /api/v1/turmas/
GET|PUT|PATCH|DELETE /api/v1/turmas/{id}/

GET|POST        /api/v1/disciplinas/
GET|PUT|PATCH|DELETE /api/v1/disciplinas/{id}/

GET|POST        /api/v1/alunos/                          (DELETE faz soft delete)
GET|PUT|PATCH|DELETE /api/v1/alunos/{id}/
GET             /api/v1/alunos/relatorio/                (cadastral, nível-diretor; ?formato=pdf|csv|xlsx)

GET|POST        /api/v1/professores/                     (DELETE faz soft delete)
GET|PUT|PATCH|DELETE /api/v1/professores/{id}/

GET|POST        /api/v1/lecionamentos/
GET|PUT|PATCH|DELETE /api/v1/lecionamentos/{id}/

GET             /api/v1/{turmas|disciplinas|alunos|professores|lecionamentos|planos-ensino}/export/
GET             /api/v1/{...}/template/                  (planilha modelo, mesmas 6 entidades)
POST            /api/v1/{...}/import/                    (migração em massa; admin global + flag da escola)

GET|POST        /api/v1/ocorrencias/
GET|PUT|PATCH|DELETE /api/v1/ocorrencias/{id}/
GET             /api/v1/ocorrencias/exportar/            (mesmo recorte da listagem; ?formato=pdf|csv|xlsx)

GET|POST        /api/v1/comunicados/                      (salvar NÃO envia: cria rascunho)
GET|PUT|PATCH|DELETE /api/v1/comunicados/{id}/            (só enquanto rascunho)
POST            /api/v1/comunicados/{id}/enviar/          (dispara os emails; 409 se já disparado)
GET             /api/v1/comunicados/{id}/previa/          (alcance sem enviar nada)
GET             /api/v1/comunicados/{id}/destinatarios/   (log de entrega; ?status=falhou)

GET|POST        /api/v1/planos-ensino/
GET|PUT|PATCH|DELETE /api/v1/planos-ensino/{id}/

GET|POST        /api/v1/registros-presenca/
GET|PUT|PATCH|DELETE /api/v1/registros-presenca/{id}/
GET             /api/v1/itens-presenca/                   (?registro= obrigatório no list)
GET|PATCH|PUT   /api/v1/itens-presenca/{id}/

GET|POST        /api/v1/periodos-avaliativos/
GET|PUT|PATCH|DELETE /api/v1/periodos-avaliativos/{id}/

GET|POST        /api/v1/avaliacoes/
GET|PUT|PATCH|DELETE /api/v1/avaliacoes/{id}/
POST            /api/v1/avaliacoes/{id}/lancar-notas/     (lote, com audit log preservado)

GET             /api/v1/notas-avaliacao/                  (?avaliacao= obrigatório no list)
GET|PUT|PATCH   /api/v1/notas-avaliacao/{id}/
GET             /api/v1/notas-avaliacao/{id}/historico/

GET             /api/v1/notas-periodo/                    (filtro de escopo obrigatório no list)
GET|PUT|PATCH   /api/v1/notas-periodo/{id}/
POST            /api/v1/notas-periodo/inicializar/        (abre a grade de um período)
POST            /api/v1/notas-periodo/lancar-em-lote/
GET             /api/v1/notas-periodo/{id}/historico/

GET|POST        /api/v1/registros-aula/                   (diário de classe)
GET|PUT|PATCH|DELETE /api/v1/registros-aula/{id}/
POST            /api/v1/registros-aula/{id}/conferir/     (visto da direção)
GET             /api/v1/registros-aula/agenda/            (?turma=&disciplina=&mes=YYYY-MM)
GET             /api/v1/registros-aula/pdf/               (?professor=&data_inicio=&data_fim=&status=)

GET|POST        /api/v1/materiais/                        (mural do professor; DELETE faz soft delete)
GET|PUT|PATCH|DELETE /api/v1/materiais/{id}/

GET|POST        /api/v1/planos-cobranca/                  (financeiro: só nível-diretor)
GET|PUT|PATCH|DELETE /api/v1/planos-cobranca/{id}/        (DELETE desativa o plano)
GET|POST        /api/v1/faturas/
GET|PUT|PATCH|DELETE /api/v1/faturas/{id}/                (DELETE cancela a fatura)
POST            /api/v1/faturas/{id}/emitir-cobranca/     (cria a cobrança no gateway)
GET|POST        /api/v1/fatura-itens/
GET|PUT|PATCH|DELETE /api/v1/fatura-itens/{id}/
GET|POST        /api/v1/pagamentos/                       (conciliação manual)
GET|DELETE      /api/v1/pagamentos/{id}/                  (DELETE estorna)
GET             /api/v1/financeiro/alunos/{aluno_id}/     (ficha financeira: totais + históricos)
POST            /api/v1/financeiro/webhooks/asaas/        (sem auth, por token; ver FINANCEIRO.md §6)

GET|POST        /api/v1/responsaveis/                     (contas do portal, vistas pelo staff)
GET             /api/v1/responsaveis/{id}/
POST            /api/v1/responsaveis/{id}/convidar/       (dispara o convite por email)
GET|POST|DELETE /api/v1/vinculos-responsavel/             (vínculo responsável × aluno; sem PUT/PATCH;
                                                           ?aluno= ou ?responsavel= obrigatório no list)

GET             /api/v1/boletins/aluno/{aluno_id}/        (agregação read-only)
GET             /api/v1/boletins/aluno/{aluno_id}/pdf/
GET             /api/v1/boletins/aluno/{aluno_id}/avaliacoes/
GET             /api/v1/timeline/aluno/{aluno_id}/        (?data_inicio=&data_fim=)

GET             /api/v1/relatorios/frequencia/            (?turma= obrigatório; ?formato=json|pdf|csv|xlsx)
GET             /api/v1/relatorios/dashboard/             (?turma=; só JSON)
```

**Portal do responsável** — autenticação própria, isolada do staff: o token de um
lado é recusado pelo outro (ver [`PORTAL.md`](./PORTAL.md) §4.1). Tudo sob
`/api/v1/portal/` e **só leitura** depois do login.

```
POST   /api/v1/portal/auth/login/           — par de tokens com claim tipo=responsavel
POST   /api/v1/portal/auth/refresh/         — rotaciona (o cliente guarda o novo)
POST   /api/v1/portal/auth/logout/
POST   /api/v1/portal/auth/senha/esqueci/   — pede o link (público)
POST   /api/v1/portal/auth/senha/definir/   — define a senha pelo token do convite/link
GET    /api/v1/portal/me/                   — identidade do responsável logado

GET    /api/v1/portal/alunos/                        — só os filhos vinculados
GET    /api/v1/portal/alunos/{id}/
GET    /api/v1/portal/alunos/{id}/boletim/
GET    /api/v1/portal/alunos/{id}/ocorrencias/
GET    /api/v1/portal/alunos/{id}/materiais/         — só a turma atual do filho
GET    /api/v1/portal/alunos/{id}/faturas/           — leva o link_pagamento a quem paga
GET    /api/v1/portal/periodos/
GET    /api/v1/portal/comunicados/
GET    /api/v1/portal/comunicados/{id}/
```

> Todos os endpoints (exceto `/auth/token/` e `/auth/token/refresh/`) exigem `Authorization: Bearer <access_token>`. O queryset retornado é sempre escopado à escola do usuário autenticado.

---

## Frontend

Single-Page Application em React 19 + TypeScript que consome a API REST do backend. Roda em `http://localhost:5173/` em desenvolvimento.

### Páginas

| Rota | Descrição |
|---|---|
| `/login` | Autenticação contra `/auth/token/` |
| `/esqueci-senha` · `/redefinir-senha` | Fluxo público de reset por email (link do Brevo) |
| `/conta/senha` | Trocar a própria senha |
| `/dashboard` | Saudação personalizada + filtro por turma + cards (ocorrências em aberto, alunos ativos, presença média, reincidência, última chamada por turma, últimas ocorrências, aulas aguardando visto). Cada card é clicável |
| `/alunos` | CRUD de alunos com busca por nome/matrícula; toggle "Mostrar inativos"; ⋯ leva à timeline, ao boletim e à ficha financeira |
| `/alunos/:id/timeline` | Timeline do aluno: ocorrências, presença e mudanças de cadastro em ordem cronológica, com filtro de janela e agrupamento por mês |
| `/turmas` | CRUD de turmas com contagem de alunos por turma |
| `/turmas/:id` | Detalhe da turma: alunos vinculados + atalhos pros relatórios de frequência e lista da turma e pro financeiro da turma |
| `/disciplinas` | CRUD de disciplinas |
| `/professores` | CRUD de professores (cria Usuario + Professor + Lecionamentos); soft delete; envio do link de senha pelo ⋯ |
| `/professores/:id` | Ficha 360º do professor: tabs Diário / Lecionamentos / Ocorrências / Dados, com filtros de período e status, agrupamento por mês, conferência das aulas e export do diário em PDF |
| `/planos-ensino` | Lista de planos com status (preenchido/em branco/inativo) |
| `/planos-ensino/:id` | Editor longo em seções (Programação / Execução / Situação) |
| `/ocorrencias` | Lista ordenada por status (abertas → arquivadas) + data desc; filtro de status em múltipla escolha; export no mesmo recorte |
| `/ocorrencias/:id` | Detalhe com botões rápidos de mudança de status; editar/excluir num dropdown discreto |
| `/presenca` | Lista de chamadas por turma e data |
| `/presenca/:id` | Tela da chamada com resumo P/A/J/R e edição inline por aluno (optimistic update) |
| `/diario` | Diário de aula do professor: agenda do mês projetada da grade horária, lançamento do conteúdo e estado de conferência |
| `/avaliacoes` | Lista de avaliações por turma/disciplina/período, com contadores de notas lançadas |
| `/avaliacoes/:id` | Lançamento de notas em lote da avaliação (grade de todos os alunos da turma) |
| `/notas-finais` | Média final por aluno × disciplina × período — o que vai no boletim |
| `/configuracao/periodos` | Períodos avaliativos da escola (bimestre/trimestre/semestre) |
| `/comunicados` | Lista de comunicados (rascunhos primeiro, depois falhas, enviados por último); filtro por status; botão "Enviar" nas linhas em rascunho |
| `/comunicados/:id` | Detalhe com a mensagem, autoria e o log de entrega por responsável (enviados / falhas / sem email), filtrável |
| `/mural` | Mural de materiais: professor publica só nos próprios lecionamentos ativos; direção escolhe o professor e modera |
| `/responsaveis` | Contas de acesso ao portal: situação do acesso (sem convite / convidado / expirado / ativo / inativo), botão Convidar, cadastro de responsável e gerência dos vínculos com os alunos |
| `/usuarios` | Contas do staff: busca, badge de perfil, toggle "Mostrar inativos", criação/edição, envio do link de senha, (des)ativação. Lista os professores junto, com o ⋯ linkando pra ficha |
| `/financeiro` | Faturas da escola (aba interna) — detalhe em dialog, registro de pagamento, estorno, cancelamento, emissão da cobrança no gateway e "Nova fatura" avulsa |
| `/financeiro/planos` | Planos de cobrança (aba interna): contrato do aluno, com select de pagador alimentado pelos vínculos do próprio aluno |
| `/financeiro/alunos/:id` | Ficha financeira do aluno: quatro contadores (em aberto, vencido, a cobrar hoje, pago no ano) sobre contratos, faturas e pagamentos |
| `/import` | Import/export em massa CSV/XLSX das 6 entidades (gated por flag da escola) |
| `/boletim/:alunoId` | Boletim agregado do aluno (frequência + notas + ocorrências) com layout de impressão e export em PDF |

**Portal do responsável** — árvore separada sob `/portal`, em chunk próprio
(`React.lazy` no `App.tsx` divide a árvore do staff da do portal), com sessão
independente (storage `portal_*`, instância de axios própria) e telas
mobile-first:

| Rota | Descrição |
|---|---|
| `/portal/entrar` | Login do responsável (contra `/portal/auth/login/`) |
| `/portal/esqueci-senha` · `/portal/definir-senha` | Pede e define a senha (é por aqui que o link do convite entra) |
| `/portal/` | Início: os filhos vinculados e os últimos comunicados |
| `/portal/alunos/:id` | Página do filho, em abas: boletim, ocorrências, mural de materiais e mensalidades (com o link de pagamento) |
| `/portal/comunicados` · `/portal/comunicados/:id` | Comunicados que alcançaram os filhos |

Botões de criação/edição/exclusão em cadastros (Alunos, Turmas, Disciplinas, Professores) só aparecem para admin/diretor — controlado por `usePermissoes`.

### Camadas

- **`features/auth`** — `AuthProvider` com login/logout, decode do JWT (jwt-decode), tokenStorage em `localStorage`, `useAuth` hook.
- **`lib/api.ts`** — instância única do axios. Request interceptor injeta `Authorization: Bearer`. Response interceptor detecta 401 → chama `/auth/token/refresh/` → refaz request original (com promise compartilhada para evitar thundering herd em queries paralelas).
- **`lib/queryClient.ts`** — TanStack Query configurado com `staleTime` 30s, retry desabilitado pra 401/403.
- **`features/<dominio>/hooks.ts`** — `useXxx`, `useCreate`, `useUpdate`, `useDelete` com invalidação automática de cache + toasts via sonner.
- **`components/ui/`** — código copiado pelo shadcn CLI (Button, Input, Card, Dialog, Table, Select, DropdownMenu, Sonner, AlertDialog, etc.). Editável livremente.
- **`lib/datas.ts`** — `hojeISO()` e os três formatadores de data, cujo nome diz o tipo do campo no backend: `formatarDataPura` pra `DateField` (split da string, porque `new Date("2026-03-10")` é lido como UTC e volta como dia 9), `formatarDataHora` pra `DateTimeField` (aí `new Date` é o certo — a string do DRF traz offset) e `formatarDiaDaDataHora` pro `DateTimeField` exibido só como dia. Consolidou 14 cópias locais espalhadas em 13 arquivos. O `hojeISO()` existe porque `toISOString().slice(0, 10)` converte pra UTC e, das 21h em diante num fuso negativo, devolve **amanhã** — e ocorrência e chamada recusam data futura no backend, então o turno noturno recebia formulário que o servidor rejeitava.
- **`lib/download.ts`** — `baixarArquivo()`: download autenticado via Blob (`window.location` perderia o Bearer). Usado por boletim, diário e relatórios. Desembrulha o corpo de erro, que com `responseType: "blob"` chega como Blob — sem isso a mensagem que o backend escreve ("recorte grande demais pro PDF") nunca chegaria no toast.
- **`portal/`** — a árvore do responsável, separada por `React.lazy` no `App.tsx`: sessão própria (storage `portal_*`, instância de axios que guarda o refresh rotacionado) e identidade lida de `/portal/me/` por **query do TanStack**, não por `useEffect`.
- **`test/`** — harness dos testes de componente (vitest + jsdom + testing-library + MSW). `renderizar()` monta os três contextos que as telas exigem (Query com `retry: false`, rota e auth); `autenticar.ts` semeia sessão forjando um JWT no localStorage — funciona porque o front **nunca** valida assinatura; `servidor.ts` nasce sem handler nenhum, e cada teste declara os endpoints que usa.

### Identidade visual

Light mode permanente com paleta de marca **Diário Diniz**: olive como cor primária (CTAs, sidebar), linho como fundo principal (papel), paper (off-white) em cards e inputs, ferrugem como accent quente (filetes, foco, indicadores), tinta + sepia como texto. Os tokens vivem em `src/index.css` como CSS variables e estão mapeados pros tokens do shadcn (`--background`, `--primary`, `--card`, etc.) — qualquer componente shadcn off-the-shelf herda automaticamente. A fonte da verdade visual da marca (tokens, voz, componentes cristalizados, anti-patterns) vive em [`DESIGN.md`](./DESIGN.md).

Tipografia mista: **Fraunces** (serif variável) em títulos via `font-heading`, **Geist** (sans) no corpo. A combinação dá tom editorial sem perder legibilidade. A varredura terminou: listagens, detalhes e formulários estão todos no padrão do `DESIGN.md` §7 — header em Fraunces + filete ferrugem + eyebrow mono + tabelas em `bg-paper`, dialogs com label mono.

Status badges 100% na paleta da marca (ocorrências, comunicados, presença, faturas) — sem amber/blue/green/red genéricos do Tailwind. O "em curso / rascunho / atenção sem urgência" virou token (`bg-mostarda text-ambar`), depois de nove usos do mesmo hex espalhados por dez arquivos; a presença ficou fora de propósito, porque os tons dela são outros e têm estado de hover.

**Erro de leitura não vira estado vazio.** No TanStack Query o `isLoading` volta a `false` quando a query **falha**, então o skeleton sai e o componente renderiza o ramo de lista vazia — a tela apresenta falha de rede como resposta do servidor ("nenhum pagamento registrado"). Todo ramo de vazio vem **depois** de um ramo de `isError`. Em form de edição o estrago é maior: o campo abre vazio **e habilitado** sobre um registro que existe, e salvar dali apaga o que estava no banco — ali a correção é travar a escrita, não trocar a mensagem. Nos dialogs, a lista que popula um `<Select>` falha e a validação de submit responde "Selecione uma turma", culpando o usuário por uma falha de rede: o aviso é o `AlertaOpcoesIndisponiveis`, um componente só, porque a frase tem que ser uma só.

Layout responsivo: a sidebar fixa (≥768px) vira um drawer (`Sheet`) com botão hamburguer abaixo de 768px. Padding e tipografia ajustam por breakpoint (`p-4 md:p-8`, `text-2xl md:text-3xl`). Headers de detalhe com muitas ações empilham até `lg` (1024px) pra evitar competição visual em tablet portrait. Tabelas escondem colunas secundárias em telas estreitas (`hidden sm:table-cell` / `md:` / `lg:`) em vez de scroll horizontal — os dados completos ficam acessíveis clicando na linha (vai pro detalhe). Funciona em celular (chamada de presença em sala) e tablet.

Soft delete UX: listagens com soft delete (Aluno) escondem inativos por padrão. Toggle `Switch` "Mostrar inativos" na `AlunosPage` inverte e mostra só os inativos com badge `[ inativo ]`. Selects de criação (ex.: nova ocorrência) ficam restritos a ativos. Telas que apenas resolvem nome de aluno em registros antigos (ocorrências, presenças, comunicados) carregam todos os alunos pra não quebrar histórico.

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
- Antes de abrir PR frontend: `npm --prefix frontend test && npm --prefix frontend run build`.
- O CI roda os dois, e **`npm run lint` é gate**: lint sujo reprova a PR.
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
- **Audit log:** `django-simple-history` nos **21 modelos** do núcleo (Usuario, Aluno, Professor, Lecionamento, Ocorrencia, RegistroPresenca, ItemPresenca, PlanoEnsino, RegistroAula, PeriodoAvaliativo, Avaliacao, NotaAvaliacao, NotaPeriodo, Comunicado, Material, Responsavel, ResponsavelAluno, PlanoCobranca, Fatura, FaturaItem, Pagamento) com aba History no `/admin/` mostrando diff lado a lado. Ficam fora `Escola`, `Turma` e `Disciplina`, que mudam raramente e não têm valor de auditoria. `populate_history --auto` no boot pra marco-zero dos registros anteriores ao audit log.
- **Comunicação:** notificação por email ao responsável funcional em produção via **Brevo HTTP API** (`django-anymail`) — off-thread, protegido, sem domínio próprio, 300 emails/dia free. Resend e Gmail SMTP foram tentados e falharam pelo bloqueio de SMTP outbound do Render free desde set/2025. **Outbox com retry e histórico** (`apps/notificacoes`): os quatro caminhos que não deixavam rastro agora gravam a mensagem antes de tentar enviar, e o reenvio é um command. Não é fila de broker de propósito — Celery/Dramatiq/RQ exigiriam Redis e um segundo processo, e o free tier dá um web service só.
- **Tarefas periódicas:** o projeto não tinha agendador em ambiente nenhum, então os commands de cron existiam sem nunca rodar. O gatilho é `POST /api/v1/tarefas/executar/` chamado por workflow agendado no GitHub Actions — gratuito, sem provedor novo, e de quebra acorda o serviço que hiberna no free tier.
- **Observabilidade:** Sentry SDK no backend e frontend — captura exceções não tratadas + `logger.error/exception` + erros de render React via `<Sentry.ErrorBoundary>`. Plano free (Developer) 5k events/mês.
- **Produto:** Dashboard com métricas (7 cards, incluindo presença média e reincidência agregadas no backend) + filtro por turma; **avaliações e notas** (período avaliativo, avaliação, lançamento em lote, média final); **diário de classe** com visto da direção, agenda projetada da grade horária e PDF; **boletim** com PDF; **timeline do aluno**; **relatórios operacionais** em PDF/CSV/XLSX (frequência por turma, ocorrências, cadastral de alunos); **comunicados institucionais** com log de entrega por responsável; **mural de materiais**; **portal do responsável** (oito fatias, ver [`PORTAL.md`](./PORTAL.md)); **financeiro** completo, do contrato ao webhook de conciliação (ver [`FINANCEIRO.md`](./FINANCEIRO.md)); fluxo de senha completo (própria, esqueci, e a direção dispara o link de terceiro); gestão de contas do staff pela UI; soft delete + UX completa (toggle "Mostrar inativos" + Reativar); auto-escopo de escola em criação (multi-tenant invisível pro usuário); **import/export em massa CSV/XLSX** (6 entidades via `django-import-export`) com gating comercial por escola (flag `importacao_em_lote_habilitada`).
- **Performance:** auditoria de queries fechada — índices simples e compostos, `annotate` no lugar de `COUNT` por linha, `bulk_*_with_history` no lançamento de notas, `Prefetch` do histórico, paginação nas listas navegáveis e **filtro de escopo obrigatório** nos endpoints matriz (a alternativa a paginar, que quebraria a chamada e o lançamento em lote).
- **Identidade visual:** paleta de marca olive/linho/ferrugem com tokens semânticos, tipografia Fraunces + Geist em hierarquia editorial, light mode permanente e a varredura de telas concluída (listagens, detalhes e formulários). Fonte da verdade em [`DESIGN.md`](./DESIGN.md).
- **Testes:** 1.076 testes no backend; no frontend, testes de função pura e de componente (vitest + jsdom + testing-library + MSW), rodando no mesmo `npm test` que o CI executa.

## Backlog (não implementado)

A lista priorizada por fases vive em [`CLAUDE.md`](./CLAUDE.md) (seção Roadmap). Resumo do que ainda falta:

- **Comunicação:** telefone do responsável — é outro canal e outro provedor. O retry e o histórico do email saíram do backlog com o outbox; o que fica de fora dele é o `comunicados`, que tem outbox próprio e lote rodando em produção.
- **Operação:** os dois secrets do workflow agendado (`BACKEND_URL` e `TAREFAS_TOKEN`) e a env `TAREFAS_TOKEN` no servidor precisam ser preenchidos — sem eles o job termina avisando em vez de falhar, então o silêncio não aparece como vermelho. `ProtectedError` ainda sai como 500 em vez de 4xx: falta um exception handler em `apps/common/`.
- **Produto:** o PDF do WeasyPrint segue síncrono na request. O outbox não resolve isso (ele é pra email), então o teto de linhas continua sendo a proteção do worker.
- **Produto:** PWA (empacotar o front atual com manifest + service worker, pra chamada em sala e pro portal no celular) é consideração, não compromisso — o divisor de esforço é a chamada precisar ou não funcionar **offline**. Editar nome/email de responsável pela tela segue pelo `/admin/`.
- **Dev experience:** drf-spectacular (gera client TypeScript), `repositories.py` por app quando houver query compartilhada entre services.
- **SaaS futuro:** multi-tenancy real (middleware + RLS + billing), httpOnly cookies, LGPD formal.
