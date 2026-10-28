import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { screen } from "@testing-library/react";

import { autenticarComo } from "@/test/autenticar";
import { renderizar } from "@/test/render";
import { servidor } from "@/test/servidor";
import type { RegistroAula } from "@/types/api";

import { RegistroAulaFormDialog } from "./RegistroAulaFormDialog";

const API = "http://api.test/api/v1";

const REGISTRO: RegistroAula = {
  id: 9,
  escola: 1,
  turma: 2,
  disciplina: 3,
  professor: 4,
  data: "2026-10-20",
  conteudo: "Equação do segundo grau: fórmula de Bhaskara.",
  status: "lancado",
  status_display: "Lançado",
  conferido_por: null,
  conferido_por_nome: null,
  conferido_em: null,
  criado_em: "2026-10-20T12:00:00Z",
  atualizado_em: "2026-10-20T12:00:00Z",
};

function abrirEdicao() {
  renderizar(
    <RegistroAulaFormDialog
      open
      onOpenChange={() => {}}
      turma={2}
      disciplina={3}
      professor={4}
      data="2026-10-20"
      registroId={9}
      contextoLabel="20/10 · 9º A · Matemática"
    />,
  );
}

describe("RegistroAulaFormDialog — leitura do registro que falha", () => {
  it("não deixa salvar sobre conteúdo que não carregou", async () => {
    // O bug que isto trava: a query de detalhe falha, `isLoading` vira
    // false e `data` fica undefined, então o textarea abria VAZIO e
    // habilitado sobre uma aula que já tem conteúdo no banco — salvar dali
    // apagava o que o professor havia escrito.
    autenticarComo("professor");
    servidor.use(
      http.get(`${API}/registros-aula/9/`, () =>
        HttpResponse.json({ detail: "erro" }, { status: 500 }),
      ),
    );
    abrirEdicao();

    expect(
      await screen.findByText(/sobrescreveria o que já estava registrado/),
    ).toBeInTheDocument();
    expect(screen.getByRole("textbox")).toBeDisabled();
    expect(
      screen.queryByRole("button", { name: "Lançar" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Salvar rascunho" }),
    ).not.toBeInTheDocument();
  });

  it("carrega o conteúdo e libera a escrita quando a leitura responde", async () => {
    // Controle positivo do teste acima: sem ele, um dialog que nunca
    // renderizasse textarea nem botão passaria nos dois.
    autenticarComo("professor");
    servidor.use(
      http.get(`${API}/registros-aula/9/`, () => HttpResponse.json(REGISTRO)),
    );
    abrirEdicao();

    expect(
      await screen.findByDisplayValue(/fórmula de Bhaskara/),
    ).toBeEnabled();
    expect(screen.getByRole("button", { name: "Lançar" })).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Salvar rascunho" }),
    ).toBeInTheDocument();
    expect(
      screen.queryByText(/sobrescreveria o que já estava registrado/),
    ).not.toBeInTheDocument();
  });

  it("mantém a aula conferida somente leitura", async () => {
    // A outra metade do estrago: `somenteLeitura` sai de
    // `registro?.status`, então a falha de leitura também derrubava o
    // travamento da aula já conferida pela direção.
    autenticarComo("professor");
    servidor.use(
      http.get(`${API}/registros-aula/9/`, () =>
        HttpResponse.json({
          ...REGISTRO,
          status: "conferido",
          status_display: "Conferido",
        }),
      ),
    );
    abrirEdicao();

    expect(await screen.findByText("Aula conferida")).toBeInTheDocument();
    expect(screen.getByRole("textbox")).toBeDisabled();
    expect(
      screen.queryByRole("button", { name: "Lançar" }),
    ).not.toBeInTheDocument();
  });
});
