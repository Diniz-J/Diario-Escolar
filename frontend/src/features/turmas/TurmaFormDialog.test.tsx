import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { screen } from "@testing-library/react";

import { autenticarComo } from "@/test/autenticar";
import { renderizar } from "@/test/render";
import { servidor } from "@/test/servidor";

import { TurmaFormDialog } from "./TurmaFormDialog";

const API = "http://api.test/api/v1";
const AVISO = /Não foi possível carregar as opções/;

function escolasFalham() {
  servidor.use(
    http.get(`${API}/escolas/`, () =>
      HttpResponse.json({ detail: "erro" }, { status: 500 }),
    ),
  );
}

function escolasRespondem() {
  servidor.use(
    http.get(`${API}/escolas/`, () =>
      HttpResponse.json([{ id: 1, nome: "Escola Teste" }]),
    ),
  );
}

function abrir() {
  renderizar(<TurmaFormDialog open onOpenChange={() => {}} />);
}

describe("TurmaFormDialog — lista de escolas que falha", () => {
  it("avisa e trava o envio do admin global", async () => {
    // Sem isto o select de escola abria vazio e o submit respondia
    // "Selecione uma escola", culpando o admin por uma falha de rede.
    autenticarComo("admin", null);
    escolasFalham();
    abrir();

    expect(await screen.findByText(AVISO)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Salvar" })).toBeDisabled();
  });

  it("não atrapalha o diretor, que não usa essa lista", async () => {
    // A não-regressão que importa: o hook de escolas roda pra todo
    // perfil, mas só o admin global vê o select e manda o campo — pros
    // outros o backend deduz a escola do JWT. Contar a falha sem olhar o
    // perfil deixaria o diretor sem conseguir criar turma por causa de
    // uma lista que ele nem consome.
    autenticarComo("diretor", 1);
    escolasFalham();
    abrir();

    // `findByText` sondando até o timeout é o que dá tempo de a query
    // falhar e o React reprocessar. Com `queryByText` logo após o render,
    // o teste afirmava antes da falha chegar e passava por corrida —
    // tirar o gate de `ehAdminGlobal` não o reprovava.
    await expect(screen.findByText(AVISO)).rejects.toThrow();
    expect(screen.getByRole("button", { name: "Salvar" })).toBeEnabled();
  });

  it("deixa o admin global salvar quando a lista responde", async () => {
    // Controle positivo: sem ele, um dialog que nunca renderizasse botão
    // passaria no primeiro teste.
    autenticarComo("admin", null);
    escolasRespondem();
    abrir();

    expect(
      await screen.findByRole("button", { name: "Salvar" }),
    ).toBeEnabled();
    expect(screen.queryByText(AVISO)).not.toBeInTheDocument();
  });
});
