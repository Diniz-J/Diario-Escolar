import { Navigate, Route, Routes } from "react-router-dom";

import { AppLayout } from "@/components/AppLayout";
import { ProtectedRoute } from "@/components/ProtectedRoute";
import { AlunosPage } from "@/pages/AlunosPage";
import { AvaliacaoDetalhePage } from "@/pages/AvaliacaoDetalhePage";
import { AvaliacoesPage } from "@/pages/AvaliacoesPage";
import { BoletimPage } from "@/pages/BoletimPage";
import { ContaSenhaPage } from "@/pages/ContaSenhaPage";
import { DashboardPage } from "@/pages/DashboardPage";
import { DiarioAulaPage } from "@/pages/DiarioAulaPage";
import { DisciplinasPage } from "@/pages/DisciplinasPage";
import { EsqueciSenhaPage } from "@/pages/EsqueciSenhaPage";
import { ImportPage } from "@/pages/ImportPage";
import { LoginPage } from "@/pages/LoginPage";
import { NotasFinaisPage } from "@/pages/NotasFinaisPage";
import { NotFoundPage } from "@/pages/NotFoundPage";
import { RedefinirSenhaPage } from "@/pages/RedefinirSenhaPage";
import { OcorrenciaDetalhePage } from "@/pages/OcorrenciaDetalhePage";
import { OcorrenciasPage } from "@/pages/OcorrenciasPage";
import { PeriodosAvaliativosPage } from "@/pages/PeriodosAvaliativosPage";
import { PlanoEnsinoDetalhePage } from "@/pages/PlanoEnsinoDetalhePage";
import { PlanosEnsinoPage } from "@/pages/PlanosEnsinoPage";
import { PresencaDetalhePage } from "@/pages/PresencaDetalhePage";
import { ProfessoresPage } from "@/pages/ProfessoresPage";
import { PresencaPage } from "@/pages/PresencaPage";
import { TurmaDetalhePage } from "@/pages/TurmaDetalhePage";
import { TurmasPage } from "@/pages/TurmasPage";

// Mapa central de rotas autenticadas. Páginas de ocorrências e presença
// chegam em PRs subsequentes.
export function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/esqueci-senha" element={<EsqueciSenhaPage />} />
      <Route path="/redefinir-senha" element={<RedefinirSenhaPage />} />

      <Route element={<ProtectedRoute />}>
        <Route element={<AppLayout />}>
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/conta/senha" element={<ContaSenhaPage />} />
          <Route path="/import" element={<ImportPage />} />
          <Route path="/alunos" element={<AlunosPage />} />
          <Route path="/turmas" element={<TurmasPage />} />
          <Route path="/turmas/:id" element={<TurmaDetalhePage />} />
          <Route path="/disciplinas" element={<DisciplinasPage />} />
          <Route path="/professores" element={<ProfessoresPage />} />
          <Route path="/planos-ensino" element={<PlanosEnsinoPage />} />
          <Route
            path="/planos-ensino/:id"
            element={<PlanoEnsinoDetalhePage />}
          />
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
          <Route path="/diario" element={<DiarioAulaPage />} />
          <Route path="/avaliacoes" element={<AvaliacoesPage />} />
          <Route
            path="/avaliacoes/:id"
            element={<AvaliacaoDetalhePage />}
          />
          <Route path="/notas-finais" element={<NotasFinaisPage />} />
          <Route path="/boletim/:alunoId" element={<BoletimPage />} />
          <Route
            path="/configuracao/periodos"
            element={<PeriodosAvaliativosPage />}
          />
        </Route>
      </Route>

      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  );
}
