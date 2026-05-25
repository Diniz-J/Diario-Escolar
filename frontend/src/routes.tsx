import { Navigate, Route, Routes } from "react-router-dom";

import { AppLayout } from "@/components/AppLayout";
import { ProtectedRoute } from "@/components/ProtectedRoute";
import { AlunosPage } from "@/pages/AlunosPage";
import { BoletimPage } from "@/pages/BoletimPage";
import { DashboardPage } from "@/pages/DashboardPage";
import { DisciplinasPage } from "@/pages/DisciplinasPage";
import { LoginPage } from "@/pages/LoginPage";
import { NotFoundPage } from "@/pages/NotFoundPage";
import { OcorrenciaDetalhePage } from "@/pages/OcorrenciaDetalhePage";
import { OcorrenciasPage } from "@/pages/OcorrenciasPage";
import { PresencaDetalhePage } from "@/pages/PresencaDetalhePage";
import { PresencaPage } from "@/pages/PresencaPage";
import { TarefaDetalhePage } from "@/pages/TarefaDetalhePage";
import { TarefasPage } from "@/pages/TarefasPage";
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
          <Route path="/disciplinas" element={<DisciplinasPage />} />
          <Route path="/ocorrencias" element={<OcorrenciasPage />} />
          <Route
            path="/ocorrencias/:id"
            element={<OcorrenciaDetalhePage />}
          />
          <Route path="/presenca" element={<PresencaPage />} />
          <Route
            path="/presenca/:id"
            element={<PresencaDetalhePage />}
          />
          <Route path="/tarefas" element={<TarefasPage />} />
          <Route path="/tarefas/:id" element={<TarefaDetalhePage />} />
          <Route path="/boletim/:alunoId" element={<BoletimPage />} />
        </Route>
      </Route>

      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  );
}
