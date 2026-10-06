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
temporária; convergir é fatia posterior, com data migration semeando
`Responsavel` a partir dos campos atuais para a escola não redigitar nada.

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

### 4.2. Autorização por vínculo, nunca por id de URL

Toda leitura do portal é filtrada pelos vínculos do responsável
autenticado. Id de aluno que chega na URL é tratado como palpite: se não
estiver entre os vínculos, é 404 — nunca 403, que confirmaria existência.

O responsável não enxerga nada agregado da turma: nem lista de colegas, nem
média da sala, nem contagem de ocorrências de terceiros.

### 4.3. Comunicados

Só aparecem os `enviado`. Rascunho nunca vaza — é texto em revisão pela
direção. O comunicado é visível se o destino for a escola do filho, ou se a
turma do filho estiver entre as turmas endereçadas.

### 4.4. Convite e senha

Token hasheado em repouso, uso único, com expiração. Convidar é ação de
nível-diretor, com rate limit desde o primeiro commit — a lição da PR #105
é que endpoint que dispara email sem limite é email bombing e queima de
cota ao mesmo tempo. Login do portal também tem rate limit, por
brute-force.

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

| # | Fatia | Verificação |
|---|---|---|
| 1 | `Responsavel`, `ResponsavelAluno`, data migration de semeadura, admin | Migration roda sobre os dados atuais; vínculos conferem; suíte verde |
| 2 | Autenticação isolada do portal (login, refresh, claim de tipo) | Token de cada lado recusado no outro; token sem claim recusado nos dois; rate limit no login |
| 3 | `ConviteResponsavel`, convidar, aceitar, reset próprio, comando de lote | Convite reusado falha; expirado falha; só nível-diretor convida; lote respeita a cota |
| 4 | Leituras: filhos, comunicados, boletim, ocorrências | Responsável A não lê nada do aluno de B; id alheio na URL dá 404; rascunho invisível |
| 5 | `Material` + CRUD do professor + leitura no portal | Professor não publica em turma que não leciona; responsável só vê a turma do filho |
| 6 | Frontend do portal sob `/portal` | Build limpo; sessão de responsável não alcança rota administrativa; storage em namespace próprio |

---

## 6. Pendências conhecidas

- Convergir `Aluno.email_responsavel` com `Responsavel.email` (seção 3).
- Anexo de arquivo no mural, se virar necessidade — depende de object
  storage.
- Responsável com filhos em escolas diferentes: hoje `Responsavel` é
  escopado por escola, o que basta no single-tenant. Vira questão real na
  FASE 5 (multi-tenancy).
- Telefone e flag `recebe_notificacao` no responsável, já listados como
  pendência do email de ocorrência no `CLAUDE.md`.
