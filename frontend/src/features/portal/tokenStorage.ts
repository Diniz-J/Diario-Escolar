// Tokens da sessão do responsável, em chaves PRÓPRIAS.
//
// O portal e a área administrativa dividem a mesma origem (ver
// `PORTAL.md`, seção 4.5), então o localStorage é o mesmo. Com as chaves
// do staff (`diario_*`), um pai logando no mesmo navegador sobrescreveria
// a sessão do funcionário e vice-versa — e, pior, o cliente HTTP de um
// lado mandaria o token do outro, que o backend recusa (401 em loop).
//
// Se um dia migrar pra cookie httpOnly, só este arquivo muda.

const ACCESS_KEY = "portal_access_token";
const REFRESH_KEY = "portal_refresh_token";

export function getPortalAccessToken(): string | null {
  return localStorage.getItem(ACCESS_KEY);
}

export function getPortalRefreshToken(): string | null {
  return localStorage.getItem(REFRESH_KEY);
}

export function setPortalTokens(tokens: {
  access: string;
  refresh: string;
}): void {
  localStorage.setItem(ACCESS_KEY, tokens.access);
  localStorage.setItem(REFRESH_KEY, tokens.refresh);
}

export function clearPortalTokens(): void {
  localStorage.removeItem(ACCESS_KEY);
  localStorage.removeItem(REFRESH_KEY);
}
