import { Navigate, Outlet, useLocation } from "react-router-dom";

import { usePortalAuth } from "./usePortalAuth";

/**
 * Portão das rotas internas do portal.
 *
 * Manda pro `/portal/entrar`, nunca pro `/login` do staff: são sessões
 * diferentes e mandar o pai pra tela de funcionário seria confuso e
 * sugeriria que ele tem conta lá.
 */
export function PortalProtectedRoute() {
  const { responsavel, carregando } = usePortalAuth();
  const location = useLocation();

  if (carregando) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <p className="text-sm text-muted-foreground">Carregando...</p>
      </div>
    );
  }
  if (responsavel == null) {
    // `state.de` deixa o login devolver o pai pra onde ele tentou ir.
    return <Navigate to="/portal/entrar" replace state={{ de: location }} />;
  }
  return <Outlet />;
}
