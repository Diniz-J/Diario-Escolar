import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { screen } from "@testing-library/react";

import { GradePage } from "@/pages/GradePage";
import { autenticarComo } from "@/test/autenticar";
import { renderizar } from "@/test/render";
import { servidor } from "@/test/servidor";

const API = "http://api.test/api/v1";

const TURMA = {
  id: 1,
  escola: 1,
  nome: "6º A",
  turno: "matutino",
  turno_display: "Matutino",
  ano_letivo: 2026,
  ativa: true,
};

const TEMPO = {
  id: 10,
  escola: 1,
  turno: "matutino",
  turno_display: "Matutino",
  ordem: 1,
  hora_inicio: "07:00:00",
  hora_fim: "07:50:00",
  ativo: true,
};

const SLOT = {
  id: 100,
  escola: 1,
  lecionamento: 5,
  turma: 1,
  turma_nome: "6º A",
  dia_semana: 0,
  dia_semana_display: "Segunda",
  tempo: 10,
  tempo_ordem: 1,
  tempo_hora_inicio: "07:00:00",
  tempo_hora_fim: "07:50:00",
  disciplina: 3,
  disciplina_nome: "Matemática",
  professor: 2,
  professor_nome: "Joana Prado",
  ativo: true,
};

interface Respostas {
  tempos?: () => Response;
  grade?: () => Response;
}

function responder({ tempos, grade }: Respostas = {}) {
  servidor.use(
    http.get(`${API}/turmas/`, () => HttpResponse.json([TURMA])),
    http.get(`${API}/tempos-aula/`, tempos ?? (() => HttpResponse.json([TEMPO]))),
    http.get(`${API}/grade-aulas/`, grade ?? (() => HttpResponse.json([SLOT]))),
  );
}

describe("GradePage", () => {
  it("monta a matriz com a aula no dia e no tempo certos", async () => {
    autenticarComo("diretor");
    responder();
    renderizar(<GradePage />, "/grade?turma=1");

    expect(await screen.findByText("Matemática")).toBeInTheDocument();
    expect(screen.getByText("Joana Prado")).toBeInTheDocument();
    // Cabeçalho da coluna e o horário da linha: é o cruzamento que faz a
    // tela ser uma grade e não uma lista.
    expect(screen.getByText("Segunda")).toBeInTheDocument();
    expect(screen.getByText("07:00–07:50")).toBeInTheDocument();
  });

  it("não deixa a falha de rede passar por grade vazia", async () => {
    autenticarComo("diretor");
    responder({
      grade: () => HttpResponse.json({ detail: "boom" }, { status: 500 }),
    });
    renderizar(<GradePage />, "/grade?turma=1");

    expect(
      await screen.findByText(/Não foi possível carregar a grade/),
    ).toBeInTheDocument();
    // Falha de leitura não pode abrir a tela de montagem: a direção
    // concluiria que a turma está sem horário e remontaria em cima.
    expect(screen.queryByText("Matemática")).not.toBeInTheDocument();
  });

  it("avisa quando o turno não tem tempo cadastrado, em vez de matriz vazia", async () => {
    autenticarComo("diretor");
    responder({ tempos: () => HttpResponse.json([]) });
    renderizar(<GradePage />, "/grade?turma=1");

    expect(
      await screen.findByText(/ainda não tem tempos de aula cadastrados/),
    ).toBeInTheDocument();
  });

  it("professor vê a grade sem as ações de montagem", async () => {
    autenticarComo("professor");
    responder();
    renderizar(<GradePage />, "/grade?turma=1");

    // Controle positivo: a grade carregou de verdade pra este perfil.
    expect(await screen.findByText("Matemática")).toBeInTheDocument();
    expect(screen.queryByText("Remover")).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Clonar grade" }),
    ).not.toBeInTheDocument();
  });
});
