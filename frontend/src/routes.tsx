import { Navigate, Route, Routes } from "react-router-dom";

import { AppLayout } from "@/components/AppLayout";
import { ProtectedRoute } from "@/components/ProtectedRoute";
import { AlunosPage } from "@/pages/AlunosPage";
import { DashboardPage } from "@/pages/DashboardPage";
import { LoginPage } from "@/pages/LoginPage";
import { NotFoundPage } from "@/pages/NotFoundPage";
import { TurmaDetalhePage } from "@/pages/TurmaDetalhePage";
import { TurmasPage } from "@/pages/TurmasPage";

// Mapa central de rotas autenticadas. Páginas de ocorrências e presença
// chegam em PRs subsequentes.
export function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />

      <Route element={<ProtectedRoute />}>
        <Route element={<AppLayout />}>
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/alunos" element={<AlunosPage />} />
          <Route path="/turmas" element={<TurmasPage />} />
          <Route path="/turmas/:id" element={<TurmaDetalhePage />} />
        </Route>
      </Route>

      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  );
}
