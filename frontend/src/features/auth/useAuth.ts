import { useContext } from "react";

import { AuthContext } from "./AuthContext";

// Hook que componentes usam pra ler/manipular auth.
//
// Uso típico:
//
//   const { user, isAuthenticated, login, logout } = useAuth();
//
// O `if (!ctx)` garante que o hook só funciona dentro de <AuthProvider>.
// Se algum componente chamar fora, lança erro explícito em vez de
// `Cannot read property of undefined` no meio do render.
export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth deve ser chamado dentro de <AuthProvider>.");
  }
  return ctx;
}
