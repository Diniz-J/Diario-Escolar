import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { screen } from "@testing-library/react";

import { autenticarComo } from "@/test/autenticar";
import { renderizar } from "@/test/render";
import { servidor } from "@/test/servidor";

import { OcorrenciaFormDialog } from "./OcorrenciaFormDialog";

const API = "http://api.test/api/v1";
const AVISO = /Não foi possível carregar as opções/;

const erro500 = () => HttpResponse.json({ detail: "erro" }, { status: 500 });

function responder({
  professoresFalham = false,
  alunosFalham = false,
}: {
  professoresFalham?: boolean;
  alunosFalham?: boolean;
} = {}) {
  servidor.use(
    http.get(`${API}/turmas/`, () =>
      HttpResponse.json([
        { id: 2, nome: "9º A", turno: "matutino", ano_letivo: 2026 },
      ]),
    ),
    http.get(`${API}/alunos/`, () =>
      alunosFalham
        ? erro500()
        : HttpResponse.json([
            { id: 7, nome_completo: "Ana Lima", turma: 2, ativo: true },
          ]),
    ),
    http.get(`${API}/professores/`, () =>
      professoresFalham ? erro500() : HttpResponse.json([]),
    ),
  );
}

function abrir() {
  renderizar(<OcorrenciaFormDialog open onOpenChange={() => {}} />);
}

describe("OcorrenciaFormDialog — falha de leitura por campo", () => {
  it("avisa mas deixa salvar quando só a lista de professores falha", async () => {
    // O professor é opcional na ocorrência (o modelo aceita nulo), então
    // travar o envio por causa dessa lista tiraria do inspetor a
    // possibilidade de registrar o que aconteceu. O aviso explica o
    // select vazio; o botão continua disponível.
    autenticarComo("inspetor", 1);
    responder({ professoresFalham: true });
    abrir();

    expect(await screen.findByText(AVISO)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Salvar" })).toBeEnabled();
  });

  it("trava o envio quando a lista de alunos falha", async () => {
    // Aqui é o oposto: o aluno é exigido na validação, então sem a lista
    // não há ocorrência a registrar e o submit só levaria a um
    // "Selecione um aluno" enganoso.
    autenticarComo("inspetor", 1);
    responder({ alunosFalham: true });
    abrir();

    expect(await screen.findByText(AVISO)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Salvar" })).toBeDisabled();
  });

  it("não avisa nada quando as três listas respondem", async () => {
    // Controle positivo das duas de cima.
    autenticarComo("inspetor", 1);
    responder();
    abrir();

    expect(
      await screen.findByRole("button", { name: "Salvar" }),
    ).toBeEnabled();
    await expect(screen.findByText(AVISO)).rejects.toThrow();
  });
});
