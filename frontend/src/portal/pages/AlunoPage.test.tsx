import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Route, Routes } from "react-router-dom";

import { AlunoPage } from "@/portal/pages/AlunoPage";
import { renderizar } from "@/test/render";
import { servidor } from "@/test/servidor";

const PORTAL = "http://api.test/api/v1/portal";

function fatura(extra: Record<string, unknown> = {}) {
  return {
    id: 1,
    competencia: "2026-03-01",
    valor: "500.00",
    vencimento: "2026-03-10",
    status: "vencido",
    valor_atualizado: "515.00",
    link_pagamento: "https://pague.example.com/abc",
    ...extra,
  };
}

function responder(faturas: unknown[]) {
  servidor.use(
    http.get(`${PORTAL}/alunos/1/`, () =>
      HttpResponse.json({
        id: 1,
        nome_completo: "Ana Lima",
        matricula: "M1",
        turma: "6º A",
        ano_letivo: 2026,
        ativo: true,
      }),
    ),
    http.get(`${PORTAL}/alunos/1/faturas/`, () =>
      HttpResponse.json({ count: faturas.length, results: faturas }),
    ),
    // A aba default é o boletim, então estas saem no render mesmo que a
    // asserção seja sobre mensalidades. Sem handler o MSW só logaria, e o
    // afterEach do setup reprova listando o endpoint esquecido.
    http.get(`${PORTAL}/periodos/`, () => HttpResponse.json([])),
    http.get(`${PORTAL}/alunos/1/boletim/`, () =>
      HttpResponse.json({
        aluno: { id: 1, nome_completo: "Ana Lima", matricula: "M1", ativo: true },
        turma: { id: 1, nome: "6º A", ano_letivo: 2026 },
        escola: { id: 1, nome: "Escola Teste" },
        periodo: {
          id: null,
          nome: null,
          ano_letivo: null,
          data_inicio: null,
          data_fim: null,
        },
        frequencia: {
          total: 0,
          presentes: 0,
          ausentes: 0,
          justificados: 0,
          retardatarios: 0,
          presencas_efetivas: 0,
          percentual_presenca: "0.00",
        },
        notas_por_disciplina: [],
        ocorrencias: {
          total: 0,
          abertas: 0,
          em_andamento: 0,
          resolvidas: 0,
          arquivadas: 0,
        },
      }),
    ),
  );
}

async function abrirMensalidades(faturas: unknown[]) {
  responder(faturas);
  renderizar(
    <Routes>
      <Route path="/portal/alunos/:id" element={<AlunoPage />} />
    </Routes>,
    "/portal/alunos/1",
  );
  await screen.findByText("Ana Lima");
  await userEvent.click(screen.getByRole("tab", { name: "Mensalidades" }));
}

describe("AlunoPage — mensalidades", () => {
  it("mostra a mensalidade com o link de pagamento", async () => {
    await abrirMensalidades([fatura()]);

    expect(await screen.findByText("03/2026")).toBeInTheDocument();
    const pagar = screen.getByRole("link", { name: "Pagar" });
    expect(pagar).toHaveAttribute("href", "https://pague.example.com/abc");
    // Alvo externo sem acesso a `window.opener`.
    expect(pagar).toHaveAttribute("rel", "noopener noreferrer");
  });

  it("mostra o valor com encargos quando ele difere do nominal", async () => {
    await abrirMensalidades([fatura()]);

    expect(await screen.findByText(/Com encargos até hoje/)).toBeInTheDocument();
    expect(screen.getByText("R$ 515,00")).toBeInTheDocument();
  });

  it("omite a linha de encargos quando não há nada somado", async () => {
    await abrirMensalidades([
      fatura({ status: "pendente", valor_atualizado: "500.00" }),
    ]);

    // Controle positivo: sem ele, a ausência abaixo passaria mesmo se a
    // lista não tivesse carregado.
    expect(await screen.findByText("03/2026")).toBeInTheDocument();
    expect(screen.queryByText(/Com encargos até hoje/)).not.toBeInTheDocument();
  });

  it("não oferece botão enquanto a escola não emitiu a cobrança", async () => {
    await abrirMensalidades([fatura({ link_pagamento: "" })]);

    expect(await screen.findByText("03/2026")).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Pagar" })).not.toBeInTheDocument();
  });

  it("recusa link que não seja http(s)", async () => {
    await abrirMensalidades([
      fatura({ link_pagamento: "javascript:alert(1)" }),
    ]);

    expect(await screen.findByText("03/2026")).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Pagar" })).not.toBeInTheDocument();
  });

  it("avisa quando não há mensalidade registrada", async () => {
    await abrirMensalidades([]);

    expect(
      await screen.findByText("Nenhuma mensalidade registrada."),
    ).toBeInTheDocument();
  });
});
