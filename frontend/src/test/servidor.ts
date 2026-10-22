import { setupServer } from "msw/node";

// Servidor de mock HTTP compartilhado pelos testes de componente.
//
// Nasce **sem handler nenhum** de propósito: cada teste declara os
// endpoints que ele precisa com `servidor.use(...)`. Handler default
// global economizaria linhas, mas esconderia a requisição que o teste não
// previu — e é justamente a requisição não prevista que costuma ser o bug.
// Sem handler, o teste falha: `onUnhandledFrame: "error"` no setup. (Em
// MSW 3 a opção se chama assim; era `onUnhandledRequest` até a v2, e
// mudou de nome porque agora cobre também conexão WebSocket.)
export const servidor = setupServer();
