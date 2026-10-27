import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { screen } from "@testing-library/react";

import { DashboardPage } from "@/pages/DashboardPage";
import { renderizar } from "@/test/render";
import { servidor } from "@/test/servidor";

const API = "http://api.test/api/v1";

// Os endpoints que o Dashboard dispara pra visitante sem perfil de
// direção (o card de aulas aguardando visto tem `enabled` e não busca).
//
// `/relatorios/dashboard/` entrou com as métricas agregadas (presença
// média e reincidência): a tela passou a chamá-lo e o teste não o
// declarava, então o `setup.ts` derrubava os dois casos por requisição
// sem handler — que é exatamente o que ele existe pra denunciar.
const ENDPOINTS = [
  "/turmas/",
  "/ocorrencias/",
  "/alunos/",
  "/registros-presenca/",
  "/relatorios/dashboard/",
];

function responderComDados() {
  servidor.use(
    http.get(`${API}/turmas/`, () =>
      HttpResponse.json([
        { id: 1, nome: "6º A", ano_letivo: 2026, ativa: true },
      ]),
    ),
    http.get(`${API}/ocorrencias/`, () =>
      HttpResponse.json([
        {
          id: 1,
          aluno: 7,
          turma: 1,
          status: "aberta",
          status_display: "Aberta",
          data_ocorrencia: "2026-03-10",
        },
        {
          id: 2,
          aluno: 8,
          turma: 1,
          status: "em_andamento",
          status_display: "Em andamento",
          data_ocorrencia: "2026-03-09",
        },
      ]),
    ),
    http.get(`${API}/alunos/`, () =>
      HttpResponse.json([
        { id: 7, nome_completo: "Ana Lima", turma: 1, ativo: true },
        { id: 8, nome_completo: "Bruno Sá", turma: 1, ativo: true },
        { id: 9, nome_completo: "Caio Melo", turma: 1, ativo: true },
      ]),
    ),
    http.get(`${API}/registros-presenca/`, () =>
      HttpResponse.json([{ id: 1, turma: 1, data: "2026-03-10" }]),
    ),
    // Valores escolhidos pra não colidirem com os que as asserções
    // procuram: `findByText` estoura quando o texto casa em mais de um
    // nó, então um "2" ou "3" vindo das métricas faria o controle
    // positivo falhar por ambiguidade, não por regressão.
    http.get(`${API}/relatorios/dashboard/`, () =>
      HttpResponse.json({
        janela: { dias: 30, data_inicio: "2026-02-08", data_fim: "2026-03-10" },
        turma_id: null,
        presenca: {
          percentual_medio: "87.50",
          total_itens: 48,
          presencas_efetivas: 42,
          total_chamadas: 6,
          abaixo_do_limite: false,
          limite_frequencia: "75.00",
        },
        reincidencia: {
          limiar: 2,
          alunos_reincidentes: 5,
          alunos_com_ocorrencia: 9,
        },
      }),
    ),
  );
}

function responderComFalha() {
  servidor.use(
    ...ENDPOINTS.map((caminho) =>
      http.get(`${API}${caminho}`, () =>
        HttpResponse.json({ detail: "boom" }, { status: 500 }),
      ),
    ),
  );
}

describe("DashboardPage", () => {
  // Controle positivo. Sem ele o teste de falha abaixo passaria mesmo se o
  // harness nunca conseguisse carregar nada — e seria um teste que não
  // prova nada.
  it("mostra os números quando a API responde", async () => {
    responderComDados();
    renderizar(<DashboardPage />);

    expect(await screen.findByText("2")).toBeInTheDocument();
    expect(screen.getByText(/1 abertas/)).toBeInTheDocument();
    expect(await screen.findByText("3")).toBeInTheDocument();
  });

  it("não apresenta zero como resposta do servidor quando a API falha", async () => {
    responderComFalha();
    renderizar(<DashboardPage />);

    // O bug: `data ?? []` e `data?.length ?? 0` faziam o card dizer
    // "0 ocorrências em aberto" com a API fora do ar, e o `carregando`
    // virava false no erro, então o skeleton saía e o zero ficava.
    const avisos = await screen.findAllByText("Não foi possível carregar.");
    expect(avisos.length).toBeGreaterThanOrEqual(2);
    expect(screen.queryByText("0")).not.toBeInTheDocument();
    expect(screen.getAllByText("—").length).toBeGreaterThanOrEqual(2);

    // E os dois cards de lista param de mentir "nada registrado".
    expect(
      await screen.findByText("Não foi possível carregar as ocorrências."),
    ).toBeInTheDocument();
    expect(
      await screen.findByText("Não foi possível carregar as chamadas."),
    ).toBeInTheDocument();
    expect(screen.queryByText("Nenhuma turma ativa.")).not.toBeInTheDocument();
  });
});
