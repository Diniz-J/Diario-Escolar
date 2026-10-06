# PORTAL.md — Portal do Responsável

Documento de desenho do portal de leitura para responsáveis. Decidido em
out/2026. Leia antes de mexer em qualquer coisa sob `apps/portal`,
`apps/materiais` ou `frontend/src/portal`.

Este arquivo é versionado em **repo público**: nada de credencial, token,
URL de admin ou detalhe de vulnerabilidade de produção aqui.

---

## 1. O que é (e o que não é)

Área autenticada onde o **responsável** acompanha o que a escola registrou
sobre os filhos vinculados a ele. Leitura, não operação: o responsável não
cria, não edita, não comenta.

**Não é portal do aluno.** O aluno continua sem login — o `Aluno` é dado de
cadastro, não identidade. Isso mantém de pé a posição do produto no
`CLAUDE.md` ("não é app do aluno") e evita a questão de consentimento de
menor de idade.

**Não é LMS.** Não há entrega de atividade, correção, chat, nota lançada
pelo pai nem gamificação. O mural de materiais é um quadro de avisos com
link, não uma sala de aula.

### Escopo da v1

| O responsável vê | Origem |
|---|---|
| Comunicados da escola | `apps/comunicados` (já existe) |
| Boletim do filho | `apps/boletins/services.py` (já existe, agregação) |
| Ocorrências do filho | `apps/ocorrencias` (já existe) |
| Mural de materiais | `apps/materiais` (novo) |

Fora da v1: anexo de arquivo, notificação push, mensagem bidirecional,
login do aluno, múltiplas escolas por responsável.

---

## 2. Decisões e por quê

**Só o responsável autentica.** Metade da superfície de risco de
responsável + aluno, e o aluno nunca precisou logar no modelo atual.

**Conta só por convite da escola.** Auto-registro, mesmo validando
matrícula contra o cadastro, permite que qualquer pessoa tente se declarar
responsável de qualquer aluno — e matrícula é previsível, então viraria
vetor de enumeração de alunos. A escola convida o email que já está no
cadastro; o responsável apenas define a senha.

**Identidade em modelo separado, com autenticação própria.** Não é um
`perfil` novo no `Usuario`. Usuário externo não encosta na superfície do
staff: todas as permission classes de lá têm bypass de admin, e é
exatamente ali que a escalada corrigida na PR #105 morava. Um furo de
permissão no staff não pode passar a vazar para fora da escola.

**Mural de texto e link, sem upload.** Não existe `FileField` nem
`MEDIA_ROOT` no projeto, o `STORAGES["default"]` é `FileSystemStorage` e o
disco do container do Render é efêmero — arquivo subido desapareceria no
próximo deploy. Anexo exigiria object storage externo, que é infra nova.
Link resolve o caso real ("segue a lista de exercícios") hoje, e dá pra
evoluir para anexo quando houver necessidade comprovada.

**Mesma aplicação de frontend, sob `/portal`.** Um deploy, um design
system, uma pipeline. O custo é disciplina, não arquitetura — ver as
invariantes de front na seção 4.

**Convite individual na UI, mais comando de lote.** O Brevo free entrega
300 emails/dia e **a cota é compartilhada com os comunicados**. Uma escola
inteira são dezenas ou centenas de convites: um botão "convidar todos"
esgotaria o dia e derrubaria os comunicados aos responsáveis junto. O dia a
dia é individual; o onboarding inicial é um management command que respeita
a cota e retoma de onde parou.

**Aluno desativado não corta o acesso.** O vínculo sobrevive ao soft
delete: o responsável segue consultando boletim e ocorrências já
registrados, mas para de receber comunicado novo — consistente com o envio
atual, que já filtra `ativo=True`. O soft delete do projeto existe
justamente para preservar histórico.

---

## 3. Modelo de dados

```
Responsavel                      ResponsavelAluno            Aluno
  email (único por escola)   ┌──  responsavel ──┐         (já existe)
  nome                       │    aluno ────────┼──────────────┘
  password (hash)            │    unique(responsavel, aluno)
  ativo                      │
  escola FK ─────────────────┘

ConviteResponsavel               Material (BaseModelEscopado)
  responsavel FK                   turma FK, disciplina FK
  token_hash                       professor FK
  expira_em                        titulo, descricao, link (opcional)
  usado_em (nulo = não usado)      publicado_em, ativo
```

`Responsavel` herda `AbstractBaseUser` — dá `set_password`/`check_password`
e `last_login` de graça — mas **não** é `AUTH_USER_MODEL`. O Django só
admite um, e esse continua sendo `Usuario`.

`ResponsavelAluno` resolve de quebra o "múltiplos responsáveis por aluno"
que já estava listado como pendência no `CLAUDE.md`.

`ConviteResponsavel` segue o molde do `PasswordResetToken` que já existe:
token hasheado em repouso, uso único, com expiração.

`Material` valida `Lecionamento` ativo para o trio professor/turma/
disciplina, igual o `RegistroAula` do diário de classe já faz.

### Convivência com `Aluno.email_responsavel`

O campo de texto continua existindo e **continua sendo o destino do email
de comunicado e de ocorrência** na v1. Não troco o que funciona em produção
no mesmo passo que crio o modelo novo. A duplicidade é consciente e
temporária; convergir é fatia posterior.

A escola não redigita nada: `manage.py portal_semear_responsaveis` converte
os campos atuais do aluno em contas e vínculos, deduplicando por email
(irmãos viram uma conta com dois vínculos).

**Por que management command e não data migration.** Primeiro, migration
não é testável sem dependência nova, e esta lógica — agrupamento,
deduplicação, nome de fallback — precisa de teste. Segundo, a semeadura
não é parte do schema: é operação de dados que a escola escolhe quando
rodar, e que vale rodar de novo a cada turma nova matriculada. Terceiro, o
projeto já resolve esse tipo de tarefa assim (`popular_alunos_mock`,
`comunicados_retomar`). É idempotente, tem `--dry-run` e `--escola-id`.

**Aluno sem email de responsável é pulado, de propósito.** O email é a
âncora da identidade: é por ele que o convite sai e é com ele que o
responsável loga. Uma conta sem email seria uma linha impossível de
convidar ou autenticar — e como boa parte desses alunos também está sem
`nome_responsavel`, o resultado seria uma pilha de registros anônimos.
Quem está sem email já aparece como tal na listagem de alunos e no log de
entrega dos comunicados. Quando a escola preencher o email, roda o comando
de novo.

---

## 4. Modelo de segurança

As invariantes abaixo não são recomendações. Teste que falha quando alguma
cai é requisito de cada fatia.

### 4.1. Separação de token entre os dois mundos

O risco central deste desenho, e não é óbvio: o SimpleJWT grava o pk do
usuário no claim de id, e o `JWTAuthentication` padrão resolve esse pk
contra o `AUTH_USER_MODEL`, que é `Usuario`. Um token emitido para o
`Responsavel` de pk 3, apresentado num endpoint de staff, carregaria o
`Usuario` de pk 3 — um funcionário real. Responsável viraria servidor da
escola, sem explorar bug nenhum: é o comportamento default das duas
bibliotecas se ninguém separar.

Portanto:

- Todo token do portal carrega um claim de tipo identificando que é de
  responsável.
- A autenticação do portal **recusa** token sem esse claim.
- A autenticação do staff **recusa** token que tenha esse claim.
- Os dois sentidos têm teste. É o primeiro teste da fatia 2, não o último.

Como ficou (fatia 2): o claim é `tipo=responsavel` e o id vai em
`responsavel_id`, **nunca** em `user_id` — segunda camada independente: se
a checagem de tipo falhasse, o staff não acharia `user_id` e recusaria do
mesmo jeito. Token com os dois ids é recusado nos dois lados. O staff usa
`StaffJWTAuthentication` (`apps/common/authentication.py`) como
autenticação padrão e um refresh que recusa o refresh do portal; o portal
usa `PortalJWTAuthentication` (`apps/portal/authentication.py`). Os tokens
do portal são montados sem `for_user()`, que ligaria o `OutstandingToken`
da blacklist ao `Usuario` de mesmo pk.

**Login por email e senha, sem escolher escola.** O email é único por
escola, não global. O login procura as contas ativas com aquele email e
entra na que tiver a senha certa; se mais de uma bater, recusa com 409 —
responsável em várias escolas está fora da v1 (seção 6). Toda outra falha
(email inexistente, conta inativa, conta sem senha, senha errada) responde
o mesmo 401 genérico.

### 4.2. Autorização por vínculo, nunca por id de URL

Toda leitura do portal é filtrada pelos vínculos do responsável
autenticado. Id de aluno que chega na URL é tratado como palpite: se não
estiver entre os vínculos, é 404 — nunca 403, que confirmaria existência.

O responsável não enxerga nada agregado da turma: nem lista de colegas, nem
média da sala, nem contagem de ocorrências de terceiros.

### 4.3. Comunicados

Só aparecem os `enviado`. Rascunho nunca vaza — é texto em revisão pela
direção.

Como ficou (fatia 4), **divergindo** do desenho original ("visível se a
turma do filho estiver entre as endereçadas"): a visibilidade parte do log
de entrega (`ComunicadoDestinatario`), que registra os alunos endereçados
no momento do disparo. Pela turma atual, o filho que trocou de turma
herdaria os avisos antigos da turma nova e perderia os da antiga; pelo log,
cada um vê o que foi de fato endereçado a ele. De quebra: filho desativado
mantém os avisos antigos e não recebe novos (a regra da seção 2), e o aluno
sem email também tem linha no log, então o pai vê no portal o aviso que não
chegou por email. Cada comunicado lista só os filhos **daquele**
responsável que ele alcançou.

O período do boletim também é escopado pela escola do filho: o portal faz
a busca própria do período, e período de outra escola dá 404.

### 4.4. Convite e senha

Token hasheado em repouso, uso único, com expiração. Convidar é ação de
nível-diretor, com rate limit desde o primeiro commit — a lição da PR #105
é que endpoint que dispara email sem limite é email bombing e queima de
cota ao mesmo tempo. Login do portal também tem rate limit, por
brute-force.

Como ficou (fatia 3): um modelo só, `ConviteResponsavel`, com
`finalidade` — **convite** (primeira ativação, disparado pela escola, 7
dias) e **redefinição** ("esqueci a senha", pedido pelo responsável, 1
hora). Os dois links caem na mesma tela (`/portal/definir-senha?token=`).
Link novo invalida os pendentes; email que não saiu invalida o próprio
link, senão o lote nunca mais tentaria aquele responsável. Convite só vale
pra conta **sem** senha: quem já ativou usa o "esqueci". O "esqueci" envia
fora da request (thread), pra o tempo de resposta não revelar quais emails
têm conta.

Trocar a senha derruba as sessões abertas: o token carrega uma impressão
do hash da senha (`senha_ver`), conferida na autenticação e no refresh.
Sem isso, uma sessão roubada sobreviveria ao reset até o refresh expirar.

### 4.5. Frontend

Como portal e administração dividem a mesma origem:

- O storage de token do portal usa **namespace próprio**. Hoje o
  `tokenStorage` usa chaves fixas; sessão de responsável e de staff no
  mesmo navegador não podem se sobrescrever.
- A árvore de rotas do portal não importa componente de rota
  administrativa, para o bundle do pai não arrastar a UI de gestão.
- O backend é a fronteira real. Esconder botão é UX, não segurança.

---

## 5. Fatias de entrega

Cada fatia é um PR próprio, mergeável sozinho.

**Portão: a fatia 2 não sobe antes da PR #105 estar mergeada e
deployada.** É ali que o login externo abre. A fatia 1 é só modelo,
migration e admin — não expõe endpoint nem cria caminho de autenticação,
então pode ser construída e mergeada antes, em paralelo à revisão da
#105.

**Portão: nenhum convite em produção antes da fatia 6.** O link do email
aponta pra `/portal/definir-senha`, tela que só nasce na fatia 6 — antes
disso o responsável cairia num 404, e o convite (7 dias) venceria sem uso.
A fatia 3 pode ser mergeada e deployada; o que espera é rodar o
`portal_convidar_responsaveis` e o botão de convite.

| # | Fatia | Status | Verificação |
|---|---|---|---|
| 1 | `Responsavel`, `ResponsavelAluno`, comando de semeadura, admin | ✅ #106 | Semeadura deduplica irmãos, é idempotente e pula aluno sem email; conta nasce sem senha utilizável; suíte verde |
| 2 | Autenticação isolada do portal (login, refresh, claim de tipo) | ✅ #107 | Token de cada lado recusado no outro; token sem claim recusado nos dois; rate limit no login |
| 3 | `ConviteResponsavel`, convidar, aceitar, reset próprio, comando de lote | ✅ #108 | Convite reusado falha; expirado falha; só nível-diretor convida; lote respeita a cota |
| 4 | Leituras: filhos, comunicados, boletim, ocorrências | ✅ #109 | Responsável A não lê nada do aluno de B; id alheio na URL dá 404; rascunho invisível |
| 5 | `Material` + CRUD do professor + leitura no portal | ✅ #110 | Professor não publica em turma que não leciona; responsável só vê a turma do filho |
| 5b | Tela do professor pro mural (staff) | ✅ #111 | Professor só vê turma/disciplina que leciona no formulário; build limpo |
| 6 | Frontend do portal sob `/portal` | ✅ | Chunk do portal sem string de tela do staff (e vice-versa); `/portal` manda pro login do portal e `/dashboard` pro do staff, verificado em navegador; storage em `portal_*` |
| 6b | Tela "Responsáveis" no staff + botão Convidar | **pendente** | Só nível-diretor convida; status da conta visível; build limpo |

**Onde paramos (out/2026):** o backend do portal está completo e em
produção (fatias 1–5), e o mural do staff também (5b). **Falta todo o lado
do pai** — a fatia 6 — e a tela de convite do staff (6b). Enquanto a 6 não
entra, o portão acima continua valendo: nenhum convite em produção.

### Fatia 6 — entregue (out/2026)

**Separação do bundle** (seção 4.5): hoje o `App.tsx` importa o
`AppRoutes` estaticamente, com todas as telas do staff. A raiz passa a
carregar sob demanda (`React.lazy`) duas árvores — `/portal/*` → app do
portal, resto → app do staff — compartilhando só `QueryClient`, `Toaster`
e os componentes de `components/ui`. Verificar no build que o chunk do
portal não contém tela do staff (procurar uma string só do staff nele).

**Sessão própria** em `features/portal/`:

- Storage com chaves próprias (`portal_access_token`,
  `portal_refresh_token`) — sessão de pai e de staff no mesmo navegador
  não se sobrescrevem.
- Cliente HTTP próprio (`portalApi`), com refresh em `/portal/auth/refresh/`
  que **guarda o refresh rotacionado** (o backend rotaciona e põe o
  anterior na blacklist; o cliente do staff errava isso — corrigido no
  #112).
- `PortalAuthContext` carregando o responsável por `/portal/me/`, e rota
  protegida própria que manda pra `/portal/entrar`.

**Telas** — mobile-first (o pai acessa pelo celular), visual do
`DESIGN.md`:

| Rota | Tela |
|---|---|
| `/portal/entrar` | Login (email + senha) |
| `/portal/esqueci-senha` | Pede o link de redefinição |
| `/portal/definir-senha?token=` | Define a senha — convite **e** reset. É a tela que o link do email abre |
| `/portal` | Início: filhos + comunicados recentes |
| `/portal/alunos/:id` | Abas Boletim (com seletor de período), Ocorrências, Mural |
| `/portal/comunicados`, `/portal/comunicados/:id` | Comunicados, com pra qual filho |

**Requisitos de segurança no front** (saíram dos CRs das fatias 4 e 5b):

- `mensagem` do comunicado renderizada como **texto**, nunca HTML
  (`whitespace-pre-wrap` pras quebras de linha). Nada de
  `dangerouslySetInnerHTML`.
- Link do mural só renderiza se for `http(s)`, com `noopener noreferrer`.
- Boletim em componente **próprio** do portal — não reaproveitar a
  `BoletimPage` do staff (469 linhas, arrasta exportação e PDF).

**Como foi verificado:** o build gera `PortalApp-*.js` (25 kB) separado do
`StaffApp-*.js` (275 kB), e seis strings exclusivas do staff ("Mostrar
inativos", "Planos de ensino", "Notas finais", "Períodos avaliativos",
"Novo comunicado", "Lecionamento") não aparecem no chunk do portal — nem
as do portal no chunk do staff. O roteamento foi exercitado no `dist`
servido, num Chromium headless: `/portal` cai em `/portal/entrar`,
`/portal/definir-senha` sem token mostra o erro de link, `/dashboard`
segue caindo em `/login` (a reestruturação da raiz não quebrou o staff) e
a 404 continua de pé. Zero erro de JS no console.

**Teste manual no preview:** o front não tem teste automatizado e o preview
do Vercel usa a API de produção. Pra ter uma conta de teste, mandar **um**
convite pra si mesmo (`POST /api/v1/responsaveis/<id>/convidar/` num
responsável com o próprio email), copiar o token do email (o link aponta
pro domínio de produção) e abrir `/portal/definir-senha?token=...` no
preview. Um convite, pra si mesmo — não fura o espírito do portão.

### Fatia 6b — tela "Responsáveis" no staff

O `PORTAL.md` decidiu "convite individual na UI", mas nenhuma fatia tinha
tela de responsáveis no staff — mesma lacuna que virou a 5b. Escopo:
listagem das contas da escola com status (sem convite / convidado / ativo),
vínculos com os alunos e o botão **Convidar** (usa o
`/responsaveis/<id>/convidar/` da fatia 3, que já tem rate limit). Precisa
de endpoint de listagem de responsáveis no staff, que ainda não existe. Até
a 6b, o onboarding depois da fatia 6 sai pelo comando de lote
`portal_convidar_responsaveis`.

---

### Como ficou a fatia 5

App `apps/materiais`, molde do `RegistroAula`: `Lecionamento` ativo
obrigatório (no `clean()` e no serializer), professor só vê e edita os
próprios materiais e não publica em nome de outro, direção vê a escola
toda. Link só `http`/`https` — vira `<a href>` no portal, e `javascript:`
seria vetor de ataque no clique. Excluir desativa (some do portal).

No portal, `/portal/alunos/<id>/materiais/` mostra só a turma **atual** do
filho. Filho desativado vê lista vazia, divergindo do resto do portal de
propósito: boletim, ocorrências e comunicados são histórico dele; o mural
é conteúdo corrente da turma, e o aluno transferido seguiria vendo o que a
turma que deixou recebe depois. Material novo **não** dispara email: cada
um seria um lote da cota compartilhada com os comunicados.

A tela do **professor** pra publicar não estava em nenhuma fatia — as seis
originais cobrem só o portal dos pais. Virou a fatia 5b, antes ou junto da
6.

Como ficou (fatia 5b): `MuralPage` em `/mural`, item "Mural" no menu pra
todo o staff. O professor escolhe "turma — disciplina" entre os **próprios
lecionamentos ativos** (nem vê turma que não leciona) e publica em nome
próprio; a direção escolhe o professor e depois um lecionamento dele, e
modera (despublica). Na edição só título, descrição e link mudam — trocar
turma/disciplina/professor é despublicar e publicar outro. Lista paginada
(`?page=`), filtro por turma (e professor, pra direção) e "Mostrar
despublicados". Link abre em aba nova com `rel="noopener noreferrer"`.

## 6. Pendências conhecidas

- Convergir `Aluno.email_responsavel` com `Responsavel.email` (seção 3).
- **Nota aparece pro responsável assim que o professor lança.** O boletim
  do portal reaproveita o `montar_boletim` do staff, que não tem etapa de
  publicação: nota provisória ou digitada errada chega direto ao pai. Se
  virar problema na operação, o caminho natural é o portal mostrar só
  períodos encerrados (o `PeriodoAvaliativo` já calcula `estado`) — fatia
  própria, decidida com a escola.
- Anexo de arquivo no mural, se virar necessidade — depende de object
  storage.
- Responsável com filhos em escolas diferentes: hoje `Responsavel` é
  escopado por escola, o que basta no single-tenant. Vira questão real na
  FASE 5 (multi-tenancy).
- Telefone e flag `recebe_notificacao` no responsável, já listados como
  pendência do email de ocorrência no `CLAUDE.md`.
- PDF do boletim no portal — fora da fatia 4 (WeasyPrint síncrono e lento
  no free tier). Entra se o pai pedir.

### Achados fora do portal (registrados como tarefa, sem PR ainda)

Saíram das revisões das fatias e afetam o **staff**. Dois deles são de
segurança e ficam fora deste arquivo (repo público): o detalhe está no
`CLAUDE.local.md` de quem mantém o projeto.

- **`ProtectedError` vira 500** — o projeto não trata em lugar nenhum;
  apagar registro referenciado por `PROTECT` (ex.: usuário que deu visto
  numa aula) responde 500 em vez de 4xx. Caminho: exception handler do DRF
  em `apps/common/`, mensagem genérica sem listar objetos (vazaria dado
  entre escolas).
- **Refresh do staff derrubava a sessão em ~2h** — o cliente guardava o
  refresh antigo, que o backend põe na blacklist na rotação. Corrigido no
  **#112** (aberto).
