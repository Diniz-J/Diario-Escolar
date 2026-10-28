import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";

import {
  getAccessToken,
  getRefreshToken,
  setTokens,
} from "@/features/auth/tokenStorage";
import { servidor } from "@/test/servidor";

import { api } from "./api";

const API = "http://api.test/api/v1";

// Caminho sem cobertura até aqui, e o mais consequente do axios: se o
// refresh parar de funcionar, todo usuário é deslogado quando o access
// expira (~1h), e nenhum teste de tela percebe. Entrou junto do bump de
// axios 1.16 -> 1.21 pra provar que o interceptor sobreviveu.
describe("api — refresh automático no 401", () => {
  it("renova o token e refaz o request original, de forma transparente", async () => {
    setTokens({ access: "velho", refresh: "refresh-1" });
    const autorizacoes: (string | null)[] = [];

    servidor.use(
      http.get(`${API}/alunos/`, ({ request }) => {
        const auth = request.headers.get("Authorization");
        autorizacoes.push(auth);
        if (auth === "Bearer novo") {
          return HttpResponse.json([{ id: 1, nome_completo: "Ana" }]);
        }
        return HttpResponse.json({ detail: "expirado" }, { status: 401 });
      }),
      http.post(`${API}/auth/token/refresh/`, () =>
        HttpResponse.json({ access: "novo", refresh: "refresh-2" }),
      ),
    );

    const { data } = await api.get("/alunos/");

    // O chamador recebe o resultado, não o 401.
    expect(data).toEqual([{ id: 1, nome_completo: "Ana" }]);
    expect(autorizacoes).toEqual(["Bearer velho", "Bearer novo"]);
  });

  it("guarda o refresh rotacionado, não o antigo", async () => {
    // O backend tem ROTATE_REFRESH_TOKENS + BLACKLIST_AFTER_ROTATION:
    // manter o refresh antigo põe na mão um token já na blacklist, e a
    // sessão morre no refresh seguinte em vez de durar os 7 dias.
    setTokens({ access: "velho", refresh: "refresh-1" });
    servidor.use(
      http.get(`${API}/alunos/`, ({ request }) =>
        request.headers.get("Authorization") === "Bearer novo"
          ? HttpResponse.json([])
          : HttpResponse.json({ detail: "expirado" }, { status: 401 }),
      ),
      http.post(`${API}/auth/token/refresh/`, () =>
        HttpResponse.json({ access: "novo", refresh: "refresh-2" }),
      ),
    );

    await api.get("/alunos/");

    expect(getAccessToken()).toBe("novo");
    expect(getRefreshToken()).toBe("refresh-2");
  });

  it("limpa a sessão quando o refresh também falha", async () => {
    setTokens({ access: "velho", refresh: "refresh-morto" });
    servidor.use(
      http.get(`${API}/alunos/`, () =>
        HttpResponse.json({ detail: "expirado" }, { status: 401 }),
      ),
      http.post(`${API}/auth/token/refresh/`, () =>
        HttpResponse.json({ detail: "invalido" }, { status: 401 }),
      ),
    );

    await expect(api.get("/alunos/")).rejects.toThrow();

    // Com o storage vazio o AuthProvider manda pro /login.
    expect(getAccessToken()).toBeNull();
    expect(getRefreshToken()).toBeNull();
  });

  it("compartilha um único refresh entre 401 simultâneos", async () => {
    // Página com várias queries: o access expira e todas levam 401 ao
    // mesmo tempo. Sem a promise compartilhada seriam N refreshes, e com
    // rotação cada um invalida o anterior — a sessão cairia.
    setTokens({ access: "velho", refresh: "refresh-1" });
    let refreshes = 0;
    servidor.use(
      http.get(`${API}/alunos/`, ({ request }) =>
        request.headers.get("Authorization") === "Bearer novo"
          ? HttpResponse.json([])
          : HttpResponse.json({ detail: "expirado" }, { status: 401 }),
      ),
      http.get(`${API}/turmas/`, ({ request }) =>
        request.headers.get("Authorization") === "Bearer novo"
          ? HttpResponse.json([])
          : HttpResponse.json({ detail: "expirado" }, { status: 401 }),
      ),
      http.get(`${API}/disciplinas/`, ({ request }) =>
        request.headers.get("Authorization") === "Bearer novo"
          ? HttpResponse.json([])
          : HttpResponse.json({ detail: "expirado" }, { status: 401 }),
      ),
      http.post(`${API}/auth/token/refresh/`, () => {
        refreshes += 1;
        return HttpResponse.json({ access: "novo", refresh: "refresh-2" });
      }),
    );

    await Promise.all([
      api.get("/alunos/"),
      api.get("/turmas/"),
      api.get("/disciplinas/"),
    ]);

    expect(refreshes).toBe(1);
  });
});
