import "@testing-library/jest-dom/vitest";

import { cleanup } from "@testing-library/react";
import { afterAll, afterEach, beforeAll } from "vitest";

import axios from "axios";

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
// O refresh de token sai pelo axios **global** (`axios.post` em
// `executarRefresh`, de propósito: a instância tem interceptor e
// recursionaria), então sem forçar o default o MSW não intercepta o
// refresh e o caminho fica impossível de testar.
axios.defaults.adapter = "fetch";

// O `Select` do shadcn é Radix, e o Radix usa APIs de ponteiro e de scroll
// que o jsdom não implementa: sem elas o menu simplesmente não abre, e o
// teste falha com "Unable to find role=option" — como se a opção não
// existisse, quando na verdade a lista nunca foi montada. Era o que
// deixava qualquer tela com `Select` intestável (o motivo de a tela da
// grade ter ido pra `?turma=` em vez de depender do seletor no teste).
//
// Só o que o Radix chama, e nada além: `hasPointerCapture` devolve false
// porque nenhum elemento tem captura num ambiente sem ponteiro de verdade,
// e as outras três são no-op. Não altera o app — são métodos do DOM que o
// browser já fornece.
for (const [metodo, implementacao] of [
  ["hasPointerCapture", () => false],
  ["setPointerCapture", () => {}],
  ["releasePointerCapture", () => {}],
  ["scrollIntoView", () => {}],
] as const) {
  if (!(metodo in Element.prototype)) {
    Object.defineProperty(Element.prototype, metodo, {
      value: implementacao,
      writable: true,
      configurable: true,
    });
  }
}

// O Radix mede o viewport do menu com ResizeObserver, que o jsdom também
// não tem.
if (!("ResizeObserver" in globalThis)) {
  globalThis.ResizeObserver = class {
    observe() {}
    unobserve() {}
    disconnect() {}
  };
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
