import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

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
    // Mesma razão: os dialogs do financeiro passaram a chamar
    // `useEscolas()` pro select que só o admin global enxerga. O hook não
    // é condicional, então a requisição sai para qualquer perfil — a
    // diretora deste teste inclusive.
    http.get(`${API}/escolas/`, () =>
      HttpResponse.json([{ id: 1, nome: "Escola Teste" }]),
    ),
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

describe("FaturasPage — emitir cobrança", () => {
  const FATURA_PENDENTE = {
    id: 1,
    aluno: 7,
    aluno_nome: "Ana Lima",
    competencia: "2026-03-01",
    vencimento: "2026-03-10",
    valor: "450.00",
    valor_pago: "0.00",
    saldo: "450.00",
    status: "pendente",
    status_display: "Pendente",
    id_externo: "",
    link_pagamento: "",
  };

  async function abrirMenuDaLinha() {
    const usuario = userEvent.setup();
    await usuario.click(await screen.findByLabelText("Ações da fatura"));
    return usuario;
  }

  it("oferece a emissão numa fatura pendente", async () => {
    autenticarComo("diretor");
    responderFaturas(() =>
      HttpResponse.json({ count: 1, results: [FATURA_PENDENTE] }),
    );
    renderizar(<FaturasPage />, "/financeiro");

    await abrirMenuDaLinha();

    expect(
      await screen.findByRole("menuitem", { name: "Emitir cobrança" }),
    ).toBeInTheDocument();
  });

  it("não oferece numa fatura que já tem cobrança no gateway", async () => {
    // Controle negativo do positivo acima: sem ele, o teste de cima
    // passaria mesmo se o item fosse renderizado sempre.
    autenticarComo("diretor");
    responderFaturas(() =>
      HttpResponse.json({
        count: 1,
        results: [{ ...FATURA_PENDENTE, id_externo: "pay_080225913252" }],
      }),
    );
    renderizar(<FaturasPage />, "/financeiro");

    await abrirMenuDaLinha();

    // O menu abriu (há outro item), mas a emissão não está nele.
    expect(
      await screen.findByRole("menuitem", { name: "Registrar pagamento" }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("menuitem", { name: "Emitir cobrança" }),
    ).not.toBeInTheDocument();
  });

  it("mostra a mensagem do backend quando a emissão é recusada", async () => {
    // É o ponto do desenho: o 400 do backend diz o que falta preencher
    // ("sem CPF", "sem pagador", "não está configurada"), e essa frase
    // tem que chegar na tela em vez de virar "erro ao emitir".
    autenticarComo("diretor");
    responderFaturas(() =>
      HttpResponse.json({ count: 1, results: [FATURA_PENDENTE] }),
    );
    servidor.use(
      http.post(`${API}/faturas/1/emitir-cobranca/`, () =>
        HttpResponse.json(
          { detail: "O responsável Maria Lima está sem CPF." },
          { status: 400 },
        ),
      ),
    );
    renderizar(<FaturasPage />, "/financeiro");

    const usuario = await abrirMenuDaLinha();
    await usuario.click(
      await screen.findByRole("menuitem", { name: "Emitir cobrança" }),
    );
    await usuario.click(
      await screen.findByRole("button", { name: "Emitir cobrança" }),
    );

    expect(
      await screen.findByText("O responsável Maria Lima está sem CPF."),
    ).toBeInTheDocument();
  });
});
