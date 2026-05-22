import { Navigate, Outlet, useLocation } from "react-router-dom";

import { useAuth } from "@/features/auth/useAuth";

// Wrapper de rota que exige autenticação. Uso no router:
//
//   <Route element={<ProtectedRoute />}>
//     <Route path="/dashboard" element={<DashboardPage />} />
//     {...outras rotas privadas}
//   </Route>
//
// O `<Outlet />` é onde o React Router injeta a rota filha que casou
// com a URL. Funciona como um "slot".
//
// `state={{ from: location }}` permite que a LoginPage devolva o usuário
// pra rota que ele tentou acessar originalmente, depois de logar.
export function ProtectedRoute() {
  const { isAuthenticated, isLoading } = useAuth();
  const location = useLocation();

  if (isLoading) {
    // Hidratação do token do localStorage ainda em curso. Mostrar
    // placeholder evita "flash" de redirect pro login antes do estado
    // verdadeiro carregar.
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <p className="text-muted-foreground">Carregando...</p>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace state={{ from: location }} />;
  }

  return <Outlet />;
}
