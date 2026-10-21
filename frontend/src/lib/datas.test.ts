// `process.env.TZ` precisa dos tipos do Node, e o `tsconfig.app.json`
// declara só `vite/client` — de propósito, pra não vazar global de Node
// pro código de browser. A referência abaixo os traz só neste arquivo.
/// <reference types="node" />

import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";

import {
  formatarDataHora,
  formatarDataPura,
  formatarDiaDaDataHora,
  hojeISO,
} from "./datas";

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

describe("formatarDataPura", () => {
  it("não desloca o dia em fuso negativo", () => {
    // `new Date("2026-03-10")` voltaria como 09/03 em UTC-3; o split não.
    expect(formatarDataPura("2026-03-10")).toBe("10/03/2026");
  });
});

describe("formatarDataHora", () => {
  it("converte o instante do DRF pro fuso do usuário", () => {
    expect(formatarDataHora("2026-03-10T21:30:00-03:00")).toBe(
      "10/03/2026, 21:30",
    );
  });

  it("devolve travessão pra nulo", () => {
    expect(formatarDataHora(null)).toBe("—");
  });
});

describe("formatarDiaDaDataHora", () => {
  it("exibe só o dia de um campo de data-hora", () => {
    expect(formatarDiaDaDataHora("2026-03-10T21:30:00-03:00")).toBe(
      "10/03/2026",
    );
  });

  it("reprova o erro que o portal cometia: data pura aplicada a data-hora", () => {
    // A `AlunoPage` do portal usava o formatador de data pura em
    // `publicado_em` (`DateTimeField`), concatenando `T00:00:00` numa
    // string que já tinha hora e offset — e o portal mostrava
    // "Invalid Date" em todo material.
    const instante = "2026-03-10T21:30:00-03:00";
    expect(new Date(`${instante}T00:00:00`).toString()).toBe("Invalid Date");
    expect(formatarDiaDaDataHora(instante)).toBe("10/03/2026");
  });
});
