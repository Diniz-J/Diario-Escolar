import { NavLink, Outlet } from "react-router-dom";

import { Button } from "@/components/ui/button";
import { useAuth } from "@/features/auth/useAuth";
import { cn } from "@/lib/utils";

// Layout para todas as rotas autenticadas: sidebar fixa à esquerda
// + área principal onde a rota filha é renderizada via <Outlet />.
//
// A sidebar fica visível durante toda a navegação autenticada — clicar
// em "Alunos" troca só o conteúdo da área principal, sem piscar.
//
// `NavLink` é como `Link`, mas expõe `isActive` quando a URL atual casa
// com o `to`. Usamos para destacar o item ativo na sidebar.

const NAV_ITEMS = [
  { to: "/dashboard", label: "Dashboard" },
  { to: "/alunos", label: "Alunos" },
  { to: "/turmas", label: "Turmas" },
  { to: "/disciplinas", label: "Disciplinas" },
  { to: "/planos-ensino", label: "Planos de ensino" },
  { to: "/ocorrencias", label: "Ocorrências" },
  { to: "/presenca", label: "Presença" },
  { to: "/tarefas", label: "Tarefas" },
];

const PERFIL_LABEL: Record<string, string> = {
  admin: "Administrador",
  diretor: "Diretor",
  professor: "Professor",
  secretaria: "Secretaria",
  inspetor: "Inspetor",
};

export function AppLayout() {
  const { user, logout } = useAuth();
  const perfilLabel = user?.perfil
    ? PERFIL_LABEL[user.perfil] ?? user.perfil
    : "—";

  return (
    <div className="min-h-screen flex bg-background">
      <aside className="w-56 border-r flex flex-col">
        <div className="p-4 border-b">
          <p className="text-sm font-semibold">Diário Escolar</p>
          <p className="text-xs text-muted-foreground mt-0.5">{perfilLabel}</p>
        </div>

        <nav className="flex-1 p-2 space-y-1">
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                cn(
                  "block px-3 py-2 text-sm rounded-md transition-colors",
                  isActive
                    ? "bg-muted text-foreground font-medium"
                    : "text-muted-foreground hover:bg-muted hover:text-foreground",
                )
              }
            >
              {item.label}
            </NavLink>
          ))}
        </nav>

        <div className="p-2 border-t">
          <Button
            variant="ghost"
            size="sm"
            onClick={logout}
            className="w-full justify-start"
          >
            Sair
          </Button>
        </div>
      </aside>

      <main className="flex-1 overflow-auto">
        <Outlet />
      </main>
    </div>
  );
}
