import type { TokenPair } from "./types";

// Encapsula leitura/escrita dos tokens JWT no localStorage.
//
// localStorage é síncrono e persiste entre reloads — adequado pra MVP.
// Se um dia migrarmos pra cookies httpOnly (mais seguro contra XSS), só
// esse arquivo muda. O resto do app continua chamando `getAccessToken()`,
// `setTokens()`, etc.

const ACCESS_KEY = "diario_access_token";
const REFRESH_KEY = "diario_refresh_token";

export function getAccessToken(): string | null {
  return localStorage.getItem(ACCESS_KEY);
}

export function getRefreshToken(): string | null {
  return localStorage.getItem(REFRESH_KEY);
}

export function setTokens(tokens: TokenPair): void {
  localStorage.setItem(ACCESS_KEY, tokens.access);
  localStorage.setItem(REFRESH_KEY, tokens.refresh);
}

export function clearTokens(): void {
  localStorage.removeItem(ACCESS_KEY);
  localStorage.removeItem(REFRESH_KEY);
}
