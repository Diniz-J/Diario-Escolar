// `process.env.TZ` precisa dos tipos do Node, e o `tsconfig.app.json`
// declara só `vite/client` — de propósito, pra não vazar global de Node
// pro código de browser. A referência abaixo os traz só neste arquivo.
/// <reference types="node" />

import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";

import { hojeISO } from "./datas";

// Estes testes só fazem sentido em fuso negativo — é lá que a conversão
// pra UTC troca o dia. Fixa São Paulo (UTC-3, sem horário de verão desde
// 2019) pra não depender do fuso da máquina de quem roda.
beforeAll(() => {
  process.env.TZ = "America/Sao_Paulo";
});

afterEach(() => {
  vi.useRealTimers();
});

describe("hojeISO", () => {
  it("roda num fuso realmente em UTC-3", () => {
    // Guarda: sem esta checagem, um ambiente que ignorasse `TZ` faria os
    // casos abaixo passar (ou falhar) pelo motivo errado.
    expect(new Date(2026, 2, 10, 12).getTimezoneOffset()).toBe(180);
  });

  it("devolve o dia local às 21h30, quando em UTC já é o dia seguinte", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date(2026, 2, 10, 21, 30));

    // O caminho antigo enxerga amanhã — é exatamente o bug.
    expect(new Date().toISOString().slice(0, 10)).toBe("2026-03-11");
    expect(hojeISO()).toBe("2026-03-10");
  });

  it("devolve o mesmo dia de manhã, quando os dois caminhos concordam", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date(2026, 2, 10, 9, 0));

    expect(new Date().toISOString().slice(0, 10)).toBe("2026-03-10");
    expect(hojeISO()).toBe("2026-03-10");
  });

  it("zera à esquerda mês e dia de um dígito", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date(2026, 0, 5, 23, 59));

    expect(hojeISO()).toBe("2026-01-05");
  });
});
