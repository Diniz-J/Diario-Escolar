import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { BotaoInstalarApp } from "./BotaoInstalarApp";

// Dispara um `beforeinstallprompt` falso com o mínimo que o componente usa.
// O listener de nível de módulo do componente captura e guarda o evento.
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

const uaOriginal = navigator.userAgent;

function definirUserAgent(valor: string): void {
  Object.defineProperty(navigator, "userAgent", {
    value: valor,
    configurable: true,
  });
}

// O prompt guardado é estado de módulo e vazaria entre testes. O evento
// `appinstalled` zera (é o que o componente escuta pra sumir após instalar).
function resetarEstado(): void {
  act(() => {
    window.dispatchEvent(new Event("appinstalled"));
  });
  definirUserAgent(uaOriginal);
}

beforeEach(resetarEstado);
afterEach(resetarEstado);

describe("BotaoInstalarApp", () => {
  it("não renderiza quando não há prompt nativo e não é iOS", () => {
    render(<BotaoInstalarApp />);
    expect(
      screen.queryByRole("button", { name: /instalar app/i }),
    ).toBeNull();
  });

  it("mostra o botão quando o navegador oferece instalação", () => {
    dispararPrompt();
    render(<BotaoInstalarApp />);
    expect(
      screen.getByRole("button", { name: /instalar app/i }),
    ).toBeInTheDocument();
  });

  it("no iOS mostra o botão e abre as instruções ao clicar", async () => {
    definirUserAgent(
      "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15",
    );
    render(<BotaoInstalarApp />);

    const botao = screen.getByRole("button", { name: /instalar app/i });
    await userEvent.click(botao);

    expect(screen.getByText(/instalar no iphone/i)).toBeInTheDocument();
    expect(
      screen.getByText(/adicionar à tela de início/i),
    ).toBeInTheDocument();
  });
});
