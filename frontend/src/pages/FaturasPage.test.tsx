import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { screen } from "@testing-library/react";

import { FaturasPage } from "@/pages/FaturasPage";
import { autenticarComo } from "@/test/autenticar";
import { renderizar } from "@/test/render";
import { servidor } from "@/test/servidor";

const API = "http://api.test/api/v1";

function responderFaturas(resposta: () => Response) {
  servidor.use(
    http.get(`${API}/faturas/`, resposta),
    http.get(`${API}/turmas/`, () =>
      HttpResponse.json([{ id: 1, nome: "6º A", ano_letivo: 2026, ativa: true }]),
    ),
    // A tela carrega os planos ativos pro dialog de nova fatura. Não tem
    // nada a ver com a asserção, mas sem o handler a requisição falharia
    // em silêncio — a checagem de requisição não-coberta pegou isso.
    http.get(`${API}/planos-cobranca/`, () => HttpResponse.json([])),
  );
}

describe("FaturasPage", () => {
  it("lista as faturas quando a API responde", async () => {
    autenticarComo("diretor");
    responderFaturas(() =>
      HttpResponse.json({
        count: 1,
        results: [
          {
            id: 1,
            aluno: 7,
            aluno_nome: "Ana Lima",
            competencia: "2026-03-01",
            vencimento: "2026-03-10",
            valor: "450.00",
            valor_pago: "0.00",
            status: "pendente",
            status_display: "Pendente",
          },
        ],
      }),
    );
    renderizar(<FaturasPage />, "/financeiro");

    expect(await screen.findByText("Ana Lima")).toBeInTheDocument();
  });

  it("não deixa a falha passar por 'nenhuma fatura'", async () => {
    autenticarComo("diretor");
    responderFaturas(() => HttpResponse.json({ detail: "boom" }, { status: 500 }));
    renderizar(<FaturasPage />, "/financeiro");

    // O estado vazio desta tela não é neutro: lido ao pé da letra, diz que
    // o aluno está quite.
    expect(
      await screen.findByText(/Não foi possível carregar as faturas/),
    ).toBeInTheDocument();
    expect(
      screen.queryByText("Nenhuma fatura neste recorte."),
    ).not.toBeInTheDocument();
  });
});
