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
gated por `VITE_SENTRY_DSN`). **Teste:** vitest + jsdom +
`@testing-library/react` + `@testing-library/jest-dom` + **MSW** (mock de
rede) — ver `src/test/` no mapa abaixo.

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
- `pdf.py` — render WeasyPrint + caminho da logo + `slug_arquivo` (lista de permissão de caracteres: o nome vai cru pra dentro de `filename="..."`, e aspa ou barra quebrariam o header). Compartilhado pelos três PDFs.
- `planilha.py` — **neutralização de fórmula** em planilha. Excel e LibreOffice executam célula iniciada em `=`, `+`, `-` ou `@` ao abrir o arquivo, e o que sai nos exports é escrito por gente (descrição de ocorrência, título de avaliação, nome vindo de importação de terceiro). Prefixa com apóstrofo, que o Excel lê como texto e não exibe. `desneutralizar_formula`/`desneutralizar_dataset` são a contraparte na leitura do import de migração, que é **round-trip**: sem elas o marcador seria gravado no banco na volta e cada ciclo acumularia mais um. Aplicado nos três caminhos que exportam planilha — `relatorios/exportacao.py`, `boletins/views.py` e o próprio `common/import_export.py`. Mora em `common` porque a camada base não pode importar app de domínio.
- Validator de CNPJ com dígito verificador.

**`accounts/`** — identidade e autenticação.
- `Usuario(AbstractUser)` — `perfil` (admin/diretor/professor/secretaria/coordenador/inspetor) + FK opcional `escola`. **Auditado** (`HistoricalRecords(excluded_fields=["last_login"])` — `last_login` ficaria barulhento, o resto vai pro histórico inclusive `password` hash).
- `UsuarioSerializer` — inclui `escola` nos fields (necessário pra criar Professor).
- `UsuarioTokenObtainPairView` / `...Serializer` — JWT com claims `escola_id`, `perfil`, `username`, `first_name`, `last_name`.
- `/usuarios/` restrito a admin/diretor (via `IsAdminOrDiretor`, que cobre também secretaria/coordenador como aliases). Desde out/2026 a direção gere os próprios pares na própria escola — ver "Senhas / acesso" no roadmap pro que ficou aberto e pro que continua fechado, que é onde a decisão está registrada.
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
lá): resolve pelos vínculos, pula conta inativa ou com
`recebe_notificacao=False`, e só cai no `Aluno.email_responsavel` quando o
aluno não tem vínculo **nenhum** — ver `RESPONSAVEIS.md` §4.1, é a
armadilha central da frente. `recebe_notificacao` é opt-out de email e é
**separado de `ativo`** de propósito: quem pede silêncio continua
consultando o boletim no portal. Semeadura:
`manage.py portal_semear_responsaveis`. **Escrita do staff** (fatia 4 do
`RESPONSAVEIS.md`): `views_staff.py` tem o `ResponsavelAlunoStaffViewSet`
(cria e apaga vínculo, sem `PUT`/`PATCH`) e o `POST` do
`ResponsavelStaffViewSet` (cadastra conta — reverteu a somente-leitura da
6b). O guard do vínculo é **duas camadas**: o `clean()` exige os dois lados
na mesma escola, e o serializer checa **cada lado contra a escola de quem
está logado** — sem a segunda, um par consistente de outra escola passaria,
porque o `clean()` não tem o que reclamar. **Fatia 6 entregue**: frontend do
portal sob `/portal`, em chunk próprio (`React.lazy` no `App.tsx` separa a
árvore do staff da do portal), sessão independente em
`features/portal/` (storage `portal_*`, `portalApi` que guarda o refresh
rotacionado, `PortalAuthContext` lendo `/portal/me/` por **query do TanStack**, não por `useEffect`: a identidade vira cache com `enabled` ligado à presença de token, `staleTime` infinito e `retry` off, e `entrar` semeia o cache com o `/me/` que acabou de responder) e seis telas
mobile-first em `src/portal/`. Backend entregue até a fatia 5:
autenticação isolada (`/api/v1/portal/auth/`, tokens com `tipo=responsavel`
e `responsavel_id` — o staff recusa), convite e senha (`ConviteResponsavel`,
comando `portal_convidar_responsaveis`) e leituras em `leituras.py`, todas a
partir dos vínculos (`filhos_do`). A última a entrar foi
`FaturasFilhoView` (out/2026), que leva o `link_pagamento` do financeiro
ao pai: quem vê é **todo responsável vinculado e não só o `pagador` do
plano**, porque o email de pagamento já sai por `destinatarios_do_aluno`
e alcança todos — restringir aqui deixaria o outro responsável com o
aviso de "pagamento recebido" e nenhum lugar pra conferir; o `pagador` é
o titular do boleto, não controle de acesso. Fatura **cancelada** não
aparece (ato interno da secretaria), e filho inativo **continua vendo as
dele**, como o boletim, divergindo do mural de propósito. Com a fatia 6 no ar, o portão
"nenhum convite em produção" caiu — o link do email tem tela pra abrir.

**`materiais/`** — mural do professor pra turma (fatia 5 do `PORTAL.md`).
`Material` = turma + disciplina + professor + título + descrição + link
(só http/https, sem upload). **Auditado**. Mesmo molde do `RegistroAula`:
`Lecionamento` ativo obrigatório, professor só vê/edita os próprios e não
publica em nome de outro (403), direção vê a escola toda. `DELETE` = soft
delete (`ativo=False`). O portal lê em `/portal/alunos/<id>/materiais/`
(só a turma atual do filho; filho desativado vê lista vazia). Tela do
staff: `MuralPage` em `/mural` (fatia 5b) — professor publica só nos
próprios lecionamentos ativos, direção escolhe o professor e modera.

**`financeiro/`** — contas a receber da mensalidade (ver
[`FINANCEIRO.md`](./FINANCEIRO.md)). Quatro modelos, todos auditados:
`PlanoCobranca` (contrato do aluno: valor, dia de vencimento, desconto,
multa/juros, vigência), `Fatura` (uma competência do contrato, com o valor
**congelado na geração** — reajuste em maio não reescreve a fatura de
março), `FaturaItem` (detalhamento, `CASCADE` como o `ItemPresenca`) e
`Pagamento` (conciliação). A emissão de boleto/Pix **não é nossa** — é de
gateway (Asaas); aqui fica o contas a receber e a conciliação por webhook.
Três coisas que não se deduzem do schema: (1) o unique é
`(aluno, competencia)` e **não** `(plano, competencia)`, senão a troca de
plano no meio do mês geraria duas faturas da mesma competência e cobraria
o aluno duas vezes — por isso `Fatura.aluno` é desnormalizado, e é a única
razão do campo; (2) multa e juros são **método**
(`Fatura.encargos(hoje)`), não campo, e os percentuais moram no plano
porque são cláusula de contrato — mudar a env não reescreve contrato
assinado; (3) `valor_pago`/`status` são escritos pelo `services.py`, nunca
pelo `save()` do `Pagamento` (quebraria em bulk e esconderia o momento em
que o dinheiro muda o estado da fatura) — tem teste travando. A vigência
sobreposta é barrada só no `clean()`: limitação conhecida da v1, com o
caminho da exclusion constraint (`daterange` + `EXCLUDE USING gist`)
anotado no `FINANCEIRO.md` §3.2. Dinheiro é sempre `DecimalField`, com
arredondamento comercial (`ROUND_HALF_UP`) centralizado em
`arredondar_dinheiro()`. **Completo — as seis fatias entregues**
(models/migration/admin + API REST + services e geração recorrente + as
telas do financeiro + a ficha do aluno + gateway Asaas + webhook). A API é **só direção**
(`IsAdminOrDiretor` uniforme; professor e inspetor levam 403 até na
leitura) e o que mexe em dinheiro é read-only — `status`/`valor_pago`/
`data_pagamento` pertencem ao `services.py`, `id_externo`/
`link_pagamento` ao gateway. `Fatura.aluno` também é read-only, deduzido
do plano, e como o `UniqueTogetherValidator` do DRF só cobre campos
graváveis, a competência repetida precisa de validação explícita pra dar
400 em vez de estourar o unique como 500. Os serializers **não**
espelham as invariantes à mão (como `materiais`/`aulas` fazem): rodam o
`clean()` do modelo sobre uma cópia carregada com o payload
(`_validar_pelo_clean`), porque o `PlanoCobranca` tem cinco invariantes e
duas cópias delas divergiriam. `DELETE` cancela a fatura, desativa o
plano, apaga o item e **estorna** o pagamento. `services.py` concentra o
que escreve dinheiro: `gerar_faturas` (idempotente, com
`bulk_create_with_history`), `registrar_pagamento`/`estornar_pagamento`
(em transação, com `select_for_update`, recalculando `valor_pago` em vez
de incrementar — recálculo é idempotente e se autocorrige) e
`marcar_vencidas`. Três management commands pra cron
(`financeiro_gerar_faturas`, `financeiro_emitir_cobrancas`,
`financeiro_marcar_vencidas`). Duas pegadinhas
que custaram código e estão registradas no `FINANCEIRO.md` §5: o DRF monta
um `UniqueValidator` a partir do `UniqueConstraint` de
`referencia_externa` e mataria a idempotência do reenvio antes do service
(o campo é declarado com `validators=[]`), e o `ValidationError` do Django
que o service levanta sai como 500 se a view não traduzir (`erro_drf`).
**Gateway e webhook entregues.** `gateways/base.py` é o contrato
(quatro operações, vocabulário nosso) e `gateways/asaas.py` o adaptador —
transporte `httpx` mais a tradução de campo e de status, escrita contra a
doc deles, não de memória. A emissão é passo **separado** da geração
(`emitir_cobranca` no service, action na API, command no cron): a geração
é transacional e em lote, e pendurar HTTP ali prenderia o lock pelo tempo
do provedor. A conciliação chega em
`POST /api/v1/financeiro/webhooks/asaas/` — única rota sem autenticação
do projeto, com token em `compare_digest`, evento gravado antes de
processado (`EventoWebhook`, unique no id do evento, **não** escopado por
escola porque o tenant só se descobre depois) e **reconsulta ao provedor
antes de escrever dinheiro**: o token prova quem mandou, não quanto
entrou. Responde 200 mesmo quando o processamento falha, porque 15 falhas
consecutivas pausam a fila deles e param a escola inteira. A emissão
exigiu schema novo: `PlanoCobranca.pagador` (o titular do boleto é
cláusula de contrato, não "o primeiro responsável com CPF") e
`Responsavel.id_externo_gateway` (criar cliente lá não é idempotente).
Detalhes do contrato real e as pegadinhas estão no `FINANCEIRO.md` §6.

**`tarefas/`** — esqueleto vazio (só `__init__.py`/`apps.py`/`migrations`). Feature **removida** do produto; frontend não tem `TarefasPage` nem feature `tarefas/`. Diretório mantido pra não quebrar migrations históricas.

**`planos_ensino/`** — `PlanoEnsino` (ementa, conteúdo programático, objetivos, habilidades BNCC, carga horária, metodologia, recursos, avaliação, `ativo`). Único por `(escola, turma, disciplina, ano_letivo)`. Casca criada num dialog; campos longos preenchidos na tela de detalhe. **Auditado**.

**`boletins/`** — **sem modelo próprio**. `services.py` agrega on-the-fly; `BoletimAlunoView` (APIView) expõe `GET /boletins/aluno/<id>/`. Justificado (J) conta como presença efetiva na frequência.

**`timeline/`** — timeline do aluno (item 13 do roadmap). **Sem modelo
próprio**, molde de `boletins`: `services.py` mescla on-the-fly três
origens numa lista ordenada por data desc e `TimelineAlunoView` serve
`GET /timeline/aluno/<id>/?data_inicio=&data_fim=` (JSON só; o que a
escola arquiva sai pelos relatórios). Três coisas que não se deduzem do
código: (1) **presença entra pelo que NÃO é presença** — o item `P` fica
fora porque 200 "veio à aula" por ano afogam as cinco linhas que
importam, e `J`/`R` entram como evento, numa régua **deliberadamente
diferente** da frequência (lá eles contam como presença efetiva): a
pergunta aqui é "o que aconteceu", e chegar atrasado aconteceu — tem
teste travando os dois lados pra ninguém "consertar" a divergência;
(2) **o histórico do simple-history é lido inteiro e filtrado depois**,
porque cada evento nasce da comparação com a entrada anterior e filtrar
no banco deixaria de fora justamente a entrada que está antes da janela;
(3) `CAMPOS_CADASTRAIS` é **lista de permissão** (`turma`, `ativo`,
`matricula`, `nome_completo`) e não "tudo menos X" — `nome_responsavel`
e `email_responsavel` ficam fora de propósito, porque a tela é lida por
professor e inspetor e contato de responsável é nível-direção no resto
do sistema (é por isso que o relatório cadastral exige
`WRITE_PERMISSION`). Teto de `LIMITE_EVENTOS` com flag `truncado` na
resposta: timeline cortada em silêncio faria a direção concluir que não
houve mais nada. Guard de IDOR igual ao do boletim — são duas cópias de
seis linhas; a terceira vai pra `apps/common`.

**`relatorios/`** — relatórios operacionais. **Sem modelo próprio**, mesmo
molde de `boletins`: `services.py` agrega on-the-fly e cada relatório é uma
APIView que serve quatro formatos no mesmo recorte
(`?formato=json|pdf|csv|xlsx`). `exportacao.py` tem a mecânica comum
(valida formato, monta planilha via tablib, devolve o download).

**Frequência por turma**
(`GET /relatorios/frequencia/?turma=&periodo=|data_inicio=&data_fim=`) —
contadores por aluno em UMA query (agregado condicional anotado sobre o
`Aluno`, com teste travando `assertNumQueries`), alerta de quem está abaixo
dos 75% da LDB, e a mesma régua de presença do boletim (P/R/J contam; só A
é falta), com teste comparando as duas pra não divergirem. Turma é
obrigatória e de outra escola responde 404. Botão na `TurmaDetalhePage`.

**Alunos (cadastral)** — action no `AlunoViewSet`
(`GET /alunos/relatorio/?formato=pdf|csv|xlsx`), **deliberadamente
separada do `export/`** do `ImportExportViewSetMixin`: aquele é o serviço
de migração em massa (admin global + flag
`Escola.importacao_em_lote_habilitada`), este é a lista que a secretaria
tira da própria escola. A permissão sai do `WRITE_PERMISSION` do
`ReadWritePermissionMixin` (admin/diretor; professor leva 403, porque a
planilha traz nome e email de responsável) — como é consequência do mixin
e não de uma declaração local, tem teste fixando os dois lados.
`permission_classes` no `@action` seria ignorado em silêncio, já que o
mixin sobrescreve `get_permissions`. PDF separado por turma, com teto
`LIMITE_PDF_ALUNOS`. Botões na `AlunosPage` ("Relatório") e na
`TurmaDetalhePage` ("Lista da turma").

**Métricas do dashboard** (`GET /relatorios/dashboard/?turma=`) — o par
que faltava nos cards (presença média e reincidência de ocorrências),
em três queries fixas. Mora nesta app porque a régua de presença efetiva
é daqui: uma terceira cópia dela é exatamente o que o teste de
não-divergência boletim×relatório existe pra impedir. Janela fixa de 30
dias (`JANELA_DASHBOARD_DIAS`), **não exposta por parâmetro** — a tela
não tem seletor de período. Reincidente é quem tem `LIMIAR_REINCIDENCIA`
(2) ou mais ocorrências na janela, contado em Python sobre uma lista de
contadores por aluno (dezenas de linhas, não milhares): em SQL exigiria
`HAVING` sobre anotação dentro de `aggregate`, e a lista dá de graça o
total de alunos envolvidos que o card usa na sublinha. Único endpoint da
app que serve só JSON — ninguém baixa dashboard em PDF. Usuário sem
escola e não-admin recebe **zerado, não 403**: um 4xx aqui derrubaria a
tela toda.

**Ocorrências** — a action mora no `OcorrenciaViewSet`
(`GET /ocorrencias/exportar/?formato=pdf|csv|xlsx`), não aqui: é lá que
`get_queryset` (escopo) e `filter_queryset` (`OcorrenciaFilter`) já
existem, e reimplementá-los seria o jeito mais fácil de o arquivo
divergir da tela. Só o agrupamento, as linhas e o template vivem em
`relatorios`. PDF agrupado por aluno (a pergunta do conselho de classe é
"o que houve com este aluno"), com teto de `LIMITE_PDF_OCORRENCIAS`
linhas — o WeasyPrint é síncrono e um PDF de dez mil blocos derruba o
worker; o erro manda pro CSV/XLSX, que não têm teto. O nome da turma no
cabeçalho sai dos dados, não do `?turma=`: id de outra escola devolve
recorte vazio, mas resolver pelo parâmetro imprimiria o nome alheio.

**`aulas/`** — diário de classe (conteúdo ministrado por aula). `RegistroAula` = turma + disciplina + professor + data + `conteudo` (texto livre) + `status` (`rascunho`→`lancado`→`conferido`) + `conferido_por`/`conferido_em` (visto da direção). Quarto conceito ao lado de `PlanoEnsino` (planejado no ano), `Tarefa` (atividade do aluno) e `RegistroPresenca` (quem veio) — registra "o que foi dado na aula do dia". Único por `(escola, turma, disciplina, data)`. **Auditado**. `clean()`/serializer: escola alinhada, **`Lecionamento` ativo obrigatório** pro trio, data não-futura, conteúdo exigido ao lançar. Viewset escopado (direção vê a escola toda; professor/inspetor só os próprios); `perform_create` bloqueia (403) lançar em nome de outro. Action `conferir` (só direção) move `lancado`→`conferido` e grava quem/quando — o serializer recusa `status=conferido` (sem auto-conferência); aula conferida trava edição. Action `agenda` (`?turma=&disciplina=&mes=YYYY-MM`) projeta os slots do mês a partir de `dias_semana` do `Lecionamento`, on-the-fly (sem tabela), via `services.py`. **Completo: backend #89; front — diário do professor #90, ficha do professor #91, PDF #94 + redesenho do PDF #97, card no dashboard #93.**

### Frontend — `frontend/src/`

- **`features/<dominio>/hooks.ts`** — TanStack Query: `useXxx` (list), `useCreate`, `useUpdate`, `useDelete`/`useDeactivate`, com invalidação de cache + toast. Domínios: `alunos`, `auth`, `boletins`, `dashboard`, `disciplinas`, `escolas`, `lecionamentos`, `ocorrencias`, `planos-ensino`, `presenca`, `professores`, `timeline`, `turmas`, `usuarios`, `comunicados`, `financeiro`. O `features/dashboard/hooks.ts` nasceu com as métricas agregadas: as outras do dashboard são derivadas no front a partir dos hooks de outros domínios, e presença média e reincidência não dão — a primeira exigiria baixar todo o `ItemPresenca` da escola, a segunda agrupar ocorrência por aluno no cliente.
- **`features/auth/`** — `AuthProvider`, `useAuth`, `usePermissoes` (regra de UI por perfil; `podeModificarCadastros` = admin/diretor), tokenStorage em localStorage, decode JWT. `user.escola_id` é o sinal usado pelos FormDialogs pra decidir se renderiza o select de escola.
- **`lib/api.ts`** — axios único. Request interceptor injeta Bearer. Response interceptor: 401 → refresh → refaz request (promise compartilhada contra thundering herd).
- **`lib/queryClient.ts`** — staleTime 30s, retry off pra 401/403.
- **`lib/datas.ts`** — `hojeISO()`, o "hoje" dos inputs de data. Existe porque `new Date().toISOString().slice(0, 10)` converte pra UTC e, das 21h em diante num fuso negativo, devolve **amanhã** — e ocorrência e chamada recusam data futura no backend, então o turno noturno recebia formulário que o servidor rejeitava (o `max` do input vinha errado junto, então o browser nem barrava). Monta campo a campo pelos getters locais. Tem teste com fuso e relógio fixos (`datas.test.ts`) que reprova a implementação antiga. Mora aqui também a **formatação de data**, em três funções cujo nome diz o tipo do campo no backend, porque errar o par era o bug clássico: `formatarDataPura` pra `DateField` (split da string, porque `new Date("2026-03-10")` é lido como UTC e volta como dia 9), `formatarDataHora` pra `DateTimeField` (aí `new Date` é o certo — a string do DRF traz offset) e `formatarDiaDaDataHora` pro `DateTimeField` exibido só como dia. Consolidou **14 cópias locais** espalhadas em 13 arquivos; a `AlunoPage` do portal aplicava a de data pura em `publicado_em`, concatenando `T00:00:00` numa string que já tinha hora e offset, e o mural do pai mostrava **"Invalid Date"** em todo material (tem teste travando). Fica fora só o formatador do `BoletimFilho`, que é o formato compacto "10/03" sem ano. `isoDiasAtras(dias)` monta a ponta de trás dos filtros de janela ("últimos 30 dias") pelo mesmo caminho — `setDate` pra resolver virada de mês/ano/bissexto, e composição campo a campo na saída.
- **`lib/download.ts`** — `baixarArquivo()`: download autenticado via Blob (`window.location` perderia o Bearer). Usado por boletim, diário e relatórios; antes era copy-paste em dois `hooks.ts`. Desembrulha o corpo de erro, que com `responseType: "blob"` chega como Blob — sem isso a mensagem que o backend escreve (recorte grande demais pro PDF, por exemplo) nunca chega no toast. Equivalente no backend: `apps/common/pdf.py` (`render_pdf`, `caminho_logo`, `slug_arquivo`), que as três views de PDF compartilham.
- **`test/`** — harness dos testes de componente (vitest + jsdom + testing-library + MSW). `render.tsx` tem o `renderizar()`, que monta os três contextos que as telas exigem (TanStack Query com `retry: false` — obrigatório, senão o teste de falha espera as tentativas antes de `isError` virar true; rota, porque os cards usam `<Link>`; e auth, porque `useAuth` lança erro explícito fora do provider). `autenticar.ts` semeia sessão forjando um JWT no localStorage — funciona porque o front **nunca** valida assinatura (`features/auth/jwt.ts`), então o token forjado é indistinguível de um real pra quem consome `useAuth`. `servidor.ts` nasce sem handler nenhum: cada teste declara os endpoints que usa.
  **Duas armadilhas pagas, e as duas produzem teste que passa pelo motivo errado** (o remédio das duas é um **controle positivo** ao lado de cada teste de erro — se o caminho felizmente carregado não for afirmado, nada garante que a falha veio do que o teste quis provar): (1) em jsdom o axios escolhe o adapter **XHR**, e a interceptação de XHR do MSW não funciona nessa combinação — todo request volta `Network Error`, então `setup.ts` força `adapter: "fetch"` nas duas instâncias (os interceptors de Bearer e de refresh são camada de axios, não de transporte, e seguem rodando); (2) requisição que nenhum handler cobre o MSW só **loga** — a falha de transporte é indistinguível de um 500 declarado, então `setup.ts` junta os `request:unhandled` e **reprova no `afterEach`** listando os endpoints esquecidos (pegou um `/planos-cobranca/` faltando no primeiro teste escrito). Em MSW 3 a opção do `listen` chama-se `onUnhandledFrame` (era `onUnhandledRequest` até a v2). E `defineConfig` sai do `vitest/config`, não do `vite` — com o do `vite`, `tsc -b` reprova o bloco `test` (TS2769) e o `npm run build` quebra junto.
- **`components/AppLayout.tsx`** — shell: sidebar fixa olive-dark em ≥768px, drawer (`Sheet`) com hamburguer em <768px. Logo "Diário Diniz" em Fraunces no topo + perfil em mono uppercase + nav com barra ferrugem no ativo + rodapé com filete ferrugem + logout + versão.
- **`components/ui/`** — shadcn (editável). `Sheet` e `Switch` foram adicionados manualmente (CLI travava em prompt).
- **`index.css`** — paleta de marca em CSS variables no `:root` (`--olive`, `--olive-dark`, `--linho`, `--paper`, `--ferrugem`, `--tinta`, `--sepia`, `--creme`) + mapeamento dos tokens shadcn (`--background`, `--primary`, etc.) pra paleta. Light mode permanente (sem `.dark` block). `color-scheme: light` + meta tag desabilitam force-dark dos browsers.
- **~29 pages** — Login, Dashboard, Alunos (+timeline do aluno), Turmas (+detalhe), Disciplinas, Professores (+detalhe — ficha 360º), PlanosEnsino (+detalhe), Ocorrencias (+detalhe), Presenca (+detalhe), Avaliacoes (+detalhe), PeriodosAvaliativos, NotasFinais, DiarioAula, Boletim, **Faturas + PlanosCobranca + FichaFinanceira** (financeiro; as duas primeiras sob um item só de sidebar com abas internas, a ficha alcançada pelo nome do aluno, pelo ⋯ da AlunosPage e pelo botão da TurmaDetalhePage), Import, **Usuarios** (gestão de conta do staff; Responsáveis é a tela do usuário externo), ContaSenha/EsqueciSenha/RedefinirSenha, NotFound, Placeholder. **Todas no padrão visual `DESIGN.md`** (Fraunces + filete ferrugem + eyebrow mono + `bg-paper`), inclusive listagens/detalhes/forms. Polidas em ondas: Login/Sidebar/Dashboard (PRs #50-#52), depois listagens e detalhes ao longo de jun/2026.
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
- **Dinheiro é string no front**: o `DecimalField` do DRF serializa `"1000.00"` pra não perder precisão em float, então os tipos declaram `string` e `formatarBRL` (em `features/financeiro/constants.ts`) só formata. **Nenhuma aritmética de dinheiro no front** — saldo, encargos e valor atualizado vêm calculados do backend.
- **Data sem hora não passa por `new Date`**: `new Date("2026-03-10")` é lido como UTC e, em fuso negativo, volta como dia 9. `formatarData`/`formatarCompetencia` fazem split da string; e o default de "hoje" num input de data é montado campo a campo, porque `toISOString()` à noite viraria amanhã (data futura que o backend recusa).
- **Query que falha não vira estado vazio**: no TanStack Query o `isLoading`
  volta a **false** quando a query **falha**, então o skeleton sai e o
  componente renderiza o ramo de lista vazia — a tela apresenta a falha de
  rede como resposta do servidor ("nenhuma ocorrência em aberto", "nenhum
  pagamento registrado", "você não tem cadastro de professor"). Todo ramo de
  vazio tem que vir **depois** de um ramo de `isError`. Duas consequências
  que doem mais que o texto errado: no financeiro a secretaria conclui que a
  família não pagou, e num **form de edição** o campo abre vazio **e
  habilitado** sobre um registro que existe, então salvar dali apaga o que
  estava no banco — aí a correção não é mensagem, é **travar a escrita**
  (`RegistroAulaFormDialog`). Pelo mesmo motivo, flag derivada de `data`
  (`somenteLeitura = registro?.status === "conferido"`) cai pro lado
  permissivo quando a leitura falha, e o travamento que ela fazia vai junto.
  Nos **dialogs de formulário** o estrago tem uma terceira forma: a lista
  que popula o `<Select>` falha, o select abre vazio e a validação de
  submit responde "Selecione uma turma" — a tela **culpa o usuário** por
  uma falha de rede. O aviso é o `AlertaOpcoesIndisponiveis`
  (`components/`, não repetido nos quinze dialogs: a frase tem que ser uma
  só), e travar o botão segue **duas regras que não se deduzem do
  diff**: (1) o `useEscolas` roda em todo perfil, mas só o admin global vê
  o select e manda o campo, então contar a falha dele sem
  `ehAdminGlobal &&` deixaria o **diretor** sem criar turma por causa de
  uma lista que ele não consome; (2) travar só vale pro campo que a
  própria validação já exige — professor na ocorrência e pagador no plano
  são opcionais, e plano/escola só entram na criação, não na edição, então
  ali o aviso aparece e o botão continua vivo. Quando os dois conjuntos
  diferem, o dialog tem `falhouCarregar` (aviso) e `bloqueiaEnvio`
  (botão) separados. Tem teste de mutação travando as três decisões.
- **Mensagem de erro do backend como UI**: nos dialogs do financeiro o texto do DRF é mostrado em vez de um "erro ao salvar" genérico — é ali que as invariantes se explicam ("Ana já tem fatura na competência 03/2026", vigência sobreposta). Centralizado em `features/financeiro/erros.ts`.
- **Status badges com paleta da marca** (em vez de red/amber/green/blue genérico do Tailwind):
  - Ocorrência aberta → terracota clarinho + texto destructive.
  - Ocorrência em andamento → mostarda clarinho + texto âmbar.
  - Ocorrência resolvida → olive clarinho + texto olive.
  - Ocorrência arquivada → muted neutro.
  - Presença P/A/J/R → olive / terracota / mostarda / petrol pastel (em `presenca/constants.ts`).
  - Fatura pendente/pago/vencido/cancelado → mostarda / olive / destructive / muted (em `financeiro/constants.ts`). Segue o molde de **ocorrência** (`DESIGN.md` §6.1.1), não os pastels de presença: status de fatura é estado de documento.
- **Família mostarda virou token** (out/2026, `DESIGN.md` §6.3): todo status "em curso / rascunho / atenção sem urgência" usa `bg-mostarda text-ambar` (e `bg-mostarda/40` no alerta translúcido), com `--mostarda`/`--ambar` no `:root` do `index.css`. Eram **nove** usos do hex `#FCE7BC`/`#854D0E` espalhados em dez arquivos quando foi extraído. A **presença ficou fora**: os tons dela são outros e têm estado de hover (`#F8DBAE` → `#F2CB8E` no `J`); só o tom de texto coincide, e convergir os dois conjuntos é decisão de desenho.

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
- **Exceção: CI vermelho na `main`.** Aí commitar, pushar e abrir a PR do conserto é **autorizado de antemão** (decisão do Diniz, out/2026) — esperar resposta deixa a branch default quebrada, e quem for trabalhar em cima dela herda o vermelho. Merge continua sendo só quando ele pedir. A autorização é pro **conserto**, não pra ampliar escopo de carona. **Antes de consertar, `git fetch` e conferir se já não entrou fix**: com várias sessões no mesmo repo, o vermelho que você viu pode ter sido resolvido em paralelo, e o segundo conserto sobrescreve o primeiro.
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
- Frontend: `npm --prefix frontend test && npm --prefix frontend run build`.
  Desde out/2026 existem **testes de componente** (ver `src/test/` no mapa):
  `npm test` roda os de função pura (`lib/datas.test.ts`) e os de tela no
  mesmo comando, e o CI já executa os dois.
- O CI roda os dois no job de frontend. O `npm run lint` **não** é gate ainda: caiu de 30 pra **5 problemas** (out/2026). O padrão de casa pros FormDialogs é estado nascendo dos props mais `key={formKey}`, e quando o valor depende de query (escola/turma única, lecionamentos, conteúdo de aula, grade de notas, form do plano) ele é **derivado**: o estado guarda só o que o usuário tocou. Sobram: 3 `react-refresh` (forma padrão do shadcn e dos contexts — configuração, não código; o quarto era a `InicioPage` do portal exportando um formatador de data, e caiu quando ele virou `lib/datas`), 1 `no-control-regex` no `NomeArquivoDialog` (o código **está correto**, sanitiza nome de arquivo; cabe disable explicado) e 1 `set-state-in-effect` no `NotasFinaisPage`, que é decisão de desenho: o efeito dispara uma **escrita** (POST que inicializa as linhas) a partir dos três selects, então mover pros handlers significa três gatilhos que só devem disparar com o trio completo — ou discutir se essa inicialização idempotente não deveria ser query em vez de mutation.

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
> NÃO focar agora em: portal **do aluno** (login de aluno), app mobile
> **nativo** (React Native etc.), gamificação, LMS, IA, microserviços,
> Kubernetes, arquitetura enterprise. O veto é a app **nativa** reescrita;
> empacotar o front atual como PWA é outra conversa — ver "App mobile (PWA)"
> abaixo.
> Em andamento (out/2026): portal **do responsável**, só leitura — ver FASE 6
> e [`PORTAL.md`](./PORTAL.md). Não confundir os dois.
> Em andamento (out/2026): **financeiro** — cobrança de mensalidade, ver
> FASE 7 e [`FINANCEIRO.md`](./FINANCEIRO.md). Saiu do "não focar agora" por
> decisão de out/2026: é contas a receber procedural (quem deve o quê, desde
> quando), que é exatamente o posicionamento de ERP administrativo — não é
> gateway de pagamento nem ERP financeiro completo. A emissão de boleto/Pix
> continua sendo de terceiro.
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
8. ✅ **Dashboard com métricas** (cards + filtro por turma) — **completo**:
    reincidência e presença média entregues como agregado do backend
    (`GET /relatorios/dashboard/`, janela de 30 dias, reincidente a
    partir de 2 ocorrências). Presença média marca `tomDestaque` abaixo
    dos 75% da LDB e distingue "ninguém veio" de "ninguém fez chamada".
    Ver o mapa de `relatorios/`.
9. ✅ **Filtro de período** em Ocorrências/Presença — **completo**: o
    status virou múltipla escolha (`MultipleChoiceFilter`), porque "o que
    ainda está em aberto" é aberta mais em andamento, uma pergunta só, e
    com um status por vez virava duas consultas e duas folhas impressas.
    Um valor só continua funcionando, então export e links salvos seguem
    válidos. Duas coisas que a mudança obrigou e não eram óbvias: o
    cabeçalho do PDF lia `query_params.get("status")` e passaria a mentir
    sobre o recorte (virou `getlist`), e o axios 1.x serializa array como
    `status[]=a`, que o `django-filter` não lê — sem
    `paramsSerializer: { indexes: null }` na instância o filtro chegaria
    **vazio** no backend, em silêncio. Na tela, o `Select` virou
    `DropdownMenu` de checkboxes (o `DropdownMenuCheckboxItem` já existia
    em `components/ui` e nunca tinha sido usado).
10. ✅ **Exportação de relatórios** — PDF/CSV/Excel. Três relatórios na
    app `relatorios`: frequência por turma (`TurmaDetalhePage`),
    ocorrências filtradas (`OcorrenciasPage`) e cadastral de alunos
    (`AlunosPage` e `TurmaDetalhePage`). Todos saem com o mesmo recorte
    da tela que os abriu, os dois últimos como action do viewset que já
    tem o filtro e o escopo. PDF via WeasyPrint com teto de linhas
    (síncrono na request), CSV/XLSX via tablib sem teto.
11. **Diário de classe (`RegistroAula`)** — **FUNCIONAL (5 fatias mergeadas)**. Pedido de cliente: professor lança o conteúdo programático ministrado por aula; direção dá o visto. Decisões travadas: grade de horário (`Lecionamento.dias_semana`) projeta slots, workflow de 3 estados (`rascunho`→`lancado`→`conferido`), conteúdo texto livre, conferência uma a uma (sem lote). Navegação da direção: aba Professores → clica no professor → **`ProfessorDetalhePage` (ficha 360º com tabs Diário/Lecionamentos/Ocorrências/Dados)** → lista cronológica das aulas → confere → **exporta PDF** (com filtros + espaço de assinatura). Pendência de conferência vira card no Dashboard. Fatiado em PRs — **todas mergeadas**: ① backend (#89) · ② PDF (#94) · ③ front diário do professor (#90) · ④ front ficha do professor (#91) · ⑤ card no dashboard (#93). Ficha ganhou também filtros (período+status), agrupamento por mês e contadores; perfil **`coordenador`** entrou como alias de diretor junto da ficha (#91).

   ✅ **Redesenho do PDF do diário — ENTREGUE (PR #97).** Layout reformulado em 4 eixos: status consolidado num badge único (sem repetição da nota "Conferido por X em Y"); cabeçalho/meta reorganizado em blocos; estrutura da lista trocada de tabela pra blocos por aula com conteúdo respirando; identidade visual alinhada (olive/ferrugem/sepia + serifa nos títulos + badges tintados: rascunho mostarda, lançado ferrugem, conferido olive). Tocado por um CC no Claude Desktop. ⚠️ WeasyPrint segue sem renderizar no Windows — iteração local exige container/preview.

   ⏱️ **Latência do PDF** — WeasyPrint é síncrono na request (~1-2s) somado ao cold start do free tier do Render. Fix real (assíncrono) é o item 12 (fila); aceitável por ora.

   ✅ **Smoke test do Sentry CONFIRMADO em prod** (era pendência da FASE 2): o 404 do endpoint de PDF (antes do #94 deployar) caiu no painel — prova que `SENTRY_DSN` está setado no Render e que a captura de 4xx (#92) está ativa.

### FASE 4 — Comunicação Institucional — FUNCIONAL EM PROD
11. ✅ **Email ao responsável na ocorrência (entrega real em prod)** — campos `nome/email_responsavel` no Aluno; envio em thread daemon (fire-and-forget) com `EMAIL_TIMEOUT=10s`, protegido por try/except. Backend de email = **Brevo via HTTP API** (`django-anymail`) — Resend e Gmail SMTP foram tentados e falharam pelo bloqueio de SMTP outbound do Render free (set/2025). Sender verificado: ver `CLAUDE.local.md` (repo público — email fora daqui). 300 emails/dia free. PRs #43 (campos), #44 (off-thread fix), #48 (Brevo). **Validado em 2026-05-30 com entrega externa.** **Múltiplos responsáveis e `recebe_notificacao` entregues** (as quatro fatias do `RESPONSAVEIS.md`, PRs #120–#122 + a tela de vínculos): o destino agora é o vínculo, com fallback pro campo antigo só quando o aluno não tem vínculo nenhum, e a secretaria cadastra o segundo responsável pela tela `/responsaveis`, sem `/admin/`. Falta: telefone (outro canal, outro provedor).

    **O desenho completo está em [`RESPONSAVEIS.md`](./RESPONSAVEIS.md)**
    (out/2026). É a convergência que o `PORTAL.md` adiou: o email saía pelo
    campo de texto `Aluno.email_responsavel` enquanto o portal lia os
    vínculos `ResponsavelAluno`, então quem estava vinculado só pelo M2M
    **via no portal e não recebia email**. Quatro fatias, todas entregues.
    A armadilha central está registrada lá e vale pra qualquer mexida
    futura no envio: o fallback pro campo antigo dispara por **ausência de
    vínculo**, nunca por ausência de destino — senão o opt-out vira nada.
12. **Email assíncrono dedicado** — fila (Celery/Dramatiq/RQ) com retry + histórico, quando o volume crescer. Hoje é thread daemon best-effort. PENDENTE.
13. ✅ **Timeline do aluno** — app `timeline` (sem modelo) +
    `/alunos/:id/timeline`. Centraliza ocorrências, presença e as
    mudanças de cadastro que o audit log guarda (é o "reaproveitar
    HistoricalRecords" que este item pedia), em ordem cronológica
    decrescente, com filtro de janela e agrupamento por mês. Leitura
    pura: cada bloco linka pra tela onde o registro é editado. Duas
    entradas — ⋯ da `AlunosPage` e botão na `BoletimPage` (a timeline é
    o complemento do boletim: notas e frequência de um lado, o que
    aconteceu do outro). Decisões e armadilhas no mapa de `timeline/`;
    o que ficou de fora de propósito: comunicados enviados e notas de
    avaliação (esta sobreporia o boletim).

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

**6b entregue**: `GET /responsaveis/` em `apps/portal/views_staff.py`
(`IsAdminOrDiretor`, escopado por escola, paginado, busca incluindo nome do
aluno) + tela `/responsaveis` com badge de situação e botão Convidar.
Nasceu somente-leitura; a fatia 4 do `RESPONSAVEIS.md` acrescentou
cadastro de conta e escrita de vínculo na mesma tela (ver o mapa do
`portal/`). A `situacao` é derivada (`Exists`/`Subquery`, sem N+1) e tem
cinco valores: os três previstos mais `convite_expirado` e `inativo`, porque
exibir "convidado" pra convite vencido faria a secretaria esperar por nada.
O `convidar` da fatia 3 migrou pra `urls_staff.py` com o nome de rota
intacto.

**Status (out/2026):** todas as oito fatias entregues — backend do portal
(#106–#110), mural do staff (#111), lado do pai (#116) e tela
"Responsáveis" (6b). Decisões, invariantes de segurança e achados dos CRs
estão no `PORTAL.md` (os de segurança, no `CLAUDE.local.md`). Com a fatia 6
deployada o portão do convite caiu; o primeiro convite real deve ser pra si
mesmo, como conta de teste, antes de ir pra uma família.

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

### FASE 7 — Financeiro — EM ANDAMENTO

Cobrança de mensalidade. Desenho, decisões e invariantes em
[`FINANCEIRO.md`](./FINANCEIRO.md). Resumo do que já está decidido, pra
não reabrir discussão:

- **A recorrência é nossa, não do gateway.** Asaas/Vindi têm assinatura
  nativa; não usamos. Bolsa, desconto variável, competência e reemissão
  são regra da escola, e com a recorrência lá cada mudança vira chamada
  de API — além do histórico financeiro passar a morar no provedor, o que
  transforma "trocar de gateway" em migração de dados.
- **Geração por management command + cron**, idempotente pela constraint
  de banco. O projeto não tem fila (item 12 segue pendente); quando
  tiver, a geração migra sem mexer no modelo.
- **Gateway: Asaas**, atrás de interface (`gateways/base.py`), com client
  próprio fino em `httpx` — não existe SDK Python maduro (os que existem
  têm ≤3 estrelas; a maturidade do Asaas está no PHP).
- **O contas a receber funciona sem gateway**: a escola que recebe Pix na
  conta e dinheiro na secretaria registra `Pagamento` manual. O gateway é
  integração, não dependência.
- **Notificação sai por `apps/portal/destinatarios.py`**, como ocorrência
  e comunicado — o pai vinculado só pelo M2M tem que receber
  (`RESPONSAVEIS.md` §4.1).

Fatias: 1) models · 2) API DRF · 3) services + geração recorrente ·
4) gateway Asaas · 5) webhook + conciliação + notificação · 6) frontend.

**Fatias 1 a 6b entregues — o módulo está completo.** Os quatro modelos
mais o `EventoWebhook` (escopo por escola,
audit log, admin com inlines na fatura), a API REST sob `/api/v1/`
(`planos-cobranca/`, `faturas/`, `fatura-itens/`, `pagamentos/`) e o
`services.py` com geração recorrente idempotente, conciliação (registro e
estorno) e job de vencidas, mais dois management commands pra cron. 150
testes. **O módulo já opera sem gateway**: a escola cadastra o plano, o
cron gera as faturas e a secretaria registra o Pix ou o dinheiro que
recebeu. Regra travada na geração (`FINANCEIRO.md` §2.8): na virada de
contrato no meio do mês cobra o plano **mais antigo** que pega a
competência — escolhido na aplicação, porque deixar o unique de banco
decidir faria o valor do boleto depender da ordem de inserção.

**Fatias 6 e 6b entregues** (frontend): `/financeiro` (faturas),
`/financeiro/planos` e `/financeiro/alunos/:id` (ficha do aluno), as duas
primeiras sob um item só de sidebar com abas internas, escondido
de professor e inspetor via `podeVerFinanceiro`. Detalhe da fatura em dialog
(composição + pagamentos + encargos do dia, com estorno), registro de
pagamento com valor sugerido pelo `valor_atualizado`, e "Nova fatura" avulsa
— que existe porque o cron ainda não está configurado em nenhum ambiente e
sem ela a tela nasceria vazia. **Com isso a escola opera o módulo inteiro
pela UI, sem `/admin/`.**

A **ficha do aluno** (6b) tem endpoint próprio
(`GET /financeiro/alunos/<id>/`, `APIView` sem modelo, molde de
`boletins`): devolve totais mais contratos, faturas e pagamentos numa
requisição. **Os totais são somados em Python sobre os métodos do modelo,
nunca em SQL** — `saldo()` trava em zero no pagamento a mais, e
`Sum(valor - valor_pago)` faria o excesso de uma fatura abater a dívida de
outra, mostrando dívida menor que a real. Três entradas (nome do aluno na
lista de faturas, ⋯ da `AlunosPage`, botão "Financeiro" na
`TurmaDetalhePage` → `/financeiro?turma=<id>`), todas nível-diretor.

Fatias 4 e 5 entregues (out/2026): o adaptador do Asaas, a emissão e o
webhook de conciliação com aviso por email ao responsável. O bloqueio de
rede que travava a fatia 4 caiu quando `docs.asaas.com` entrou nos
domínios liberados do ambiente — o adaptador foi escrito contra o
contrato real (OpenAPI deles), que era a condição registrada aqui.

**Pendência operacional de produção** (o que falta não é código): as
**três** entradas de cron (`financeiro_gerar_faturas` dia 1,
`financeiro_emitir_cobrancas` meia hora depois,
`financeiro_marcar_vencidas` diário) precisam ser configuradas no
servidor que hospedar o backend — sem elas nenhuma fatura é gerada nem
emitida automaticamente, e é a tela "Nova fatura" que cobre o buraco
hoje. Comandos e horários no `FINANCEIRO.md` §2.2. Faltam também as
quatro envs do gateway (`ASAAS_API_KEY`, `ASAAS_BASE_URL`,
`ASAAS_TIMEOUT`, `ASAAS_WEBHOOK_TOKEN` — §6) e o cadastro do hook no
painel do Asaas apontando pra `/api/v1/financeiro/webhooks/asaas/` com o
mesmo token. Sem nada disso o módulo segue operando manualmente: a
secretaria registra o Pix ou o dinheiro que recebeu, que é como ele já
funciona hoje.

**UI da emissão entregue** (out/2026): item "Emitir cobrança" no ⋯ da
`FaturasPage` **e** da `FichaFinanceiraPage` (as duas compartilham o
`FaturaDetalheDialog`, então ligar numa obrigava ligar na outra),
confirmação em dialog próprio no molde do `FaturaCancelDialog` — a ação
sai do sistema, cria cobrança de verdade e é o provedor quem avisa o
pagador, sem desfazer prático — e o `link_pagamento` no detalhe da
fatura, que é o resultado visível da emissão.

Duas decisões que valem pra quem mexer: `podeEmitirCobranca` mora em
`financeiro/constants.ts`, e não repetida nas duas telas, porque duas
cópias divergiriam no dia em que a regra mudar e aí uma das duas
ofereceria botão que só devolve erro; e o erro **não** vai pra toast, vai
pro `Alert` dentro do dialog, porque é a frase do backend que diz o que
falta preencher ("o responsável está sem CPF", "este plano não tem
pagador definido", "cobrança online não está configurada") e toast some
antes de a secretaria agir. Sem `ASAAS_API_KEY` o botão aparece e
devolve a terceira dessas mensagens: o front não tem como saber que o
gateway não existe, e inventar um endpoint de capabilities pra uma
instalação só não se paga.

**Campo de pagador entregue** (out/2026): select no
`PlanoCobrancaFormDialog`, alimentado pelos vínculos **do próprio aluno**
(`/vinculos-responsavel/?aluno=`) e não por toda a escola, porque o
`clean()` do plano exige que o pagador seja responsável daquele aluno —
uma lista mais larga ofereceria opção que o backend recusa. Trocar o
aluno limpa o pagador. O campo é opcional: a escola que recebe Pix na
conta e registra à mão nunca precisa de um, e exigir travaria o jeito
como o módulo já opera. Limitação conhecida: o endpoint de vínculos não
diz se o responsável tem CPF, então pagador sem CPF só é pego na emissão
— que devolve a frase do backend no `Alert` do dialog.

**`link_pagamento` no portal entregue** (out/2026): aba "Mensalidades" na
página do filho, servida por `GET /portal/alunos/<id>/faturas/`. Duas
decisões registradas no mapa de `portal/`, porque nenhuma se deduz do
código: quem vê é **todo responsável vinculado** (não só o `pagador`), e
**fatura cancelada fica de fora**.

### App mobile (PWA) — consideração (out/2026), NÃO comprometido

Ideia levantada pelo Diniz: empacotar o **frontend atual** como **PWA**
(`manifest.json` + service worker, mesmo build já no Vercel) pra dois públicos
que pertencem ao celular — o **responsável** (portal, leitura) e o **professor**
na hora de **lançar presença** (chamada em sala). Não cruza o posicionamento:
continua sendo responsável lendo + professor operando, não app do aluno, e PWA
não é app nativo (o veto da visão estratégica é a reescrita nativa, não isto).

O que já joga a favor (nada a construir):
- Portal `/portal` é mobile-first, em chunk próprio (`React.lazy`).
- A chamada (`PresencaDetalhePage`) já é responsiva e tem **optimistic update**.
- "Ficar logado" já funciona: JWT `ACCESS 60min` / `REFRESH 7d` com
  `ROTATE_REFRESH_TOKENS` + `BLACKLIST_AFTER_ROTATION`
  ([`config/settings.py`](./config/settings.py) §SimpleJWT) + refresh automático
  no 401 ([`frontend/src/lib/api.ts`](./frontend/src/lib/api.ts)). Token no
  `localStorage` persiste entre aberturas; com a rotação, quem usa dentro de 7
  dias **nunca reloga**. Passo barato pra "praticamente nunca sair": subir
  `REFRESH_TOKEN_LIFETIME` pra ~30d.

Divisor de esforço (a decisão que define o tamanho): a chamada precisa funcionar
**offline** (sala sem sinal)? O optimistic update de hoje **não** é offline —
assume a API no ar e faz rollback se cair.
- **Com conexão na sala** → PWA simples, ~1-2 PRs (manifest + SW + polir touch da
  lista de presença).
- **Sem sinal na sala** → fila local (IndexedDB) + sync + conflito (a unique
  `(escola, turma, data)` ancora o merge). Frente de semanas, não "de graça".

Trade-off de segurança: refresh longo no `localStorage` amplia a janela de um
token roubado (baixo risco pro pai só-leitura, maior pro professor que escreve).
O endurecimento é **httpOnly cookie**, já previsto na FASE 5 item 15 — não é
pré-requisito do PWA, é evolução.

Degrau seguinte, só se pedirem loja/push nativo: **Capacitor** embrulha esse
mesmo PWA num app publicável (iOS/Android). Web push no iOS é fraco — esse é o
gatilho real pra Capacitor. React Native segue fora (reescrita, não compensa).

Status: **consideração, nada iniciado.** Entra depois da migração OVH (prazo
real; ver meta de curto prazo), que é prioridade.

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

### Higiene pós-deploy — atacar quando o ambiente novo nascer
Pendências de segurança de produção ficam no `CLAUDE.local.md` (não versionado — repo é público). Resolvem quando um ambiente novo nascer com env vars novas, seja a OVH depois da venda ou um Postgres free de reposição.
- ✅ Frontend chama `/auth/logout/` no logout (invalida o refresh) — `AuthContext.tsx`.
- 🟢 Placeholder "(YYYY-MM-DD)" da presença — cleanup cosmético.

### Backup do Render — feito (serve pra migração e pra salvar a demo)
- Dump custom format gerado via `docker run --rm postgres:18 pg_dump -Fc` apontando pra External Database URL (Virginia). Saiu em `backups/render_*.dump` (~222 KB, 469 TOC entries, PG 18.3).
- Smoke test do restore num container PG 18 local: passou em ~4s, contagens conferem (1 escola, 4 turmas, 50 alunos, 11 usuários, 7 ocorrências, 5 RegistroPresenca + 55 ItemPresenca, 2 RegistroAula, 2 PlanoEnsino).
- `backups/` está no `.gitignore` (linha 34) — dump não vaza no commit.
- Comando de seed reproduzível em qualquer ambiente novo: `python manage.py popular_alunos_mock --escola-id 1 --turma "Mock 35" --quantidade 35` (PR #101). Idempotente.

### Senhas / acesso — TUDO ENTREGUE
- ✅ Tela "Trocar minha senha" (`ContaSenhaPage`).
- ✅ Reset por email (`EsqueciSenhaPage` + `RedefinirSenhaPage`) via Brevo.
- ✅ Admin/direção reseta senha de terceiro pela UI — action `enviar-reset-senha` no `UsuarioViewSet` + botão na ficha do professor / ⋯ na listagem. PR #100.
- ✅ **`UsuariosPage` entregue** (out/2026) — a limitação acima caiu. Tela
  `/usuarios` com busca, badge de perfil, toggle "Mostrar inativos",
  criação/edição, envio do link de senha e (des)ativação. Lista
  professores junto, com o ⋯ linkando pra ficha: esconder daria dois
  lugares pra procurar a mesma pessoa, duplicar daria duas verdades
  sobre ela.

  **A tela exigiu afrouxar permissão, e esse é o detalhe que importa.**
  O backend barrava não-admin de criar ou editar conta de nível-direção
  (`PERFIS_PRIVILEGIADOS` na criação, `_CAMPOS_SO_ADMIN` no update), ou
  seja, barrava exatamente o caso que este item nomeia — a tela sairia
  sem fazer a única coisa pela qual existe. Decisão de out/2026: a
  direção gere os próprios pares **na própria escola**. O movimento é
  lateral (secretaria, coordenador e diretor são aliases uns dos
  outros), então o que se ganha tomando uma conta dessas é persistência,
  não alcance — e `Usuario` é auditado.

  As linhas que **não** se mexem, cada uma com um teste travando os dois
  lados: `perfil=admin` nem criado nem promovido (é o que separa lateral
  de escalada); `escola` admin-only no update (pulo de tenant), liberada
  na criação presa à escola do autor (o cadastro de professor depende);
  `password` admin-only no update (takeover silencioso — o caminho da
  direção é o link de reset, que vai pro email do alvo); a conta do
  admin global intocável por não-admin em editar, apagar e resetar; e
  ninguém muda o próprio perfil nem se desativa (auto-tranco: dentro da
  escola não sobraria quem destrancasse).

  Conta criada pela tela nasce **sem senha utilizável**
  (`set_unusable_password()`), então "existe" e "já entra" viraram
  estados diferentes — o serializer expõe `senha_definida` e a linha
  ganha o badge "aguardando senha", senão a secretaria reenvia link a
  esmo.

  Achado de teste de mutação que vale pra quem mexer: o guard da conta
  do admin **não estava coberto por nada**. O admin global tem
  `escola=None`, então o `get_queryset` já o escondia e a resposta saía
  404 pelo escopo; as asserções aceitavam `(403, 404)` e passavam pelo
  motivo errado. Os testes agora usam um admin **com** escola
  preenchida, alcançável pelo queryset, e exigem 403 exato.

### Meta de curto prazo — STATUS
Infra ✅, segurança operacional ✅, audit log ✅, comunicação por email **funcional em prod** ✅, **Sentry em prod ✅ (DSN setado + smoke test confirmado + captura de 4xx)**, **identidade visual completa ✅ (Login + Sidebar + Dashboard + listagens + detalhes + forms; DESIGN.md durável travado)**, auto-escopo de escola ✅, **diário de classe ✅ (5 fatias + redesenho do PDF #97)**, **fluxo de senha completo ✅ (próprio + esqueci + admin reseta de terceiro, PR #100)**, **performance ✅ (índices, annotates, bulk, prefetch + escopo obrigatório nos endpoints matriz)**. **Migração pra OVH: condicionada à venda** (decisão de out/2026). Não é
pré-requisito pra vender — é consequência de ter vendido. Enquanto não
houver escola pagante o sistema segue em Render free + Vercel, e a frente
ativa é **produto**, não infra.

O que **não** espera a venda é a sobrevivência da demo. O Postgres free do
Render expira sozinho, e é ele que sustenta o ambiente que se mostra pra
escola: se morrer antes de alguém fechar, o instrumento de venda vai com
ele. O remédio não é a OVH — é provisionar outro Postgres free e restaurar,
com o dump custom format que já existe (PG 18, ~222 KB, restore
smoke-testado num container local) e o seed reproduzível
(`popular_alunos_mock`). Meia hora de trabalho, não uma migração.

**A data de expiração precisa ser conferida no painel do Render.** Este
arquivo registrava duas afirmações que não fecham entre si: que a validade
de ~90 dias voltou a contar com o restart de out/2026, e que vence "por
volta de 2026-11-05". Noventa dias a partir de 2026-10-06 cairia em
janeiro/2027, não em novembro. Até alguém abrir o painel, tratar a data
como desconhecida em vez de assumir qualquer uma das duas — o tamanho da
folga muda o quanto a demo aperta.

Quando a venda acontecer, a migração já está mapeada: provisionar VPS OVH,
restaurar dump, ajustar `ALLOWED_HOSTS`/`CSRF_TRUSTED_ORIGINS`/
`CORS_ALLOWED_ORIGINS`/`DATABASE_URL`, rotacionar `SECRET_KEY`, trocar
`VITE_API_URL` no Vercel e criar as duas entradas de cron do financeiro.
Frontend continua no Vercel — só backend+banco saem do Render.

Frentes ativas enquanto isso: **melhorias de frontend** (mapeamento
iniciado em out/2026) e fila assíncrona pra email (item 12).

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
