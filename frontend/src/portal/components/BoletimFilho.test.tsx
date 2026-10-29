import { http, HttpResponse } from "msw";
import { describe, expect, it, vi } from "vitest";
import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { renderizar } from "@/test/render";
import { servidor } from "@/test/servidor";

import { BoletimFilho } from "./BoletimFilho";

const PORTAL = "http://api.test/api/v1/portal";

const BOLETIM = {
  frequencia: {
    percentual_presenca: "92.0",
    total: 50,
    ausentes: 4,
    justificados: 1,
  },
  notas_por_disciplina: [],
};

function responder() {
  servidor.use(
    http.get(`${PORTAL}/periodos/`, () =>
      HttpResponse.json([
        { id: 7, nome: "1º Bimestre", ano_letivo: 2026 },
        { id: 8, nome: "2º Bimestre", ano_letivo: 2026 },
      ]),
    ),
    http.get(`${PORTAL}/alunos/1/boletim/`, () => HttpResponse.json(BOLETIM)),
  );
}

// O seletor de período é `<select>` nativo, e não o `Select` do shadcn:
// era o único uso de Radix pesado no portal e sozinho obrigava o pai a
// baixar o chunk inteiro (medido: 158,9 -> 135,6 kB gzip). Estes testes
// prendem o comportamento que a troca mexeu, pra ninguém "repadronizar"
// de volta sem perceber o custo.
describe("BoletimFilho — seletor de período", () => {
  it("lista os períodos vindos da API junto da opção anual", async () => {
    responder();
    renderizar(
      <BoletimFilho alunoId={1} periodoId={null} onPeriodoChange={() => {}} />,
    );

    const campo = await screen.findByLabelText("Período");
    // `getByRole("option")` enxerga `<option>` nativo; o Radix renderiza
    // os itens só depois de abrir o popover, então este teste também é o
    // que falha se alguém voltar o componente.
    const opcoes = within(campo).getAllByRole("option");
    expect(opcoes.map((o) => o.textContent)).toEqual([
      "Ano inteiro",
      "1º Bimestre (2026)",
      "2º Bimestre (2026)",
    ]);
  });

  it("avisa o pai com o id ao escolher um período", async () => {
    responder();
    const aoTrocar = vi.fn();
    renderizar(
      <BoletimFilho alunoId={1} periodoId={null} onPeriodoChange={aoTrocar} />,
    );

    const campo = await screen.findByLabelText("Período");
    await userEvent.selectOptions(campo, "8");

    expect(aoTrocar).toHaveBeenCalledWith(8);
  });

  it("volta a null ao escolher o ano inteiro", async () => {
    // `null` é o que o hook usa pra omitir `?periodo=` e pedir o ano
    // todo; mandar a string sentinela adiante quebraria a query.
    responder();
    const aoTrocar = vi.fn();
    renderizar(
      <BoletimFilho alunoId={1} periodoId={8} onPeriodoChange={aoTrocar} />,
    );

    const campo = await screen.findByLabelText("Período");
    await userEvent.selectOptions(campo, "__anual__");

    expect(aoTrocar).toHaveBeenCalledWith(null);
  });
});
