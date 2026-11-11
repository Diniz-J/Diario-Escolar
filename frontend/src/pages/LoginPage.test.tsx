import { act } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { screen } from "@testing-library/react";

import { LoginPage } from "@/pages/LoginPage";
import { PortalAuthProvider } from "@/features/portal/PortalAuthContext";
import { EntrarPage } from "@/portal/pages/EntrarPage";
import { renderizar } from "@/test/render";

// Mesmo molde do teste do botão: o prompt é estado de módulo e pode
// chegar antes da montagem, como chega no browser.
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

// As duas telas de login existem no teste pelo mesmo motivo: o botão de
// instalar morava só na sidebar e no card da home, e as duas exigem
// sessão. Quem abre o endereço cai aqui, e aqui não havia nada.
describe("convite de instalação nas telas de login", () => {
  it("o login do staff mostra o botão quando dá pra instalar", () => {
    limpar();
    dispararPrompt();
    renderizar(<LoginPage />);
    expect(
      screen.getByRole("button", { name: /instalar app/i }),
    ).toBeInTheDocument();
    limpar();
  });

  it("o login do staff não mostra nada sem instalação possível", () => {
    limpar();
    renderizar(<LoginPage />);
    // Controle positivo: a tela é a de login mesmo.
    expect(screen.getByLabelText(/usuário/i)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /instalar app/i })).toBeNull();
  });

  it("o login do portal mostra o botão quando dá pra instalar", () => {
    limpar();
    dispararPrompt();
    renderizar(
      <PortalAuthProvider>
        <EntrarPage />
      </PortalAuthProvider>,
    );
    expect(
      screen.getByRole("button", { name: /instalar app/i }),
    ).toBeInTheDocument();
    limpar();
  });

  it("o login do portal não mostra nada sem instalação possível", () => {
    limpar();
    renderizar(
      <PortalAuthProvider>
        <EntrarPage />
      </PortalAuthProvider>,
    );
    expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /instalar app/i })).toBeNull();
  });
});
