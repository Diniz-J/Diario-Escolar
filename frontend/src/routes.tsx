import { Navigate, Route, Routes } from "react-router-dom";

import { AppLayout } from "@/components/AppLayout";
import { ProtectedRoute } from "@/components/ProtectedRoute";
import { AlunosPage } from "@/pages/AlunosPage";
import { DashboardPage } from "@/pages/DashboardPage";
import { LoginPage } from "@/pages/LoginPage";
import { NotFoundPage } from "@/pages/NotFoundPage";
import { PlaceholderPage } from "@/pages/PlaceholderPage";

// Mapa central de rotas.
//
// Estrutura:
// - `/login` é público.
// - `/` redireciona pra `/dashboard`.
// - Todas as demais rotas ficam aninhadas em ProtectedRoute (exige auth)
//   e AppLayout (sidebar + outlet). O Outlet do AppLayout é onde a página
//   específica é renderizada.
// - `*` cai no 404 (sem sidebar, pra não parecer rota válida).
export function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />

      {/* Rotas autenticadas com layout de sidebar */}
      <Route element={<ProtectedRoute />}>
        <Route element={<AppLayout />}>
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/alunos" element={<AlunosPage />} />
          <Route
            path="/turmas"
            element={<PlaceholderPage titulo="Turmas" />}
          />
          <Route
            path="/ocorrencias"
            element={<PlaceholderPage titulo="Ocorrências" />}
          />
          <Route
            path="/presenca"
            element={<PlaceholderPage titulo="Presença" />}
          />
        </Route>
      </Route>

      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  );
}
