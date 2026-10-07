# CLAUDE.md — Diário Escolar

Guia operacional para agentes de IA (e humanos) trabalhando neste repositório.
Cobre visão do produto, mapa do código, guardrails e roadmap. Leia antes de
escrever qualquer código.

---

## 1. Visão do produto

Diário Escolar é um **sistema administrativo procedural** para gestão
disciplinar, presença e rastreabilidade escolar. O foco NÃO é ser um ERP
escolar completo nem uma plataforma de ensino (LMS/EdTech).

> Posicionamento: ERP administrativo escolar procedural — gestão disciplinar,
> presença e rastreabilidade. Não é LMS, não é app do aluno, não é EdTech.

Decidido em out/2026: existe um **portal de leitura para o responsável**
(ver [`PORTAL.md`](./PORTAL.md)) — o pai acompanha comunicados, boletim,
ocorrências e o mural de materiais dos filhos vinculados. Isso **não**
torna o produto um app do aluno nem um LMS: o aluno continua sem login, e
o portal é só leitura (nada de entrega de atividade, correção ou chat).
A ressalva de posicionamento acima segue valendo com essa única exceção —
não a use pra justificar outras frentes de EdTech.

Meta de curto prazo: **1 escola usando o sistema de verdade** antes de expandir
escopo. Prioridade em estabilidade, rastreabilidade, deploy e UX administrativa.

Arquitetura single-tenant hoje, com base abstrata preparada para row-level
multi-tenancy (SaaS) sem retrofit doloroso.

---

## 2. Stack

**Backend:** Django 5.2 + Django REST Framework · PostgreSQL (psycopg 3) ·
SimpleJWT (claims customizados) · django-filter · python-decouple ·
django-cors-headers · **django-simple-history** (audit log) ·
**django-anymail[brevo]** (email via HTTP API) · **sentry-sdk[django]**
(error tracking, gated por `SENTRY_DSN`).

**Frontend:** Vite 8 · React 19 · TypeScript · Tailwind CSS 4 + shadcn/ui
(tokens semânticos mapeados pra paleta de marca olive/linho/ferrugem) ·
**Fraunces** (serif variable) em títulos + **Geist** (sans) no corpo ·
React Router 7 · TanStack Query 5 · axios (interceptors Bearer + refresh) ·
sonner (toasts) · jwt-decode · **@sentry/react** (error tracking + ErrorBoundary,
gated por `VITE_SENTRY_DSN`).

**Ambiente do Diniz:** Windows + PowerShell. Banco de teste em Docker
(`docker start diario_pg_test`). Venv em `.venv/Scripts/python.exe`.

---

## 3. Mapa do código ("cada centímetro")

### Backend — `apps/`

**`common/`** — base compartilhada, sem modelos de domínio próprios.
- `TimeStampedModel` — `criado_em` / `atualizado_em`.
- `BaseModelEscopado` — `TimeStampedModel` + FK `escola`. Base de todo modelo de domínio.
- `EscopoEscolaMixin` (views) — filtra queryset pela escola do usuário autenticado.
- `ReadWritePermissionMixin` (views) — resolve permissão por ação: `list`/`retrieve` usam `READ_PERMISSION`, o resto usa `WRITE_PERMISSION`.
- `FiltroEscopoObrigatorioMixin` (views) — recusa (400) `list` sem nenhum dos `FILTROS_ESCOPO` do viewset. Usado nos endpoints **matriz** (`NotaAvaliacao`, `NotaPeriodo`, `ItemPresenca`) que a UI sempre consome escopados (`?avaliacao=`/`?registro=`/...) e cujas telas (lançar em lote, chamada) precisam de todos os alunos de uma vez — paginar quebraria a UX, então limitamos a carga exigindo escopo. Levanta `ImproperlyConfigured` se `FILTROS_ESCOPO` ficar vazio. Não afeta `retrieve` nem actions custom.
- `permissions.py` — `IsAdmin`, `IsAdminOrDiretor`, `IsAdminOrDiretorOrProfessor`, `IsAdminOrDiretorOrProfessorOrInspetor`. Admin/superuser têm bypass total. **Aliases de perfil**: `secretaria` **e `coordenador`** operam como `diretor` (fazem cadastros, gerenciam usuários); `inspetor` opera como `professor` (lança ocorrência e chamada). A distinção entre eles é só rótulo de UX (sidebar/Dashboard mostram "Secretaria"/"Coordenador"/"Inspetor" via `PERFIL_LABEL` no front) — decisão consciente pra escala de escola pequena/média onde os papéis são fluidos. Quando crescer pra rede grande e fizer sentido separar, basta refinar as classes — os perfis já existem distintos no enum `Usuario.Perfil`.
- `serializers.py` — helpers compartilhados pra escopo de escola:
  - `AutoEscopoEscolaSerializerMixin` — sobrescreve `to_internal_value` pra injetar `escola=request.user.escola_id` no payload quando o usuário tem escola no JWT e o campo foi omitido. Roda ANTES de validators (UniqueTogether incluso). Quando o user não tem escola (admin global), o `extra_kwargs={"escola":{"required":False}}` do serializer e o `validate_escola` cuidam de devolver 400 explícito se ainda assim faltar. Aplicado em todos os 9 serializers com FK `escola`.
  - `validate_escola_do_usuario(value, request, mensagem)` — guard de IDOR: admin/superuser passa qualquer escola; não-admin só pode escrever na própria. Substituiu o copy-paste de 4 serializers que tinham essa lógica.
- Validator de CNPJ com dígito verificador.

**`accounts/`** — identidade e autenticação.
- `Usuario(AbstractUser)` — `perfil` (admin/diretor/professor/secretaria/coordenador/inspetor) + FK opcional `escola`. **Auditado** (`HistoricalRecords(excluded_fields=["last_login"])` — `last_login` ficaria barulhento, o resto vai pro histórico inclusive `password` hash).
- `UsuarioSerializer` — inclui `escola` nos fields (necessário pra criar Professor).
- `UsuarioTokenObtainPairView` / `...Serializer` — JWT com claims `escola_id`, `perfil`, `username`, `first_name`, `last_name`.
- `/usuarios/` restrito a admin/diretor (via `IsAdminOrDiretor`, que cobre também secretaria/coordenador como aliases).
- **Fluxo de senha completo**: público (`/auth/password/reset/request|confirm/`), próprio usuário logado (`/auth/password/change/`) e **action de direção** (`POST /usuarios/<id>/enviar-reset-senha/`) que dispara o mesmo link de redefinição em nome do alvo. Toda a plumbing reusa `PasswordResetToken.gerar()` + `services.enviar_link_redefinicao()`. A action tem guard de IDOR inline (não-admin só dispara reset pra alguém da própria escola). Frontend: `useEnviarResetSenha` + item no ⋯ da `ProfessoresPage` + botão na header da `ProfessorDetalhePage`.

**`escola/`** — núcleo do domínio. Cinco modelos:
- `Escola` — tenant root; CNPJ validado; `on_delete=PROTECT`. **Não auditado** (muda raramente).
- `Turma` — turno + ano_letivo; única por `(escola, nome, ano_letivo)`. **Não auditado**.
- `Disciplina` — única por `(escola, nome)`; campo `ativa`. **Não auditado**.
- `Aluno` — não loga; matrícula única por escola; invariante turma/escola. **DELETE = soft delete** (`ativo=False`); o front esconde inativos por padrão e oferece toggle "Mostrar inativos" + ação "Reativar" (PATCH `ativo=true`). Tem `nome_responsavel` + `email_responsavel` (obrigatórios no serializer, `blank` no banco pros antigos) — destino da notificação de ocorrência. **Auditado** (`HistoricalRecords()`).
- `Professor` — OneToOne com `Usuario(perfil=professor)`; `ativo`; invariante `usuario.escola == professor.escola`. **Auditado**.
- `Lecionamento` — vínculo granular **professor × turma × disciplina** (substituiu a antiga M2M `Professor.disciplinas`). `ano_letivo` derivado da turma. Unique `(professor, turma, disciplina)`. `clean()` valida escola alinhada nos três. `CASCADE` no professor, `PROTECT` em turma/disciplina. Tem `dias_semana` (`ArrayField` de inteiros, 0=segunda…6=domingo, alinhado a `date.weekday()`) — grade horária que serve de base pra projetar os slots do diário de aula (app `aulas`). **Auditado**.

**`ocorrencias/`** — `Ocorrencia` (turma + aluno + professor opcional + descrição + data + status `aberta`/`em_andamento`/`resolvida`/`arquivada`). Invariantes em `clean()` + serializer. Permissão uniforme admin/diretor/professor. Guard de IDOR no payload `escola`. **Auditado**. **`services.py`**: `notificar_responsavel_ocorrencia` é disparado em `perform_create` e roda numa **thread daemon** (fire-and-forget — POST volta na hora, sem pendurar a resposta HTTP). Em `TESTING` o envio é síncrono pra manter `mail.outbox` determinístico. Destinatários vêm de `apps/portal/destinatarios.py` — um aluno com mãe e pai vinculados recebe **duas mensagens individuais**, cada uma saudada pelo nome do responsável, e a falha de uma não cala a outra. Aluno sem responsável com email é pulado (log warning). Falha de envio é logada com stack trace, nunca propagada. Em produção o backend é `anymail.backends.brevo.EmailBackend` (HTTP API porta 443) — ver Infra.

**`presenca/`** — chamada.
- `RegistroPresenca` — chamada de uma turma num dia; única por `(escola, turma, data)`. **Auditado**.
- `ItemPresenca` — status por aluno (`P`/`A`/`J`/`R`). **Único `CASCADE` do projeto** (filho do registro). **Auditado**.
- Auto-geração: criar registro gera um `ItemPresenca(P)` por aluno ativo da turma, em transação atômica.
- `ItemPresencaViewSet` não expõe POST/DELETE (ciclo de vida pertence ao pai). Leitura inclui inspetor.

**`portal/`** — portal do responsável (ver [`PORTAL.md`](./PORTAL.md)).
`Responsavel` herda `AbstractBaseUser` **sem** ser `AUTH_USER_MODEL` (o
projeto só tem um, e é `accounts.Usuario`) — ganha hash de senha e
`last_login`, mas nada aqui passa pelos backends de auth do Django, então
o `is_active` da base é irrelevante: quem manda é o campo `ativo`. Email
normalizado no `save()` (lowercase+strip), unique por `(escola, email)`.
`ResponsavelAluno` é o vínculo M2M (resolve "múltiplos responsáveis"),
`PROTECT` nos dois lados, `clean()` exige escola igual, **auditado** — é o
modelo que decide quem vê os dados de quem. `destinatarios.py` é a
**origem única de quem recebe email** (ocorrência e comunicado chamam de
lá): resolve pelos vínculos, pula conta inativa, e só cai no
`Aluno.email_responsavel` quando o aluno não tem vínculo **nenhum** — ver
`RESPONSAVEIS.md` §4.1, é a armadilha central da frente. Semeadura:
`manage.py portal_semear_responsaveis`. **Fatia 6 entregue**: frontend do
portal sob `/portal`, em chunk próprio (`React.lazy` no `App.tsx` separa a
árvore do staff da do portal), sessão independente em
`features/portal/` (storage `portal_*`, `portalApi` que guarda o refresh
rotacionado, `PortalAuthContext` lendo `/portal/me/`) e seis telas
mobile-first em `src/portal/`. Backend entregue até a fatia 5:
autenticação isolada (`/api/v1/portal/auth/`, tokens com `tipo=responsavel`
e `responsavel_id` — o staff recusa), convite e senha (`ConviteResponsavel`,
comando `portal_convidar_responsaveis`) e leituras em `leituras.py`, todas a
partir dos vínculos (`filhos_do`). **Nenhum convite em produção antes da
fatia 6** (o link cai numa tela que ainda não existe).

**`materiais/`** — mural do professor pra turma (fatia 5 do `PORTAL.md`).
`Material` = turma + disciplina + professor + título + descrição + link
(só http/https, sem upload). **Auditado**. Mesmo molde do `RegistroAula`:
`Lecionamento` ativo obrigatório, professor só vê/edita os próprios e não
publica em nome de outro (403), direção vê a escola toda. `DELETE` = soft
delete (`ativo=False`). O portal lê em `/portal/alunos/<id>/materiais/`
(só a turma atual do filho; filho desativado vê lista vazia). Tela do
staff: `MuralPage` em `/mural` (fatia 5b) — professor publica só nos
próprios lecionamentos ativos, direção escolhe o professor e modera.

**`tarefas/`** — esqueleto vazio (só `__init__.py`/`apps.py`/`migrations`). Feature **removida** do produto; frontend não tem `TarefasPage` nem feature `tarefas/`. Diretório mantido pra não quebrar migrations históricas.

**`planos_ensino/`** — `PlanoEnsino` (ementa, conteúdo programático, objetivos, habilidades BNCC, carga horária, metodologia, recursos, avaliação, `ativo`). Único por `(escola, turma, disciplina, ano_letivo)`. Casca criada num dialog; campos longos preenchidos na tela de detalhe. **Auditado**.

**`boletins/`** — **sem modelo próprio**. `services.py` agrega on-the-fly; `BoletimAlunoView` (APIView) expõe `GET /boletins/aluno/<id>/`. Justificado (J) conta como presença efetiva na frequência.

**`aulas/`** — diário de classe (conteúdo ministrado por aula). `RegistroAula` = turma + disciplina + professor + data + `conteudo` (texto livre) + `status` (`rascunho`→`lancado`→`conferido`) + `conferido_por`/`conferido_em` (visto da direção). Quarto conceito ao lado de `PlanoEnsino` (planejado no ano), `Tarefa` (atividade do aluno) e `RegistroPresenca` (quem veio) — registra "o que foi dado na aula do dia". Único por `(escola, turma, disciplina, data)`. **Auditado**. `clean()`/serializer: escola alinhada, **`Lecionamento` ativo obrigatório** pro trio, data não-futura, conteúdo exigido ao lançar. Viewset escopado (direção vê a escola toda; professor/inspetor só os próprios); `perform_create` bloqueia (403) lançar em nome de outro. Action `conferir` (só direção) move `lancado`→`conferido` e grava quem/quando — o serializer recusa `status=conferido` (sem auto-conferência); aula conferida trava edição. Action `agenda` (`?turma=&disciplina=&mes=YYYY-MM`) projeta os slots do mês a partir de `dias_semana` do `Lecionamento`, on-the-fly (sem tabela), via `services.py`. **Completo: backend #89; front — diário do professor #90, ficha do professor #91, PDF #94 + redesenho do PDF #97, card no dashboard #93.**

### Frontend — `frontend/src/`

- **`features/<dominio>/hooks.ts`** — TanStack Query: `useXxx` (list), `useCreate`, `useUpdate`, `useDelete`/`useDeactivate`, com invalidação de cache + toast. Domínios: `alunos`, `auth`, `boletins`, `dashboard`, `disciplinas`, `escolas`, `lecionamentos`, `ocorrencias`, `planos-ensino`, `presenca`, `professores`, `turmas`, `usuarios`, `comunicados`.
- **`features/auth/`** — `AuthProvider`, `useAuth`, `usePermissoes` (regra de UI por perfil; `podeModificarCadastros` = admin/diretor), tokenStorage em localStorage, decode JWT. `user.escola_id` é o sinal usado pelos FormDialogs pra decidir se renderiza o select de escola.
- **`lib/api.ts`** — axios único. Request interceptor injeta Bearer. Response interceptor: 401 → refresh → refaz request (promise compartilhada contra thundering herd).
- **`lib/queryClient.ts`** — staleTime 30s, retry off pra 401/403.
- **`components/AppLayout.tsx`** — shell: sidebar fixa olive-dark em ≥768px, drawer (`Sheet`) com hamburguer em <768px. Logo "Diário Diniz" em Fraunces no topo + perfil em mono uppercase + nav com barra ferrugem no ativo + rodapé com filete ferrugem + logout + versão.
- **`components/ui/`** — shadcn (editável). `Sheet` e `Switch` foram adicionados manualmente (CLI travava em prompt).
- **`index.css`** — paleta de marca em CSS variables no `:root` (`--olive`, `--olive-dark`, `--linho`, `--paper`, `--ferrugem`, `--tinta`, `--sepia`, `--creme`) + mapeamento dos tokens shadcn (`--background`, `--primary`, etc.) pra paleta. Light mode permanente (sem `.dark` block). `color-scheme: light` + meta tag desabilitam force-dark dos browsers.
- **~25 pages** — Login, Dashboard, Alunos, Turmas (+detalhe), Disciplinas, Professores (+detalhe — ficha 360º), PlanosEnsino (+detalhe), Ocorrencias (+detalhe), Presenca (+detalhe), Avaliacoes (+detalhe), PeriodosAvaliativos, NotasFinais, DiarioAula, Boletim, Import, ContaSenha/EsqueciSenha/RedefinirSenha, NotFound, Placeholder. **Todas no padrão visual `DESIGN.md`** (Fraunces + filete ferrugem + eyebrow mono + `bg-paper`), inclusive listagens/detalhes/forms. Polidas em ondas: Login/Sidebar/Dashboard (PRs #50-#52), depois listagens e detalhes ao longo de jun/2026.
- **`types/api.ts`** — interfaces espelhando os serializers (mantido à mão; drf-spectacular no backlog). Todos os `*Input` com FK `escola` têm o campo opcional (`escola?: number`) — backend deduz pelo JWT quando ausente.

### Padrões de UI consolidados

- **Linha de tabela clicável** leva ao detalhe; dropdown ⋯ (Editar/Excluir) com `e.stopPropagation()` na célula.
- **Tabelas responsivas**: colunas secundárias somem com `hidden sm:table-cell` / `hidden md:table-cell` / `hidden lg:table-cell` em vez de scroll horizontal grosso.
- **Optimistic update** na chamada de presença (snapshot + rollback).
- **Light mode permanente** com paleta de marca olive/linho/ferrugem (sem toggle de tema).
- **Tipografia mista**: Fraunces (serif) em títulos via `font-heading`, Geist (sans) no corpo. Tom editorial com legibilidade técnica.
- **Padding/typography responsivos**: `p-4 md:p-8` (ou `md:p-10` no Dashboard), `text-2xl md:text-3xl`.
- Botões de escrita (Novo/Editar/Excluir) escondidos pra não-admin/diretor via `usePermissoes`.
- **Header de detalhe com muitas ações**: stack vertical até `lg` (1024px), row a partir daí. Usado na `OcorrenciaDetalhePage` pra evitar o título competir com 3 botões + dropdown em tablet portrait/mobile.
- **Filtro de inativos**: padrão em listagens com soft delete = só ativos. Toggle `Switch` (shadcn) "Mostrar inativos" inverte e mostra só os inativos. Linhas de inativo ganham badge `[ inativo ]` e o ⋯ troca "Excluir" por "Reativar". Aplicado em `AlunosPage`. Mesmo princípio nas contagens (`TurmasPage`, `TurmaDetalhePage`) e nos selects de criação (`OcorrenciaFormDialog`): só ativos.
- **Resolução de nome em registros antigos**: telas que apenas resolvem nome de aluno em ocorrência/presença/tarefa antigas (ex.: `OcorrenciasPage`, `OcorrenciaDetalhePage`, `TarefaDetalhePage`, `PresencaDetalhePage`, `UltimasOcorrenciasCard`) chamam `useAlunos()` SEM filtro de `ativo` — assim o nome de um aluno desativado depois ainda resolve.
- **Auto-escopo de escola nos FormDialogs**: cada `*FormDialog.tsx` lê `user.escola_id` do `useAuth`. Quando o user tem escola, o select de escola some e o payload omite `escola` — backend deduz pelo JWT. Admin global (sem `escola_id`) ainda vê o select e envia explícito.
- **Filete ferrugem como assinatura visual**: `h-px w-X bg-ferrugem` aparece debaixo de títulos em Login, Sidebar e Dashboard — marca de "encadernação" que conecta as telas visualmente.
- **Status badges com paleta da marca** (em vez de red/amber/green/blue genérico do Tailwind):
  - Ocorrência aberta → terracota clarinho + texto destructive.
  - Ocorrência em andamento → mostarda clarinho + texto âmbar.
  - Ocorrência resolvida → olive clarinho + texto olive.
  - Ocorrência arquivada → muted neutro.
  - Presença P/A/J/R → olive / terracota / mostarda / petrol pastel (em `presenca/constants.ts`).

### Infra / deploy (raiz)

- **`Dockerfile`** — backend multi-stage (`dev`/`prod`); `prod` roda `collectstatic` e usa `entrypoint.sh`.
- **`entrypoint.sh`** — produção: `migrate` + cria superusuário (via `DJANGO_SUPERUSER_*`) + **`populate_history --auto`** (backfill do audit log idempotente, dá marco-zero pros registros que existem antes do audit log entrar) + gunicorn. Necessário no free tier do Render (sem Pre-Deploy/Shell).
- **`docker-compose.yml`** (dev, hot reload) e **`docker-compose.prod.yml`** (gunicorn + nginx).
- **`frontend/Dockerfile`** (build Node → nginx) + **`nginx.conf`** + **`vercel.json`** (SPA).
- **`.github/workflows/ci.yml`** — testes backend + build frontend por PR.
- **`scripts/`** — backup/restore do Postgres. **`DEPLOY.md`** — guia Render+Vercel+Brevo.
- **Config por env** (decouple): `DATABASE_URL` (ou `DB_*`), `$PORT`, `GUNICORN_*`, `EMAIL_BACKEND`, `ANYMAIL_BREVO_API_KEY`, `DEFAULT_FROM_EMAIL`, `SECURE_SSL`, `CSRF_TRUSTED_ORIGINS`. Portável (Render hoje, AWS depois). Em testes, `settings.TESTING` desliga throttle e usa email locmem.
- **Email em prod via Brevo** — `EMAIL_BACKEND=anymail.backends.brevo.EmailBackend` + `ANYMAIL_BREVO_API_KEY=<key>`. **Por quê HTTP API, não SMTP**: o free tier do Render bloqueia outbound SMTP nas portas 25/465/587 desde set/2025. A API do Brevo trafega em HTTPS (porta 443) — sempre liberada. 300 emails/dia grátis pra sempre, sem domínio próprio (só verificar o sender). Pra trocar pra SendGrid/Mailgun/Postmark depois é só mudar `EMAIL_BACKEND` — `services.py` não muda.
- **Audit log via `simple_history`** — `HistoryRequestMiddleware` captura `history_user` automaticamente; cada modelo auditado tem tabela `*_historical`. Aba "History" no `/admin/` mostra diff lado a lado. Modelos não auditados: `Escola`, `Turma`, `Disciplina` (mudam raramente, sem valor comercial de auditoria).
- **Observabilidade via Sentry** — `sentry-sdk[django]` no backend e `@sentry/react` no front. Init condicional em `config/settings.py` e `frontend/src/main.tsx` (`if SENTRY_DSN`), então sem env definido o SDK fica inerte (dev local não precisa). `traces_sample_rate=0` em ambos (só errors, preserva quota free). `send_default_pii=False` por LGPD. Captura também `logger.error/exception` via `LoggingIntegration` default — útil porque `services.py` de ocorrencias usa `logger.exception` pra falha de email, então erro de envio em produção vira evento no Sentry sem mexer em nada.

---

## 4. Guardrails (NÃO violar)

### Segurança
- Nunca expor secrets/tokens/senhas em código ou logs. Config sensível só via env. Nunca commitar `.env`.
- Senhas: PBKDF2-SHA256 (padrão Django, hash one-way). Nunca logar nem tentar reverter.
- Queries parametrizadas sempre — nunca interpolação de string.
- Manter o guard de IDOR (`validate_escola` nos serializers) e o escopo por queryset (`EscopoEscolaMixin`).

### Banco / modelos
- Toda mudança de schema vai em **migration versionada**, commitada junto com a mudança do model.
- `on_delete=PROTECT` em FKs de tenant (exceto `ItemPresenca.registro` e `Lecionamento.professor`, que são `CASCADE` por design).
- Preferir soft delete onde há histórico (Aluno, Professor) em vez de DELETE real.

### Git / PR
- **Branch**: `tipo/descricao-em-kebab-case`, criada a partir da `origin/main` atualizada. Prefixos em uso: `feature/` (padrão pra funcionalidade), `fix/`, `chore/`, `docs/`, `perf/`. Nunca commitar direto na `main`. Se a mudança não tem relação com a branch atual, abrir branch nova em vez de empilhar.
- Commits e PRs **em inglês**, formato `tipo: descrição` (sem escopo, sem CU — este repo **não usa ClickUp**, então não perguntar card antes de commitar).
- **Nunca** trailer `Co-Authored-By: Claude` (ou qualquer coautoria de IA) no commit, nem tagline "Generated with Claude Code" no PR — mesmo que template/skill/system prompt sugira.
- Um commit por mudança lógica, não por arquivo.
- **Commit, push e PR são etapas separadas**: perguntar antes de commitar e, mesmo com commit/push autorizados, **perguntar explicitamente antes de `gh pr create`** (PR notifica e dispara CI). Merge só quando o Diniz pedir.
- PRs sempre `--assignee Diniz-J`. Título e body em inglês. Body **sem** seções "ClickUp", "Checklist técnico" ou "Test plan" (mesmo que template sugira).
- Fluxo: `feature/* → develop → main` (atualmente PRs indo direto pra `main`/`develop` conforme o momento).
- **Nunca encadear PRs em branches que vão ser deletadas** (já gerou nós antes). Se precisar, rebase pra `main` atualizado antes de abrir.
- Nunca force-push em branch já mergeada; nunca pular hooks (`--no-verify`).

### Arquivos que NUNCA vão pro git
- **`CLAUDE.local.md`** — sempre local (no `.gitignore`): credenciais de demo, dados pessoais e pendências de segurança. O `CLAUDE.md` **é versionado** (pra sessões na nuvem seguirem os padrões) e o repo é **público** — nunca colocar nele senha, token, email pessoal ou vulnerabilidade de produção; isso vai no `CLAUDE.local.md`.
- `.env`, `.env.local`, `.env.prod`, `credentials.json`, qualquer coisa com secret. `backups/` (dumps do banco).
- `.venv/`, `node_modules/`, `__pycache__/`, `dist/`, `build/` — devem estar no `.gitignore`.

### Validação antes de PR
- Backend: `python manage.py check && python manage.py test`.
- Frontend: `npm --prefix frontend run build`.

### Código
- Comentários **em português**. **Nunca emojis** em código ou respostas.
- Erros explícitos, sem panic/silent failure.
- Corrigir erros de tipo/import assim que detectados (preferir LSP pra navegação).
- Separar em camadas (handler/service/repository) quando a complexidade justificar.
- **Simplicidade**: o mínimo que resolve o pedido. Sem abstração, configurabilidade ou tratamento de erro impossível que não foram pedidos.
- **Mudanças cirúrgicas**: tocar só no que a tarefa exige, manter o estilo existente, não refatorar o que não está quebrado. Dead code não relacionado: mencionar, não deletar. Remover só o que a própria mudança deixou órfão.
- Docker: imagens com tag explícita (nunca `:latest`), multi-stage.

### Testes
- Nunca remover teste existente sem justificativa.
- Funcionalidade nova ou bug corrigido vem com teste junto (bug: teste que reproduz, depois o fix).

### Comunicação com o Diniz
- Tratá-lo por **"Diniz"** (não "Rodrigo").
- **Pensar antes de codar**: declarar premissas; se houver mais de uma interpretação razoável, apresentar as opções; se algo não está claro, perguntar em vez de supor. Se existir abordagem mais simples que a pedida, apontar antes.
- **Mudança cirúrgica** (1 arquivo, poucas linhas, escopo claro): aplicar direto, sem mostrar diff antes — ele lê o diff no GitHub/IDE.
- **Mudança estrutural ou multi-arquivo** (>= 2 arquivos relevantes, refactor, schema, módulo novo): apresentar plano em alto nível (`etapa → verificar: checagem`) e **aguardar confirmação** antes de cada etapa. Ele revisa várias vezes antes de aprovar; não pressionar.
- Explicar o raciocínio de forma sucinta, sem repetir o que já está visível no diff.

### Ambiente (Windows / PowerShell)
- Python via `.venv/Scripts/python.exe`. Postgres de teste: `docker start diario_pg_test` quando cair.
- Matar Vite/Django zumbis antes de subir (portas 5173/8000) pra evitar instâncias duplicadas.

---

## 5. Roadmap — status e próximos passos

> Visão estratégica: validar operação real numa escola antes de expandir.
> NÃO focar agora em: portal **do aluno** (login de aluno), app mobile nativo,
> gamificação, financeiro, LMS, IA, microserviços, Kubernetes, arquitetura
> enterprise.
> Em andamento (out/2026): portal **do responsável**, só leitura — ver FASE 6
> e [`PORTAL.md`](./PORTAL.md). Não confundir os dois.
> Focar em: estabilidade, rastreabilidade, deploy, operação, UX administrativa.

### MARCO: aplicação NO AR (demo)
- **Frontend (Vercel):** https://diario-diniz.vercel.app
- **Backend + Admin (Render):** URL do serviço e caminho do admin ficam no `CLAUDE.local.md` (Docker + gunicorn + Postgres gerenciado). Este arquivo é versionado em repo público — não apontar o admin aqui.
- Banco populado com dados de demo. Credenciais ficam no `CLAUDE.local.md` (não versionado).
- Free tier: hiberna após 15 min; Postgres free expira ~90 dias. Pra cliente pagante: plano pago + domínio.

### FASE 1 — Infraestrutura — COMPLETA
1. ✅ **Dockerização** — Dockerfile back/front, compose dev + prod, gunicorn gthread, WhiteNoise.
2. ✅ **Deploy** — Render (Docker, $PORT, DATABASE_URL, entrypoint migrate+superuser) + Vercel. Guia em `DEPLOY.md`.
3. ✅ **Backup** — `scripts/backup.sh`+`restore.sh` (pg_dump -Fc + retenção). Falta: agendar cron no servidor + dump pra storage externo.
4. ✅ **CI** — GitHub Actions (backend check+test, frontend build).

### Segurança — entregue
- ✅ Rate limit no login (5/min), JWT blacklist + rotação (`/auth/logout/`), hardening de produção (CSRF/proxy/cookies/HSTS).

### FASE 2 — Robustez Operacional — PARCIAL
5. **Performance de queries** — auditoria completa feita em 2026-06-08, segunda passada em 2026-06-10 (cobriu Avaliacao/NotaAvaliacao/NotaPeriodo + boletim refactor PDF/CSV/XLSX). Roadmap priorizado de PRs (do mais impactante pro menos):

   > **STATUS (jun/2026) — quase tudo entregue.** ✅ #1 índices (PR #81) · ✅ #3 annotate AvaliacaoViewSet (PR #82) · ✅ #4 bulk lançamento de notas (PR #83) · ✅ #5 prefetch history + cap `/historico/` (PR #84) · ✅ #6 annotate estado + guard save (PR #85) · ✅ #7 purge tokens + `.only()` boletim (PR #86). **#2 resolvido em duas frentes**: PR #87 paginou as listas navegáveis (`Ocorrencia`, `RegistroPresenca`); para os endpoints **matriz** (`NotaAvaliacao`, `NotaPeriodo`, `ItemPresenca`) a decisão de arquitetura (jun/2026) foi **NÃO paginar** — paginar quebraria o lançamento em lote / chamada, que precisam de todos os alunos de uma vez. Em vez disso, **filtro de escopo obrigatório** no `list` (`FiltroEscopoObrigatorioMixin` em `apps/common/views.py`, recusa 400 sem `?avaliacao=`/`?registro=`/etc.) — PR #96. Os sub-itens abaixo ficam como registro histórico do raciocínio.

   1. **PR de índices** (escopo expandido na 2ª auditoria) — migration única adicionando `db_index=True` em:
      - `Ocorrencia.data_ocorrencia`, `Ocorrencia.status`
      - `RegistroPresenca.data`
      - `Aluno.ativo`
      - `Avaliacao.data`, `Avaliacao.periodo`, `Avaliacao.ativo` (campos novos filtrados nos endpoints de avaliação)

      E índices compostos via `Meta.indexes`:
      - `Aluno(turma, ativo)` — auto-geração de presença/avaliação
      - `Lecionamento(professor, ativo)` — dashboards do professor
      - `NotaPeriodo(disciplina, periodo, aluno)` — filtros de notas finais

      Esses campos aparecem em filtros (`filterset_fields`, `?ano_letivo=`, ranges de data) e ordenações em toda listagem. Hoje viram full table scan. ~80 linhas + 1 migration. PENDENTE.

   2. **PR de paginação default opt-out** — `apps/common/pagination.py` hoje retorna `None` quando o front não passa `?page`. Inverter: paginar sempre nos 5+ endpoints volumosos (Ocorrencia, ItemPresenca, NotaAvaliacao, NotaPeriodo, RegistroPresenca). **Urgência**: `NotaAvaliacaoViewSet` e `NotaPeriodoViewSet` retornam 1 linha por (aluno × avaliação) — escola média com 300 alunos × 50 avaliações = 15k linhas sem paginação. Coordenar com front pra ler `{count, results}` em vez de array cru — afeta os hooks TanStack Query desses domínios. Selects de "popular dropdown" (alunos/turmas/disciplinas) continuam sem paginação ou usam `?page_size=all` opt-in. PENDENTE.

   3. **PR de annotate em `AvaliacaoViewSet`** — `AvaliacaoSerializer.get_total_alunos` e `get_notas_lancadas` (apps/avaliacao/serializers.py:208,211) disparam 2 `COUNT(*)` por linha (50 avaliações = 100 queries extras). Trocar `SerializerMethodField` por `IntegerField(read_only=True)` e annotate no `get_queryset()`:
      ```python
      .annotate(
          total_alunos=Count("notas"),
          notas_lancadas=Count("notas", filter=Q(notas__nota__isnull=False)),
      )
      ```
      PENDENTE.

   4. **PR de bulk em lançamento de notas** (novo achado da 2ª auditoria — ALTA) —
      - `lancar_notas` (apps/avaliacao/views.py:158) faz `.save()` em loop: 30 alunos = 30 UPDATEs + 30 INSERTs em `historicalnotaavaliacao`.
      - `lancar_em_lote` (apps/avaliacao/views.py:417) faz `get_or_create` em loop: até 60 queries pra 30 alunos.

      Fix: usar `simple_history.utils.bulk_update_with_history` e `bulk_create_with_history` (preservam audit log). Padrão:
      ```python
      existentes = NotaPeriodo.objects.filter(...).in_bulk(field_name="aluno_id")
      a_criar, a_atualizar = [], []
      for aluno_id, payload in dados.items():
          if aluno_id in existentes:
              obj = existentes[aluno_id]; obj.nota = ...; a_atualizar.append(obj)
          else:
              a_criar.append(NotaPeriodo(aluno_id=aluno_id, ...))
      bulk_create_with_history(a_criar, NotaPeriodo)
      bulk_update_with_history(a_atualizar, NotaPeriodo, ["nota", "observacao"])
      ```
      PENDENTE.

   5. **PR de Prefetch do `history` + paginar endpoint `/historico/`** (combinado com novo achado) —
      - `NotaAvaliacaoSerializer.get_ultima_edicao` e `NotaPeriodoSerializer.get_ultima_edicao` (apps/avaliacao/serializers.py:269,360) chamam `obj.history.first()` por linha → tela "lançamento em lote" de 30 alunos = 30 SELECTs na `historicalnotaavaliacao`. Fix: `Prefetch("history", queryset=Historical.objects.order_by("-history_date"), to_attr="historico_recente")` no `get_queryset()` + ler `obj.historico_recente[0]`.
      - Endpoint `/historico/` (apps/avaliacao/views.py:237,450) retorna `nota.history.all()` sem paginação — nota muito editada vira lista enorme. Fix: aplicar `?page` ou slice `[:50]`.

      PENDENTE.

   6. **PR de annotate `PeriodoAvaliativo.estado` + guard em `Avaliacao.save()`** — a property `estado` (apps/avaliacao/models.py:118-122) dispara 2 `EXISTS` por instância na lista (poucos períodos por escola, prioridade baixa em single-tenant). Annotate com `Exists(...)` no `PeriodoAvaliativoViewSet`. E `Avaliacao.save()` (apps/avaliacao/models.py:283-298) hoje recalcula `periodo` em todo save (mesmo soft delete) — guardar com `if "data" in update_fields or self._state.adding`. PENDENTE.

   7. **PR de cleanup de `PasswordResetToken` + `.only()` no boletim** —
      - Tokens nunca apagados, tabela cresce indefinidamente. Adicionar `manage.py purge_expired_tokens` (apaga `expira_em < now() - INTERVAL 30d`) e plugar no cron de backup.
      - `apps/boletins/services.py:148` puxa colunas pesadas sem `only()`: `observacao` (300 chars) e `descricao` (TextField). Em boletim de 200 avaliações ao ano, vale `.only("aluno_id", "nota", "avaliacao__id", "avaliacao__disciplina_id", "avaliacao__data")`.

      PENDENTE.

   **Itens MÉDIA pendentes (não viraram PR ainda)**: WeasyPrint PDF síncrono (boletim anual trava worker — fix real é Celery, item 12 do roadmap); `ItemPresenca.save` carrega `registro` redundante (item de baixa prioridade); `icontains` em TextField longo no PlanoEnsino (busca pouco usada hoje).

   Itens 1-3 entregam ~80% do ganho real. 4-5 atacam o pico de tráfego do endpoint de lançamento de notas. 6-7 são pré-emptivos pra quando o sistema sair do free tier. **(1, 3-7 todos mergeados — ver STATUS acima.)**
6. ✅ **Audit log** — `django-simple-history` nos 9 modelos do núcleo (Aluno, Professor, Lecionamento, Ocorrencia, RegistroPresenca, ItemPresenca, Tarefa, EntregaTarefa, PlanoEnsino, Usuario). Aba History no admin com diff lado a lado. `populate_history --auto` no boot pra marco-zero dos registros existentes. PR #45.
7. ✅ **Observabilidade — Sentry** integrado em backend e frontend (PR #49). Init condicional por DSN, captura exceções não tratadas + erros 5xx + `logger.error/exception` + erros de render React via `<Sentry.ErrorBoundary>`. Plano Developer (free) 5k events/mês. Em produção, falta o Diniz setar `SENTRY_DSN` no Render e `VITE_SENTRY_DSN` no Vercel (DSNs já criados: projeto Django e projeto React em `diario-diniz.sentry.io`). Sem essas envs o SDK fica inerte. **`SENTRY_DSN` JÁ SETADO no Render e smoke test CONFIRMADO** (jun/2026): um 404 real em prod apareceu no painel. Captura de **4xx** adicionada via `SentryHttpErrorMiddleware` (#92, ignora 401 por default, env `SENTRY_IGNORE_STATUS_CODES`). **Logging estruturado JSON entregue (PR #88)** — contexto por escola via `EscolaLogContextMiddleware`.

### FASE 3 — Produto Comercial — PARCIAL
8. ✅ **Dashboard com métricas** (cards + filtro por turma). Falta: reincidência, presença média.
9. ✅ **Filtro de período** em Ocorrências/Presença. Falta: múltiplos status.
10. **Exportação de relatórios** — PDF/CSV/Excel. PENDENTE.
11. **Diário de classe (`RegistroAula`)** — **FUNCIONAL (5 fatias mergeadas)**. Pedido de cliente: professor lança o conteúdo programático ministrado por aula; direção dá o visto. Decisões travadas: grade de horário (`Lecionamento.dias_semana`) projeta slots, workflow de 3 estados (`rascunho`→`lancado`→`conferido`), conteúdo texto livre, conferência uma a uma (sem lote). Navegação da direção: aba Professores → clica no professor → **`ProfessorDetalhePage` (ficha 360º com tabs Diário/Lecionamentos/Ocorrências/Dados)** → lista cronológica das aulas → confere → **exporta PDF** (com filtros + espaço de assinatura). Pendência de conferência vira card no Dashboard. Fatiado em PRs — **todas mergeadas**: ① backend (#89) · ② PDF (#94) · ③ front diário do professor (#90) · ④ front ficha do professor (#91) · ⑤ card no dashboard (#93). Ficha ganhou também filtros (período+status), agrupamento por mês e contadores; perfil **`coordenador`** entrou como alias de diretor junto da ficha (#91).

   ✅ **Redesenho do PDF do diário — ENTREGUE (PR #97).** Layout reformulado em 4 eixos: status consolidado num badge único (sem repetição da nota "Conferido por X em Y"); cabeçalho/meta reorganizado em blocos; estrutura da lista trocada de tabela pra blocos por aula com conteúdo respirando; identidade visual alinhada (olive/ferrugem/sepia + serifa nos títulos + badges tintados: rascunho mostarda, lançado ferrugem, conferido olive). Tocado por um CC no Claude Desktop. ⚠️ WeasyPrint segue sem renderizar no Windows — iteração local exige container/preview.

   ⏱️ **Latência do PDF** — WeasyPrint é síncrono na request (~1-2s) somado ao cold start do free tier do Render. Fix real (assíncrono) é o item 12 (fila); aceitável por ora.

   ✅ **Smoke test do Sentry CONFIRMADO em prod** (era pendência da FASE 2): o 404 do endpoint de PDF (antes do #94 deployar) caiu no painel — prova que `SENTRY_DSN` está setado no Render e que a captura de 4xx (#92) está ativa.

### FASE 4 — Comunicação Institucional — FUNCIONAL EM PROD
11. ✅ **Email ao responsável na ocorrência (entrega real em prod)** — campos `nome/email_responsavel` no Aluno; envio em thread daemon (fire-and-forget) com `EMAIL_TIMEOUT=10s`, protegido por try/except. Backend de email = **Brevo via HTTP API** (`django-anymail`) — Resend e Gmail SMTP foram tentados e falharam pelo bloqueio de SMTP outbound do Render free (set/2025). Sender verificado: ver `CLAUDE.local.md` (repo público — email fora daqui). 300 emails/dia free. PRs #43 (campos), #44 (off-thread fix), #48 (Brevo). **Validado em 2026-05-30 com entrega externa.** Falta: múltiplos responsáveis, telefone, flag `recebe_notificacao`.
12. **Email assíncrono dedicado** — fila (Celery/Dramatiq/RQ) com retry + histórico, quando o volume crescer. Hoje é thread daemon best-effort. PENDENTE.
13. **Timeline do aluno** — centraliza ocorrências, presença, advertências. Pode reaproveitar a API HistoricalRecords pra mostrar mudanças no histórico. PENDENTE.

### FASE 6 — Portal do Responsável — EM ANDAMENTO

Desenho completo, decisões e invariantes de segurança em
[`PORTAL.md`](./PORTAL.md). Resumo das decisões, pra não reabrir discussão:

- **Só o responsável autentica.** Aluno não loga.
- **Conta só por convite da escola.** Sem auto-registro — qualquer pessoa
  poderia se declarar responsável de qualquer aluno, e matrícula é
  previsível (vetor de enumeração).
- **Identidade em modelo separado** (`Responsavel`, herdando
  `AbstractBaseUser` mas **não** sendo `AUTH_USER_MODEL`), com autenticação
  própria. Usuário externo não encosta na superfície do staff.
- **Mural de materiais é texto + link, sem upload.** Não existe
  `FileField`/`MEDIA_ROOT` no projeto e o disco do Render é efêmero; anexo
  exigiria object storage.
- **Mesma app de frontend, sob `/portal`**, com namespace próprio no
  storage de token.
- **Convite individual na UI + management command de lote**, porque a cota
  de 300 emails/dia do Brevo é compartilhada com os comunicados.
- **Aluno desativado não corta o acesso**: o responsável mantém o
  histórico, mas para de receber comunicado novo.

Risco central, documentado por não ser óbvio: o SimpleJWT resolve o claim
de id contra o `AUTH_USER_MODEL`, então um token de `Responsavel` de pk N
apresentado num endpoint de staff carregaria o `Usuario` de pk N. Cada
token carrega claim de tipo e **cada lado recusa o token do outro**, com
teste nos dois sentidos.

Fatias (um PR cada): 1) modelo e vínculo · 2) auth isolado · 3) convite e
senha · 4) leituras · 5) mural · 5b) tela do mural no staff · 6) frontend
do portal · 6b) tela "Responsáveis" + botão Convidar no staff.

**Status (out/2026):** 1–5b entregues (#106–#111) — backend do portal
completo em produção, mural do staff no ar. **Pendentes: 6 (todo o lado do
pai) e 6b.** Plano aprovado da 6, escopo da 6b e achados do staff que
saíram dos CRs estão no `PORTAL.md`, seções 5 e 6 (os de segurança, no
`CLAUDE.local.md`).
**Nenhum convite em produção antes da fatia 6.**

**Fatia 1 entregue**: app `portal` com `Responsavel` (`AbstractBaseUser`,
não `AUTH_USER_MODEL`; email normalizado no `save`, unique por
`(escola, email)`) e `ResponsavelAluno` (M2M auditado, `PROTECT` nos dois
lados, `clean()` exige mesma escola). Semeadura por
`manage.py portal_semear_responsaveis` — idempotente, deduplica irmãos por
email, inclui aluno inativo, pula aluno sem email (o email é a âncora da
identidade). Conta nasce sem senha utilizável: acesso só pelo convite.

**Portão: a fatia 2 (login externo) não sobe antes da PR #105 estar
mergeada e deployada.** A fatia 1 é só modelo/migration/admin, não abre
caminho de autenticação, e pode ir em paralelo.

### FASE 5 — Evolução SaaS
14. **Multi-tenancy real** — middleware de tenant, RLS PostgreSQL, billing. Só após validação comercial.
15. **Segurança e compliance** — httpOnly cookies, LGPD formal, retenção de logs, auditoria avançada.

### Soft delete UX — entregue
- ✅ Listagens escondem inativos por padrão; toggle `Switch` "Mostrar inativos" na `AlunosPage` reverte (PR #47).
- ✅ Linha de inativo ganha badge `[ inativo ]` e ⋯ troca "Excluir" por "Reativar".
- ✅ Selects de criação (OcorrenciaFormDialog) restritos a ativos.
- ✅ `AlunoDeleteDialog` com texto correto ("inativar", não "excluir permanente").

### Identidade visual — entregue (Login + AppLayout + Dashboard)
- ✅ Paleta de marca olive/linho/ferrugem em CSS variables, mapeada pros tokens shadcn (PR #51).
- ✅ Light mode permanente (sem dark toggle); `color-scheme: light` + meta tag desabilitam force-dark de browsers.
- ✅ Tipografia mista — Fraunces (serif via Google Fonts `<link>`) em títulos, Geist em corpo. `font-heading` token.
- ✅ Login repaginado (PR #50) — Fraunces 26-30px tracking-tight, filete ferrugem, microtípico, botão olive solid.
- ✅ AppLayout/Sidebar repaginado (PR #51) — olive-dark, barra ferrugem no ativo, perfil em mono uppercase.
- ✅ Dashboard repaginado (PR #52) — cards `bg-paper` próprios (dropam shadcn Card), MetricCard com Fraunces 50px no valor + label mono, badges de ocorrência com paleta da marca, cores P/A/J/R da presença em pastels terrosos.
- ✅ Auto-escopo de escola (PR #53) — diretor/professor não vê select de escola; backend deduz pelo JWT via `AutoEscopoEscolaSerializerMixin`. Multi-tenant invisível pro cliente.
- ✅ **Listagens + detalhes + forms repaginados** (varredura jun/2026) — todas no padrão `DESIGN.md` §7 (header Fraunces + filete + eyebrow mono + `bg-paper` + badges tintados + dialogs com label mono).
- ✅ **`DESIGN.md` durável** (356 linhas, raiz do repo) — fonte da verdade visual com tokens, tipografia, status badges, antecipações §7 e anti-patterns §8 (todos pagos). Atualizado em cada PR visual.

### Higiene pós-deploy — atacar junto da migração OVH
Pendências de segurança de produção ficam no `CLAUDE.local.md` (não versionado — repo é público). Resolvem junto da migração, quando o ambiente novo nasce com env vars novas.
- ✅ Frontend chama `/auth/logout/` no logout (invalida o refresh) — `AuthContext.tsx`.
- 🟢 Placeholder "(YYYY-MM-DD)" da presença — cleanup cosmético.

### Backup do Render (pré-migração) — feito
- Dump custom format gerado via `docker run --rm postgres:18 pg_dump -Fc` apontando pra External Database URL (Virginia). Saiu em `backups/render_*.dump` (~222 KB, 469 TOC entries, PG 18.3).
- Smoke test do restore num container PG 18 local: passou em ~4s, contagens conferem (1 escola, 4 turmas, 50 alunos, 11 usuários, 7 ocorrências, 5 RegistroPresenca + 55 ItemPresenca, 2 RegistroAula, 2 PlanoEnsino).
- `backups/` está no `.gitignore` (linha 34) — dump não vaza no commit.
- Comando de seed reproduzível na OVH: `python manage.py popular_alunos_mock --escola-id 1 --turma "Mock 35" --quantidade 35` (PR #101). Idempotente.

### Senhas / acesso — TUDO ENTREGUE
- ✅ Tela "Trocar minha senha" (`ContaSenhaPage`).
- ✅ Reset por email (`EsqueciSenhaPage` + `RedefinirSenhaPage`) via Brevo.
- ✅ Admin/direção reseta senha de terceiro pela UI — action `enviar-reset-senha` no `UsuarioViewSet` + botão na ficha do professor / ⋯ na listagem. PR #100.
- Limitação restante: usuários puros (diretor/secretaria/coordenador sem perfil de professor) ainda dependem do `/admin/` do Django — não têm página de gestão dedicada. Fica pra quando uma `UsuariosPage` aparecer no roadmap.

### Meta de curto prazo — STATUS
Infra ✅, segurança operacional ✅, audit log ✅, comunicação por email **funcional em prod** ✅, **Sentry em prod ✅ (DSN setado + smoke test confirmado + captura de 4xx)**, **identidade visual completa ✅ (Login + Sidebar + Dashboard + listagens + detalhes + forms; DESIGN.md durável travado)**, auto-escopo de escola ✅, **diário de classe ✅ (5 fatias + redesenho do PDF #97)**, **fluxo de senha completo ✅ (próprio + esqueci + admin reseta de terceiro, PR #100)**, **performance ✅ (índices, annotates, bulk, prefetch + escopo obrigatório nos endpoints matriz)**. **Próximo objetivo crítico: migração pra OVH 🔴** — segue em Render free + Vercel. O Postgres free foi **reiniciado em out/2026**, então a validade de ~90 dias voltou a contar: **~30 dias de folga a partir de 2026-10-06** (vence por volta de 2026-11-05). É o prazo real da migração — passou disso, o banco expira de novo. Dump local já feito (PG 18 custom format, ~222KB), restore smoke-testado num container PG 18 local. Resta: provisionar VPS OVH, restaurar dump, ajustar `ALLOWED_HOSTS`/`CSRF_TRUSTED_ORIGINS`/`CORS_ALLOWED_ORIGINS`/`DATABASE_URL`, rotacionar `SECRET_KEY`, trocar `VITE_API_URL` no Vercel. Frontend continua no Vercel — só backend+banco saem do Render. Próximas frentes pós-OVH: fila assíncrona pra email (item 12), múltiplos responsáveis no aluno, dashboard com mais métricas.

---

## 6. Diferenciais já implementados

**Técnicos:** permissões granulares por perfil, guard contra IDOR
consistente em todos os serializers com FK escola, optimistic updates,
tenancy preparada (`BaseModelEscopado`) + auto-escopo invisível na UI
(`AutoEscopoEscolaSerializerMixin`), JWT customizado (com rate
limit + blacklist/rotação), coerência transacional (auto-geração de
presença/tarefas), soft delete com preservação de histórico + UX de toggle
"Mostrar inativos" + ação Reativar, shell mobile responsivo, seed de
disciplinas BNCC, **dockerização + deploy no ar + CI + backup**,
**audit log com diff (django-simple-history) nos 9 modelos do núcleo**,
**notificação por email ao responsável nas ocorrências entregando de
verdade em prod via Brevo HTTP API** (off-thread, protegido, sem domínio
próprio, 300/dia free), **observabilidade via Sentry** (backend +
frontend, plano free, gated por DSN), **identidade visual Diário Diniz**
(paleta olive/linho/ferrugem + Fraunces + Geist em hierarquia editorial).

**Comerciais:** foco operacional procedural, rastreabilidade real (audit log
+ email transacional), simplicidade de uso administrativo, **multi-tenant
invisível pro cliente final** (diretor da Escola X loga e nem sabe que
existe Escola Y no mesmo banco).
