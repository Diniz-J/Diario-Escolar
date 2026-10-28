import { describe, expect, it } from "vitest";

import type { Fatura } from "@/types/api";

import { podeEmitirCobranca } from "./constants";

// A regra decide o que a `FaturasPage` e a `FichaFinanceiraPage` mostram
// no menu ⋯ e no detalhe. Como ela mora num lugar só pra não divergir
// entre as duas, o teste é sobre ela, não sobre cada tela.
function fatura(parcial: Partial<Fatura>): Fatura {
  return {
    id: 1,
    status: "pendente",
    id_externo: "",
    ...parcial,
  } as Fatura;
}

describe("podeEmitirCobranca", () => {
  it("vale pra pendente e vencida sem cobrança no gateway", () => {
    expect(podeEmitirCobranca(fatura({ status: "pendente" }))).toBe(true);
    expect(podeEmitirCobranca(fatura({ status: "vencido" }))).toBe(true);
  });

  it("não vale pra paga nem cancelada", () => {
    // Emitir cobrança do que já foi recebido é cobrar duas vezes; do que
    // a escola baixou é ressuscitar. O backend recusa as duas — isto é
    // só pra não oferecer um botão que já se sabe que dá erro.
    expect(podeEmitirCobranca(fatura({ status: "pago" }))).toBe(false);
    expect(podeEmitirCobranca(fatura({ status: "cancelado" }))).toBe(false);
  });

  it("não vale pra fatura que já foi emitida", () => {
    // O que ela precisa é do link, não de uma segunda cobrança. O backend
    // é idempotente aqui, então o erro seria silencioso: a secretaria
    // clicaria e nada mudaria na tela.
    expect(
      podeEmitirCobranca(fatura({ status: "pendente", id_externo: "pay_1" })),
    ).toBe(false);
  });
});
