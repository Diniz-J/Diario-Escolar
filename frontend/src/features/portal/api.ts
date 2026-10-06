import axios, { type InternalAxiosRequestConfig } from "axios";

import {
  clearPortalTokens,
  getPortalAccessToken,
  getPortalRefreshToken,
  setPortalTokens,
} from "./tokenStorage";

// Cliente HTTP do portal. Separado do `lib/api.ts` do staff de propósito:
// os dois mandam Bearer, mas de tokens diferentes, e o backend recusa o
// token do outro lado (`apps/common/authentication.py`). Um cliente só,
// lendo um storage só, logaria o pai e o funcionário fora um do outro.
export const portalApi = axios.create({
  baseURL: `${import.meta.env.VITE_API_URL}/portal`,
  headers: { "Content-Type": "application/json" },
});

// Endpoints públicos do portal: mandar Authorization neles é inofensivo,
// mas evitar deixa claro o que é público e não sujeita o login a um
// access expirado pendurado no storage.
function ehPublico(url: string): boolean {
  return url.startsWith("/auth/login") || url.startsWith("/auth/senha");
}

portalApi.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const url = config.url ?? "";
  const token = getPortalAccessToken();
  if (token && !ehPublico(url) && !url.startsWith("/auth/refresh")) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

interface RetryableConfig extends InternalAxiosRequestConfig {
  _retry?: boolean;
}

// Promise compartilhada: se várias queries caírem em 401 ao mesmo tempo
// (comum quando o access expira numa tela com 3 requests), todas esperam
// o MESMO refresh em vez de disparar três.
let refreshPromise: Promise<string> | null = null;

async function executarRefresh(): Promise<string> {
  const refresh = getPortalRefreshToken();
  if (!refresh) {
    throw new Error("Sem refresh token do portal.");
  }
  // Axios puro: passar pelo `portalApi` recairia no interceptor e podia
  // recursar.
  const resp = await axios.post<{ access: string; refresh?: string }>(
    `${import.meta.env.VITE_API_URL}/portal/auth/refresh/`,
    { refresh },
  );
  // `ROTATE_REFRESH_TOKENS` está ligado e o anterior vai pra blacklist,
  // então o refresh NOVO tem que ser gravado. Guardar o antigo faria a
  // sessão morrer no refresh seguinte — foi exatamente o bug do cliente
  // do staff, corrigido no #112.
  const novoAccess = resp.data.access;
  setPortalTokens({
    access: novoAccess,
    refresh: resp.data.refresh ?? refresh,
  });
  return novoAccess;
}

portalApi.interceptors.response.use(
  (resp) => resp,
  async (error) => {
    const config = error.config as RetryableConfig | undefined;
    const status = error.response?.status;
    if (
      status !== 401 ||
      config == null ||
      config._retry ||
      ehPublico(config.url ?? "")
    ) {
      throw error;
    }
    config._retry = true;
    try {
      refreshPromise = refreshPromise ?? executarRefresh();
      const novoAccess = await refreshPromise;
      config.headers.Authorization = `Bearer ${novoAccess}`;
      return portalApi(config);
    } catch (falha) {
      // Refresh morto (expirado, rotacionado por outra aba, senha trocada):
      // limpa e deixa o PortalAuthContext mandar pro login.
      clearPortalTokens();
      throw falha;
    } finally {
      refreshPromise = null;
    }
  },
);
