// Tipos do domínio de autenticação. Espelham o contrato da API:
//
// - `LoginInput` é o payload de POST /api/v1/auth/token/
// - `TokenPair` é o que o backend devolve (access + refresh)
// - `JwtPayload` representa os claims dentro do token (ver
//   UsuarioTokenObtainPairSerializer no backend)
// - `Perfil` casa com Usuario.Perfil do backend

export type Perfil =
  | "admin"
  | "diretor"
  | "professor"
  | "secretaria"
  | "inspetor";

export interface LoginInput {
  username: string;
  password: string;
}

export interface TokenPair {
  access: string;
  refresh: string;
}

export interface JwtPayload {
  // Claims customizados injetados pelo UsuarioTokenObtainPairSerializer.
  escola_id: number | null;
  perfil: Perfil;
  // Claims padrão do SimpleJWT.
  user_id: number;
  exp: number; // unix timestamp em segundos
  iat: number;
  jti: string;
  token_type: "access" | "refresh";
}
