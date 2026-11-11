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
// O opt-out mora no localStorage e vazaria do mesmo jeito.
function resetarEstado(): void {
  act(() => {
    window.dispatchEvent(new Event("appinstalled"));
  });
  localStorage.removeItem("pwa_instalacao_dispensada");
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

  // O caso que o opt-out existe pra resolver: no iPhone, voltar pela aba
  // do Safari depois de instalar mostraria o convite de novo, porque
  // `navigator.standalone` só é verdadeiro dentro do app. Sem o "já
  // instalei" não há como sumir.
  it("no iOS, 'já instalei' esconde o botão e ele não volta", async () => {
    definirUserAgent(
      "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15",
    );
    const { unmount } = render(<BotaoInstalarApp />);

    await userEvent.click(
      screen.getByRole("button", { name: /instalar app/i }),
    );
    await userEvent.click(
      screen.getByRole("button", { name: /já instalei/i }),
    );

    expect(screen.queryByRole("button", { name: /instalar app/i })).toBeNull();

    // Visita seguinte: o opt-out está no localStorage, não na memória
    // do componente.
    unmount();
    render(<BotaoInstalarApp />);
    expect(screen.queryByRole("button", { name: /instalar app/i })).toBeNull();
  });

  // Controle negativo do teste acima: sem o opt-out gravado, a montagem
  // nova mostra o botão. Sem isto, o "não volta" passaria mesmo se o
  // componente tivesse parado de renderizar por outro motivo.
  it("no iOS, sem dispensar, o botão continua na montagem seguinte", () => {
    definirUserAgent(
      "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15",
    );
    const { unmount } = render(<BotaoInstalarApp />);
    unmount();
    render(<BotaoInstalarApp />);
    expect(
      screen.getByRole("button", { name: /instalar app/i }),
    ).toBeInTheDocument();
  });

  // O opt-out não é só do iOS: quem dispensa no Android também não quer
  // ver de novo, mesmo com o prompt nativo disponível.
  it("dispensar também vale para o prompt nativo", async () => {
    definirUserAgent(
      "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15",
    );
    render(<BotaoInstalarApp />);
    await userEvent.click(
      screen.getByRole("button", { name: /instalar app/i }),
    );
    await userEvent.click(
      screen.getByRole("button", { name: /já instalei/i }),
    );

    definirUserAgent(uaOriginal);
    dispararPrompt();
    render(<BotaoInstalarApp />);
    expect(screen.queryByRole("button", { name: /instalar app/i })).toBeNull();
  });
});
