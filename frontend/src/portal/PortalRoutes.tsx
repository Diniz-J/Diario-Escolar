import { Route, Routes } from "react-router-dom";

import { PortalProtectedRoute } from "@/features/portal/PortalProtectedRoute";

import { PortalLayout } from "./PortalLayout";
import { AlunoPage } from "./pages/AlunoPage";
import { ComunicadoDetalhePage } from "./pages/ComunicadoDetalhePage";
import { ComunicadosPage } from "./pages/ComunicadosPage";
import { DefinirSenhaPage } from "./pages/DefinirSenhaPage";
import { EntrarPage } from "./pages/EntrarPage";
import { EsqueciSenhaPage } from "./pages/EsqueciSenhaPage";
import { InicioPage } from "./pages/InicioPage";

// Rotas RELATIVAS: esta árvore é descendente de `/portal/*` no `App.tsx`.
// Caminho absoluto aqui não casaria com a base do pai.
export function PortalRoutes() {
  return (
    <Routes>
      <Route path="entrar" element={<EntrarPage />} />
      <Route path="esqueci-senha" element={<EsqueciSenhaPage />} />
      <Route path="definir-senha" element={<DefinirSenhaPage />} />

      <Route element={<PortalProtectedRoute />}>
        <Route element={<PortalLayout />}>
          <Route index element={<InicioPage />} />
          <Route path="alunos/:id" element={<AlunoPage />} />
          <Route path="comunicados" element={<ComunicadosPage />} />
          <Route path="comunicados/:id" element={<ComunicadoDetalhePage />} />
        </Route>
      </Route>

      <Route path="*" element={<NaoEncontrado />} />
    </Routes>
  );
}

function NaoEncontrado() {
  return (
    <div className="min-h-screen flex items-center justify-center p-6 text-center">
      <div className="space-y-2">
        <h1 className="font-heading text-[22px] text-tinta">
          Página não encontrada
        </h1>
        <a href="/portal" className="text-sm underline">
          Ir para o início
        </a>
      </div>
    </div>
  );
}
