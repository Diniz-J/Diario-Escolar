import "@testing-library/jest-dom/vitest";

import { cleanup } from "@testing-library/react";
import { afterAll, afterEach, beforeAll } from "vitest";

import { portalApi } from "@/features/portal/api";
import { api } from "@/lib/api";

import { servidor } from "./servidor";

// Em jsdom o axios escolhe o adapter XHR, e a interceptação de XHR do MSW
// não funciona nessa combinação: todo request volta como `Network Error`
// (ERR_NETWORK) em vez da resposta declarada no handler. Com `fetch` o
// mesmo request é interceptado normalmente.
//
// Isto é configuração só de teste e não muda o app: interceptor de request
// (Bearer) e de response (refresh no 401) são camada de axios, não de
// transporte, então seguem sendo exercitados. O que deixa de rodar é o
// XMLHttpRequest, que não é código nosso.
for (const instancia of [api, portalApi]) {
  instancia.defaults.adapter = "fetch";
}

// Requisição que nenhum handler cobre. O MSW loga e deixa o request
// falhar, mas **não** reprova o teste por conta própria — e falha de
// transporte é indistinguível de um 500 declarado, então um teste de
// estado de erro passaria sem handler nenhum, provando nada. Por isso a
// lista vira falha explícita no fim de cada teste.
const semHandler: string[] = [];

beforeAll(() => {
  servidor.listen({ onUnhandledFrame: "error" });
  servidor.events.on("request:unhandled", ({ request }) => {
    semHandler.push(`${request.method} ${request.url}`);
  });
});

afterEach(() => {
  servidor.resetHandlers();
  cleanup();
  // O storage é global do jsdom e vaza entre testes — um token deixado
  // por um teste de login mudaria o comportamento do próximo.
  localStorage.clear();
  sessionStorage.clear();

  // `splice` em vez de ler: limpa pro teste seguinte mesmo quando este
  // falha aqui.
  const naoCobertas = semHandler.splice(0);
  if (naoCobertas.length > 0) {
    throw new Error(
      "O teste disparou requisição que nenhum handler do MSW cobre:\n" +
        naoCobertas.map((r) => `  ${r}`).join("\n") +
        "\nDeclare o endpoint com servidor.use(...) — sem isso a query " +
        "falha por transporte, não pelo que o teste quer provar.",
    );
  }
});

afterAll(() => servidor.close());
