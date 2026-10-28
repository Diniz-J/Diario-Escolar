import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { screen } from "@testing-library/react";

import { autenticarComo } from "@/test/autenticar";
import { renderizar } from "@/test/render";
import { servidor } from "@/test/servidor";
import type { PlanoCobranca } from "@/types/api";

import { PlanoCobrancaFormDialog } from "./PlanoCobrancaFormDialog";

const API = "http://api.test/api/v1";

const PLANO: PlanoCobranca = {
  id: 1,
  escola: 1,
  aluno: 7,
  aluno_nome: "Ana Lima",
  pagador: null,
  pagador_nome: "",
  valor_mensalidade: "1000.00",
  dia_vencimento: 10,
  desconto_tipo: "nenhum",
  desconto_valor: "0.00",
  valor_efetivo: "1000.00",
  multa_percentual: "2.00",
  juros_mes_percentual: "1.00",
  vigencia_inicio: "2026-01-01",
  vigencia_fim: null,
  ativo: true,
  criado_em: "2026-01-01T00:00:00Z",
  atualizado_em: "2026-01-01T00:00:00Z",
};

// Os endpoints que o dialog dispara além dos vínculos. `escolas` sai pelo
// `useEscolas` que o select de admin global usa (o hook não é
// condicional), e `alunos` pelo select de aluno.
function responderBase() {
  servidor.use(
    http.get(`${API}/escolas/`, () =>
      HttpResponse.json([{ id: 1, nome: "Escola Teste" }]),
    ),
    http.get(`${API}/alunos/`, () =>
      HttpResponse.json([
        { id: 7, nome_completo: "Ana Lima", matricula: "001", ativo: true },
      ]),
    ),
  );
}

function responderVinculos(vinculos: unknown[]) {
  servidor.use(
    http.get(`${API}/vinculos-responsavel/`, () =>
      HttpResponse.json(vinculos),
    ),
  );
}

describe("PlanoCobrancaFormDialog — pagador", () => {
  it("mostra o pagador do contrato, resolvido pelos vínculos", async () => {
    // O nome não vem no plano — o backend manda `pagador` como id. Ele só
    // aparece se a tela cruzar esse id com a resposta dos vínculos, que é
    // exatamente o que este teste prova.
    autenticarComo("diretor");
    responderBase();
    responderVinculos([
      {
        id: 1,
        responsavel: 3,
        responsavel_nome: "Maria Lima",
        responsavel_email: "maria@exemplo.com",
        aluno: 7,
      },
    ]);
    renderizar(
      <PlanoCobrancaFormDialog
        open
        onOpenChange={() => {}}
        plano={{ ...PLANO, pagador: 3 }}
      />,
    );

    expect(await screen.findByText("Pagador")).toBeInTheDocument();
    expect(
      await screen.findByText(/Maria Lima \(maria@exemplo\.com\)/),
    ).toBeInTheDocument();
  });

  it("explica o que fazer quando o aluno não tem vínculo", async () => {
    // Controle do caso acima, e o que evita um campo vazio sem motivo:
    // sem vínculo não há quem cobrar, e a saída é a tela Responsáveis.
    autenticarComo("diretor");
    responderBase();
    responderVinculos([]);
    renderizar(
      <PlanoCobrancaFormDialog open onOpenChange={() => {}} plano={PLANO} />,
    );

    expect(
      await screen.findByText(/não tem responsável vinculado/),
    ).toBeInTheDocument();
  });

  it("pede os vínculos do aluno, não a lista de responsáveis da escola", async () => {
    // A regra central: o backend exige que o pagador seja responsável
    // **deste** aluno. Se um dia a tela passar a chamar /responsaveis/,
    // ela ofereceria terceiros e o backend recusaria na hora de salvar.
    autenticarComo("diretor");
    responderBase();
    const vistos: string[] = [];
    servidor.use(
      http.get(`${API}/vinculos-responsavel/`, ({ request }) => {
        vistos.push(new URL(request.url).searchParams.get("aluno") ?? "");
        return HttpResponse.json([]);
      }),
    );
    renderizar(
      <PlanoCobrancaFormDialog open onOpenChange={() => {}} plano={PLANO} />,
    );

    await screen.findByText(/não tem responsável vinculado/);
    expect(vistos).toContain("7");
  });
});
