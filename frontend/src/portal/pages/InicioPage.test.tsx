import { http, HttpResponse } from "msw";
import { act } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { screen } from "@testing-library/react";

import { InicioPage } from "@/portal/pages/InicioPage";
import { renderizar } from "@/test/render";
import { servidor } from "@/test/servidor";

const PORTAL = "http://api.test/api/v1/portal";

function responder(): void {
  servidor.use(
    http.get(`${PORTAL}/alunos/`, () =>
      HttpResponse.json([
        {
          id: 1,
          nome_completo: "Ana Lima",
          matricula: "M1",
          turma: "6º A",
          ano_letivo: 2026,
          ativo: true,
        },
      ]),
    ),
    http.get(`${PORTAL}/comunicados/`, () =>
      HttpResponse.json([
        { id: 1, titulo: "Reunião de pais", enviado_em: "2026-03-10T12:00:00-03:00" },
      ]),
    ),
  );
}

// O componente guarda o prompt em nível de módulo, então o evento pode
// ser disparado antes de montar — é assim que ele funciona no browser.
function dispararPrompt(): void {
  const evento = new Event("beforeinstallprompt") as Event & {
    prompt: () => Promise<void>;
    userChoice: Promise<{ outcome: string }>;
  };
  evento.prompt = async () => {};
  evento.userChoice = Promise.resolve({ outcome: "accepted" });
  act(() => {
    window.dispatchEvent(evento);
  });
}

function limpar(): void {
  act(() => {
    window.dispatchEvent(new Event("appinstalled"));
  });
  localStorage.removeItem("pwa_instalacao_dispensada");
}

describe("InicioPage do portal", () => {
  it("mostra o convite de instalação acima dos comunicados", async () => {
    limpar();
    responder();
    dispararPrompt();
    renderizar(<InicioPage />);

    // Controle positivo: a tela carregou de verdade, então a ordem
    // abaixo fala do que a página renderizou e não de tela vazia.
    expect(await screen.findByText("Ana Lima")).toBeInTheDocument();

    const convite = screen.getByText(/tenha o diário na tela inicial/i);
    const comunicados = screen.getByRole("heading", {
      name: /comunicados recentes/i,
    });

    // `DOCUMENT_POSITION_FOLLOWING`: o convite vem ANTES do título dos
    // comunicados na ordem do documento. Era o contrário, e no celular
    // isso o deixava abaixo da dobra.
    expect(
      convite.compareDocumentPosition(comunicados) &
        Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();

    limpar();
  });

  it("sem instalação possível, o card inteiro não aparece", async () => {
    limpar();
    responder();
    renderizar(<InicioPage />);

    expect(await screen.findByText("Ana Lima")).toBeInTheDocument();
    expect(screen.queryByText(/tenha o diário na tela inicial/i)).toBeNull();
  });
});
