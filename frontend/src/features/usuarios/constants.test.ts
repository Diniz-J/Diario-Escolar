import { describe, expect, it } from "vitest";

import { opcoesDePerfil } from "./constants";

describe("opcoesDePerfil", () => {
  it("não oferece administrador pra quem não é admin global", () => {
    const valores = opcoesDePerfil(false).map((o) => o.value);
    // Controle positivo: sem ele, a ausência abaixo passaria com a
    // lista vazia.
    expect(valores).toContain("secretaria");
    expect(valores).toContain("professor");
    expect(valores).not.toContain("admin");
  });

  it("oferece administrador pro admin global", () => {
    expect(opcoesDePerfil(true).map((o) => o.value)).toContain("admin");
  });

  it("oferece os perfis de direção, que é o ponto da tela", () => {
    const valores = opcoesDePerfil(false).map((o) => o.value);
    for (const perfil of ["diretor", "secretaria", "coordenador"]) {
      expect(valores).toContain(perfil);
    }
  });
});
