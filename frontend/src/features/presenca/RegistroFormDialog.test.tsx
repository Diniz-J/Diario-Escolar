import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { RegistroFormDialog } from "@/features/presenca/RegistroFormDialog";
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

// `autenticarComo` forja o JWT com `user_id: 1`, e é por ele que a tela
// acha o Professor do usuário logado.
const PROFESSOR = { id: 7, escola: 1, usuario: 1, nome_completo: "Joana Prado" };

function tempo(ordem: number, inicio: string, fim: string) {
  return {
    id: 100 + ordem,
    escola: 1,
    turno: "matutino",
    turno_display: "Matutino",
    ordem,
    hora_inicio: inicio,
    hora_fim: fim,
    ativo: true,
  };
}

function slot(ordem: number, disciplina = 3, nome = "Matemática") {
  return {
    id: 500 + ordem,
    escola: 1,
    lecionamento: 9,
    turma: 1,
    turma_nome: "6º A",
    dia_semana: 0,
    dia_semana_display: "Segunda",
    tempo: 100 + ordem,
    tempo_ordem: ordem,
    tempo_hora_inicio: "07:00:00",
    tempo_hora_fim: "07:50:00",
    disciplina,
    disciplina_nome: nome,
    professor: PROFESSOR.id,
    professor_nome: PROFESSOR.nome_completo,
    ativo: true,
  };
}

interface Cenario {
  tempos?: unknown[];
  slots?: unknown[];
  turmas?: () => Response;
  // Por default o usuário logado (user_id 1 do JWT forjado) É o professor
  // do mock. Passar outro valor simula quem não tem cadastro de Professor.
  professores?: unknown[];
}

function responder({ tempos, slots, turmas, professores }: Cenario = {}) {
  const enviados: Record<string, unknown>[] = [];
  servidor.use(
    http.get(`${API}/turmas/`, turmas ?? (() => HttpResponse.json([TURMA]))),
    http.get(`${API}/professores/`, () =>
      HttpResponse.json(professores ?? [PROFESSOR]),
    ),
    http.get(`${API}/tempos-aula/`, () =>
      HttpResponse.json(tempos ?? [tempo(1, "07:00:00", "07:50:00")]),
    ),
    http.get(`${API}/grade-aulas/`, () => HttpResponse.json(slots ?? [])),
    http.post(`${API}/registros-presenca/`, async ({ request }) => {
      const corpo = (await request.json()) as Record<string, unknown>;
      enviados.push(corpo);
      return HttpResponse.json({ id: 42, ...corpo }, { status: 201 });
    }),
  );
  return enviados;
}

function abrir() {
  renderizar(
    <RegistroFormDialog open onOpenChange={() => {}} />,
    "/presenca",
  );
}

describe("RegistroFormDialog — bloco de tempos", () => {
  it("pré-marca os tempos que a grade dá ao professor", async () => {
    autenticarComo("professor");
    responder({
      tempos: [
        tempo(1, "07:00:00", "07:50:00"),
        tempo(2, "07:50:00", "08:40:00"),
        tempo(3, "08:40:00", "09:30:00"),
      ],
      slots: [slot(1), slot(2)],
    });
    abrir();

    // Os dois tempos da grade entram marcados; o terceiro não.
    await waitFor(() =>
      expect(screen.getAllByRole("button", { pressed: true })).toHaveLength(2),
    );
    expect(
      await screen.findByText("Marcados pela grade horária desta turma."),
    ).toBeInTheDocument();
  });

  it("manda o bloco da grade e a disciplina no payload", async () => {
    autenticarComo("professor");
    const enviados = responder({
      tempos: [
        tempo(1, "07:00:00", "07:50:00"),
        tempo(2, "07:50:00", "08:40:00"),
      ],
      slots: [slot(1), slot(2)],
    });
    abrir();

    await waitFor(() =>
      expect(screen.getAllByRole("button", { pressed: true })).toHaveLength(2),
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Abrir chamada" }),
    );

    await waitFor(() => expect(enviados).toHaveLength(1));
    expect(enviados[0].tempos).toEqual([1, 2]);
    expect(enviados[0].disciplina).toBe(3);
  });

  it("deixa desmarcar um tempo do bloco sugerido", async () => {
    autenticarComo("professor");
    const enviados = responder({
      tempos: [
        tempo(1, "07:00:00", "07:50:00"),
        tempo(2, "07:50:00", "08:40:00"),
      ],
      slots: [slot(1), slot(2)],
    });
    abrir();

    await waitFor(() =>
      expect(screen.getAllByRole("button", { pressed: true })).toHaveLength(2),
    );
    // O professor cobriu só o segundo tempo: desmarca o primeiro.
    const botoes = screen.getAllByRole("button", { pressed: true });
    await userEvent.click(botoes[0]);
    await userEvent.click(
      screen.getByRole("button", { name: "Abrir chamada" }),
    );

    await waitFor(() => expect(enviados).toHaveLength(1));
    expect(enviados[0].tempos).toEqual([2]);
  });

  it("quem não dá aula na turma recebe o dia todo, sem disciplina", async () => {
    // Secretaria/diretor sem cadastro de Professor: a grade da turma tem
    // aula, mas não é dele, então a sugestão é o turno inteiro.
    autenticarComo("diretor");
    const enviados = responder({
      tempos: [
        tempo(1, "07:00:00", "07:50:00"),
        tempo(2, "07:50:00", "08:40:00"),
      ],
      slots: [slot(1)],
      professores: [{ ...PROFESSOR, usuario: 99 }],
    });
    abrir();

    await waitFor(() =>
      expect(screen.getAllByRole("button", { pressed: true })).toHaveLength(2),
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Abrir chamada" }),
    );

    await waitFor(() => expect(enviados).toHaveLength(1));
    expect(enviados[0].tempos).toEqual([1, 2]);
    expect(enviados[0].disciplina).toBeUndefined();
  });

  it("o critério é o cadastro de professor, não o perfil", async () => {
    // Diretor que também dá aula (escola pequena) tem grade própria: a
    // sugestão é a dele, não o dia todo.
    autenticarComo("diretor");
    responder({
      tempos: [
        tempo(1, "07:00:00", "07:50:00"),
        tempo(2, "07:50:00", "08:40:00"),
        tempo(3, "08:40:00", "09:30:00"),
      ],
      slots: [slot(2)],
    });
    abrir();

    await waitFor(() =>
      expect(screen.getAllByRole("button", { pressed: true })).toHaveLength(1),
    );
  });

  it("sem catálogo de tempos, não mostra seletor e não manda o campo", async () => {
    // É a escola que ainda não montou a grade: a chamada tem que
    // continuar funcionando, e o backend assume um tempo.
    autenticarComo("diretor");
    const enviados = responder({
      tempos: [],
      professores: [{ ...PROFESSOR, usuario: 99 }],
    });
    abrir();

    expect(
      await screen.findByRole("button", { name: "Abrir chamada" }),
    ).toBeInTheDocument();
    expect(screen.queryByText("Dia todo")).not.toBeInTheDocument();

    await userEvent.click(
      screen.getByRole("button", { name: "Abrir chamada" }),
    );
    await waitFor(() => expect(enviados).toHaveLength(1));
    expect(enviados[0].tempos).toBeUndefined();
    expect(enviados[0].turma).toBe(TURMA.id);
  });

  it("falha ao carregar turmas avisa e trava o envio", async () => {
    autenticarComo("diretor");
    responder({
      turmas: () => HttpResponse.json({ detail: "boom" }, { status: 500 }),
    });
    abrir();

    // Sem a lista de turmas não há chamada a abrir; o aviso é o do
    // projeto, não "Selecione uma turma" (que culparia o usuário).
    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: "Abrir chamada" }),
      ).toBeDisabled(),
    );
  });

  it("falha ao carregar tempos avisa e trava o envio", async () => {
    // Rede caiu no catálogo de tempos: deixar passar faria a chamada ser
    // enviada sem `tempos`, e o backend assumiria um tempo — a chamada
    // entraria no tempo errado sem o usuário saber. O aviso é o mesmo
    // genérico do projeto.
    autenticarComo("diretor");
    responder();
    servidor.use(
      http.get(`${API}/tempos-aula/`, () =>
        HttpResponse.json({ detail: "boom" }, { status: 500 }),
      ),
    );
    abrir();

    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: "Abrir chamada" }),
      ).toBeDisabled(),
    );
  });

  it("troca de turma reseta a escolha explícita de tempos", async () => {
    // Professor desmarca um tempo na turma A e troca pra turma B: a
    // sugestão da grade precisa voltar, senão o formulário manda o bloco
    // da turma anterior sem avisar.
    autenticarComo("professor");
    responder({
      tempos: [
        tempo(1, "07:00:00", "07:50:00"),
        tempo(2, "07:50:00", "08:40:00"),
      ],
      slots: [slot(1), slot(2)],
      turmas: () =>
        HttpResponse.json([TURMA, { ...TURMA, id: 2, nome: "6º B" }]),
    });
    abrir();

    // Como há duas turmas, a sugestão inicial não aparece sozinha; o
    // professor escolhe a turma A primeiro.
    const [seletorTurma] = await screen.findAllByRole("combobox");
    await userEvent.click(seletorTurma);
    await userEvent.click(await screen.findByRole("option", { name: /6º A/ }));

    await waitFor(() =>
      expect(screen.getAllByRole("button", { pressed: true })).toHaveLength(2),
    );

    // Desmarca o 1º tempo.
    const marcados = screen.getAllByRole("button", { pressed: true });
    await userEvent.click(marcados[0]);
    await waitFor(() =>
      expect(screen.getAllByRole("button", { pressed: true })).toHaveLength(1),
    );

    // Troca pra 6º B: a sugestão da grade volta pra bloco cheio.
    await userEvent.click(screen.getAllByRole("combobox")[0]);
    await userEvent.click(await screen.findByRole("option", { name: /6º B/ }));
    await waitFor(() =>
      expect(screen.getAllByRole("button", { pressed: true })).toHaveLength(2),
    );
  });
});
