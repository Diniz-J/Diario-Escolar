# DESIGN.md — Diário Diniz

Norte visual e de voz pro frontend. Existe pra evitar regressão entre PRs
e pra qualquer agente (humano ou IA) entrar numa tela nova já sabendo
qual paleta usar, qual tipografia chamar e como nomear botão de submit.

Toda mudança visual estrutural deve refletir aqui no mesmo PR.

---

## 1. Marca em uma frase

> Diário em papel: linho de fundo, tinta sépia no texto, olive nas
> decisões, ferrugem nos acentos.

Light mode permanente. Sem toggle de tema. Sem `.dark` ativo. O
`color-scheme: light` no `:root` + `<meta name="color-scheme" content="light">`
desabilitam force-dark de browsers (Opera GX inclusive).

---

## 2. Tokens

Definidos em `frontend/src/index.css`. Editar lá, não inline.

### 2.1 Paleta

| Token       | Hex       | Uso                                                    |
| ----------- | --------- | ------------------------------------------------------ |
| `olive`     | `#4d5a2e` | Primária. CTAs, marca, charts                          |
| `olive-dark`| `#3a4524` | Fundo da sidebar, hover de CTA, charts                 |
| `linho`     | `#ebe2d1` | Fundo principal do app (background)                    |
| `paper`     | `#f5efe0` | Fundo de cards, inputs, áreas elevadas                 |
| `ferrugem`  | `#b07d62` | Accent quente. Links, foco, filete-assinatura          |
| `tinta`     | `#2d2a24` | Texto principal                                        |
| `sepia`     | `#6b6859` | Texto secundário, labels, microtípico                  |
| `creme`     | `#ebe2d1` | Texto sobre fundos escuros (sidebar)                   |

Exposição: cada token vira utility class Tailwind via `@theme inline`
(`bg-olive`, `text-ferrugem`, `border-paper`, etc).

Também ficam mapeados pros tokens semânticos shadcn (`--primary`,
`--background`, `--card`, `--accent`, `--destructive`, `--border`,
`--ring`, etc) — qualquer componente shadcn herda automaticamente.
**Nunca reescreva um componente shadcn por causa de cor** — ajuste o
mapeamento no `:root`.

### 2.2 Tipografia

- `font-heading` → **Fraunces** (serif variable). Carregada via `<link>`
  no `index.html` (não via fontsource, pra evitar conflito de ordem com
  `@import` do Tailwind). Usar em **títulos, valores grandes em métricas,
  marca**.
- `font-sans` → **Geist** (variable). Padrão de corpo.

Escala usada nas telas cristalizadas (referência, não regra rígida):

| Contexto                         | Tamanho           | Família        |
| -------------------------------- | ----------------- | -------------- |
| Título de página                 | `28-34px`         | Fraunces 500   |
| Título de Login                  | `26-30px`         | Fraunces 500   |
| Marca na sidebar                 | `18px`            | Fraunces       |
| Valor de `MetricCard`            | `~50px`           | Fraunces       |
| Body                             | `text-sm/text-base`| Geist         |
| Eyebrow / labels mono            | `text-[10/11px]`  | Geist + uppercase + `tracking-[0.18-0.25em]` |

Tracking apertado em títulos Fraunces (`tracking-tight`) — sem isso ela
estoura largura de container estreito.

### 2.3 Radius e bordas

- `--radius: 0.625rem` (default shadcn ajustado). Escala derivada em
  `--radius-sm/md/lg/xl/2xl/3xl/4xl` via `calc()` em `index.css`.
- Borda padrão: `border` (token `--border` = `#d9cfb8`).
- Sem sombras pesadas. Quando precisar de elevação, usar contraste de
  tom (`bg-paper` sobre `bg-linho`) em vez de `shadow-xl`.

---

## 3. Voz e microcopy

- **Sempre PT-BR**, inclusive nas mensagens de erro e empty states.
- Títulos curtos, **sem ponto final** (`"Alunos"`, `"Ocorrências em aberto"`).
- **Frases completas usam ponto** (`"Que bom te ver de volta."`,
  `"Continue de onde parou."`).
- **Eyebrow / microtípico**: `text-[11px] uppercase tracking-[0.18-0.25em]`
  em `text-sepia`. Usar pra label de seção, perfil ativo, "diário diniz"
  sobre o título, etc. Nunca abuse — máximo um eyebrow por bloco.
- **CTAs no infinitivo** (`"Acessar"`, `"Salvar"`, `"Cadastrar"`),
  não no imperativo (`"Acesse"`, `"Salve"`). Mais seco, menos comercial.
- **"Diniz"**, não "Rodrigo" — tanto pro user dele quanto em qualquer
  copy que mencione o time.
- **Sem emojis**. Em código, em copy, em commit, em PR. Sem exceção.
- **Sem ícones decorativos**. Ícones só com função (`MenuIcon` na
  sidebar mobile, `⋯` em ações). Lucide é a biblioteca.

---

## 4. Filete ferrugem — assinatura visual

Detalhe memorável que costura as telas — metáfora de "filete de
encadernação". Aplicado em:

- **Login** — entre subtítulo e formulário (`h-px w-12 mb-10 bg-ferrugem`).
- **Sidebar** — acima do botão Sair (`h-px w-8 mb-4`).
- **Dashboard** — sob o título de saudação (`h-px w-10`).

Regra: `h-px` + `w-{8,10,12}` (sempre estreito) + `bg-ferrugem`. Posição
canônica: **logo abaixo do título da seção**, antes do corpo. Não usar
como divisor entre linhas de tabela ou seções longas — perde força.

Marcador alternativo (pingo ferrugem) na marca da sidebar:
`inline-block w-1.5 h-1.5 rounded-full bg-ferrugem`. Mesma família.

---

## 5. Componentes cristalizados

### 5.1 Sidebar (`AppLayout.tsx`)

- Desktop: `aside` fixo, `w-60`, `bg-sidebar` (olive-dark), texto
  `text-creme`. Some abaixo de `md`.
- Mobile: vira drawer (shadcn `Sheet`) acionado por hamburguer num
  header também olive-dark. Fecha sozinho ao trocar de rota.
- Item ativo: `border-l-2 border-l-ferrugem` + `bg-white/[0.04]` +
  `font-medium`. Inativo: `text-creme/75` com hover idêntico ao ativo
  exceto pela barra ferrugem.
- Marca no topo: pingo ferrugem + "Diário Diniz" em Fraunces 18px.
- Eyebrow do perfil logo abaixo (`text-[10px] uppercase tracking-[0.2em]
  opacity-60`).
- Rodapé: filete ferrugem + "Sair" + versão em micro mono.

### 5.2 Login (`LoginPage.tsx`)

- Centralizado, `max-w-lg`, `bg-linho text-tinta`.
- Eyebrow olive `· diário diniz` no topo.
- Título Fraunces 26-30px, peso 500, com ponto final.
- Subtítulo `text-sm text-sepia`.
- Filete ferrugem `w-12`.
- Labels em mono uppercase (`text-[11px] uppercase tracking-[0.18em]
  text-sepia`).
- Inputs: `bg-paper border border-border`, foco em `border-ferrugem` +
  `ring-2 ring-ferrugem/20`.
- Erro: `bg-destructive/15 text-destructive border-destructive/30`.
- CTA: `bg-olive text-creme hover:bg-olive-dark`.
- Rodapé: 2 dots (olive + ferrugem) + versão.

### 5.3 Dashboard (`DashboardPage.tsx` + `MetricCard`)

- Container `p-4 md:p-10 space-y-8`.
- Header: saudação Fraunces 28-34px + filete + perfil eyebrow.
- Filtro de visão: label mono + `Select` shadcn em `bg-paper`.
- Grid `md:grid-cols-2 gap-5` com 2 `MetricCard` + 2 cards de listagem.
- `MetricCard` **não usa shadcn `Card`** — é um card próprio com fundo
  `bg-paper`, valor em Fraunces ~50px, sublinha em sépia com separador
  `·` em cor `border`. Variante `tomDestaque` muda o valor pra ferrugem.

### 5.4 Header de página padrão (proposto, ver §7)

Mesma fórmula da Dashboard:

```
[eyebrow opcional]
[Título Fraunces 28-34px tracking-tight]
[filete ferrugem h-px w-10]
[perfil/contexto em eyebrow ou subtítulo]
```

Usar em todas as páginas internas (Alunos, Turmas, Ocorrências, etc).

---

## 6. Status badges

Duas famílias, deliberadamente diferentes — vivem em domínios
distintos:

### 6.1 Ocorrência — paleta da marca

| Status         | Visual                           |
| -------------- | -------------------------------- |
| `aberta`       | Terracota clarinho + `text-destructive` |
| `em_andamento` | Mostarda clarinho + texto âmbar  |
| `resolvida`    | Olive clarinho + olive escuro    |
| `arquivada`    | `bg-muted` + `text-muted-foreground` |

### 6.2 Presença — pastels terrosos

Hex inline em `presenca/constants.ts`, deliberadamente fora dos tokens
pra marcar a especificidade (e porque pastels não existem no shadcn
default):

| Status         | Fundo / Texto                  |
| -------------- | ------------------------------ |
| `P` Presente   | `#D7DCC1` / `#3A4524` (olive)  |
| `A` Ausente    | `#F4DAD3` / `#7C2D1A` (terracota) |
| `J` Justificado| `#FCE7BC` / `#854D0E` (mostarda)  |
| `R` Retardatário | `#C4D4D2` / `#1F3A37` (petrol) |

Regra: sempre comentar no código que aquele hex é deliberado, com
referência à decisão (parágrafo desta seção, idealmente).

---

## 7. Antecipações (norte, ainda não cristalizado)

Próximas ondas de redesign herdam destas decisões para não regredir.

### 7.1 Listas (Alunos, Turmas, Disciplinas, Professores, Ocorrências, etc)

**Header da página** segue §5.4 (eyebrow + título Fraunces + filete +
contexto). À direita ou na linha de baixo: botão primário
`"Novo X"` em `bg-olive text-creme`.

**Linha de filtros**: label mono à esquerda + control shadcn em
`bg-paper`. `gap-3`. Em mobile, empilhar.

**Tabela**:
- Wrapper em `bg-paper rounded-lg border border-border`.
- Header da tabela em `text-sepia` peso normal, `text-[11px] uppercase
  tracking-[0.15em]` — eyebrow virou pattern aqui também.
- Linha clicável (leva ao detalhe) + dropdown `⋯` no fim com
  `e.stopPropagation()` na célula.
- Colunas secundárias usam `hidden sm:table-cell` / `md:table-cell` /
  `lg:table-cell` — **nunca** scroll horizontal grosso.
- Linhas de registro inativo: opacidade reduzida + badge `[ inativo ]`
  em `text-[10px] text-sepia uppercase`.

**Toggle "Mostrar inativos"**: `Switch` shadcn na linha de filtros
(padrão já aplicado em `AlunosPage`).

### 7.2 Empty state

```
[bg-paper rounded-lg border border-border p-6]
[Título Fraunces text-lg text-tinta]
[Frase em text-sm text-sepia explicando como sair daqui]
```

Já aplicado no Dashboard quando não há turmas. Replicar em
listas vazias e em fluxos onde o usuário ainda não cadastrou nada.

### 7.3 Forms e Dialogs

- Dialog em `bg-paper` + `border-border` (default shadcn, herda
  automaticamente).
- Título do dialog em Fraunces, peso 500, tracking-tight.
- Labels em **eyebrow mono** (consistente com Login).
- Inputs idênticos ao Login: `bg-paper border border-border`, foco
  `border-ferrugem` + `ring-2 ring-ferrugem/20`.
- Ações no rodapé: botão secundário `variant="ghost"` à esquerda
  ("Cancelar"), primário olive à direita ("Salvar").
- Validação inline em vermelho destructive — mesma família do Login.
- Form em coluna única até onde der; só usar grid quando 2 campos
  curtos couberem visualmente lado a lado (ex: matrícula + data).

### 7.4 Detalhes (Ocorrência, Aluno, Turma, etc)

- Header com muitas ações: **stack vertical até `lg` (1024px), row a
  partir daí**. Padrão já aplicado em `OcorrenciaDetalhePage` —
  evita título competir com 3 botões + dropdown em tablet portrait.
- Ações secundárias em `variant="outline"`; destrutiva em
  `variant="destructive"` (terracota — `--destructive: #b85c38`).
- Cards de seção dentro do detalhe: `bg-paper rounded-lg border p-6`,
  título em Fraunces text-lg.

### 7.5 Confirmação destrutiva

- Sempre dialog (`AlertDialog` shadcn).
- Título Fraunces. Frase explicando consequência em sépia.
- CTA `variant="destructive"` à direita; "Cancelar" à esquerda.
- Texto **fiel à ação real**: soft delete diz "inativar", não "excluir
  permanentemente". Hard delete diz "excluir permanentemente" (e
  destaca o "permanentemente").

### 7.6 Toasts

- `sonner` com tema herdando paleta.
- Sucesso em olive; erro em destructive; sem emojis e sem ponto final
  no título.

---

## 8. Anti-patterns

Coisas a evitar e/ou a migrar quando cruzar pelo arquivo.

### 8.1 Tons Tailwind crus em badges

`text-amber-700 bg-amber-50`, `text-red-700`, `text-green-700`,
`text-blue-700` — não combinam com a paleta linho/olive.

**Estado atual da dívida:**
- ❌ `frontend/src/features/ocorrencias/constants.ts` — ainda usa
  `amber/blue/green/red`. Migrar pra paleta da marca (§6.1).
- ❌ `frontend/src/features/tarefas/constants.ts` — mesmo problema.
  Mapear status `pendente/atrasada/entregue_no_prazo/entregue_com_atraso`
  pra mostarda/terracota/olive/petrol seguindo §6.2.
- ✅ `frontend/src/features/presenca/constants.ts` — já migrado, é a
  referência.

### 8.2 Classes `dark:` mortas

Light é permanente. Toda classe `dark:bg-X dark:text-Y` é código morto e
confunde (dá impressão que dark existe). Remover ao tocar no arquivo.

Aparece principalmente nos dois `constants.ts` da dívida acima.

### 8.3 Override de paleta inline

`style={{ background: "var(--ferrugem)" }}` aparece em alguns lugares
(Sidebar) porque era pré-tokens. **Quando tocar no arquivo, trocar por
`bg-ferrugem`** — utility class do `@theme inline`. Vale também pra
borda/text/ring.

Exceção legítima: pastels P/A/J/R em `presenca/constants.ts`. Inline
porque não existe token correspondente e a especificidade é semântica.
Sempre com comentário justificando.

### 8.4 Reescrever componente shadcn por causa de cor

Se um botão precisa de cor diferente, conferir primeiro qual variante
shadcn cobre (`default`, `outline`, `ghost`, `destructive`, `link`). Se
nenhuma cobre, **ajustar o mapeamento de tokens** em `index.css`. Só
em último caso criar variante nova — e a variante nova vira pattern,
documentar aqui.

### 8.5 Sombras pesadas

Sem `shadow-lg`/`shadow-xl` em cards. Elevação no Diário Diniz vem do
contraste de tom (`paper` sobre `linho`) e da borda fina (`border`).

### 8.6 Mais de um eyebrow seguidos

Eyebrow microtípico é assinatura — perde força se aparecer dois ou três
seguidos. Máximo um por bloco visual.

### 8.7 Ícones decorativos

Lucide só com função. Sem ícone "📅" ao lado do label de data, sem
"👤" ao lado do nome. Tipografia já carrega hierarquia.

---

## 9. Como atualizar este doc

- Toda mudança visual estrutural (token novo, componente cristalizado,
  pattern novo de página) entra aqui **no mesmo PR**.
- Anti-pattern descoberto vira item da §8 com o arquivo/linha onde
  apareceu — vira dívida visível.
- Quando pagar uma dívida da §8, mover de ❌ pra ✅ e referenciar o
  PR que fez a migração.

Diniz é a fonte da verdade visual. Em divergência entre o que está aqui
e o que ele decide numa sessão, **atualiza o doc primeiro, aplica
depois**.
