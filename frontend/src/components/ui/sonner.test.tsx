import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { toast } from "sonner";

import { Toaster } from "./sonner";

/**
 * O app é light-mode permanente (`index.css`: `color-scheme: light`, sem
 * bloco `.dark`). O wrapper do shadcn vinha com `theme="system"`, que faz
 * o sonner ler `prefers-color-scheme` e marcar `data-sonner-theme="dark"`
 * no aparelho com tema escuro — e aí os toasts, que são todos
 * `success`/`error` com `richColors`, pegam a paleta escura da lib
 * (`--success-bg: hsl(150, 100%, 6%)`, quase preto) dentro de uma tela
 * linho. O `style` inline do wrapper cobre só `--normal-*`, então não
 * alcança essas variáveis.
 */
describe("Toaster", () => {
  function fingirSistemaEscuro() {
    vi.stubGlobal(
      "matchMedia",
      vi.fn().mockImplementation((query: string) => ({
        matches: query.includes("dark"),
        media: query,
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        addListener: vi.fn(),
        removeListener: vi.fn(),
        dispatchEvent: vi.fn(),
        onchange: null,
      })),
    );
  }

  it("fica no tema claro mesmo com o sistema no escuro", async () => {
    fingirSistemaEscuro();
    render(<Toaster richColors position="bottom-right" />);
    toast.success("Aluno salvo com sucesso");

    await screen.findByText("Aluno salvo com sucesso");
    const toaster = document.querySelector("[data-sonner-toaster]");
    expect(toaster).toHaveAttribute("data-sonner-theme", "light");
  });
});
