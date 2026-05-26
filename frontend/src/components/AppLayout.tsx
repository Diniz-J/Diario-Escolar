import { Menu as MenuIcon } from "lucide-react";
import { useEffect, useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";

import { Button } from "@/components/ui/button";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";
import { useAuth } from "@/features/auth/useAuth";
import { cn } from "@/lib/utils";

// Layout para todas as rotas autenticadas.
//
// Desktop (>=768px): sidebar fixa à esquerda como antes.
// Mobile (<768px): sidebar some, vira drawer (Sheet) acionado por um
// botão hamburguer num header superior. O drawer fecha automaticamente
// quando o usuário escolhe uma rota — evita ficar aberto sobre o
// conteúdo após a navegação.

const NAV_ITEMS = [
  { to: "/dashboard", label: "Dashboard" },
  { to: "/alunos", label: "Alunos" },
  { to: "/turmas", label: "Turmas" },
  { to: "/disciplinas", label: "Disciplinas" },
  { to: "/professores", label: "Professores" },
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

interface SidebarBodyProps {
  perfilLabel: string;
  onNavigate?: () => void;
  onLogout: () => void;
}

// Conteúdo da sidebar — extraído pra ser reaproveitado entre o painel
// fixo do desktop e o Sheet do mobile.
function SidebarBody({ perfilLabel, onNavigate, onLogout }: SidebarBodyProps) {
  return (
    <div className="flex flex-col h-full">
      <div className="p-4 border-b">
        <p className="text-sm font-semibold">Diário Escolar</p>
        <p className="text-xs text-muted-foreground mt-0.5">{perfilLabel}</p>
      </div>

      <nav className="flex-1 p-2 space-y-1 overflow-y-auto">
        {NAV_ITEMS.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            onClick={onNavigate}
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
          onClick={onLogout}
          className="w-full justify-start"
        >
          Sair
        </Button>
      </div>
    </div>
  );
}

export function AppLayout() {
  const { user, logout } = useAuth();
  const location = useLocation();
  const [drawerOpen, setDrawerOpen] = useState(false);

  const perfilLabel = user?.perfil
    ? PERFIL_LABEL[user.perfil] ?? user.perfil
    : "—";

  // Fecha o drawer toda vez que a rota muda — assim clicar num item na
  // navegação mobile leva pra página e some sozinho.
  useEffect(() => {
    setDrawerOpen(false);
  }, [location.pathname]);

  return (
    <div className="min-h-screen flex flex-col md:flex-row bg-background">
      {/* Header mobile — só aparece abaixo de md, com hamburguer. */}
      <header className="md:hidden flex items-center gap-3 px-3 h-12 border-b bg-background sticky top-0 z-30">
        <Sheet open={drawerOpen} onOpenChange={setDrawerOpen}>
          <SheetTrigger asChild>
            <Button variant="ghost" size="icon-sm" aria-label="Abrir menu">
              <MenuIcon className="size-5" />
            </Button>
          </SheetTrigger>
          <SheetContent side="left" className="w-64 max-w-[80vw] p-0">
            <SheetHeader className="sr-only">
              <SheetTitle>Menu de navegação</SheetTitle>
            </SheetHeader>
            <SidebarBody
              perfilLabel={perfilLabel}
              onNavigate={() => setDrawerOpen(false)}
              onLogout={logout}
            />
          </SheetContent>
        </Sheet>
        <span className="text-sm font-semibold">Diário Escolar</span>
      </header>

      {/* Sidebar desktop — só a partir de md. */}
      <aside className="hidden md:flex w-56 border-r flex-col shrink-0">
        <SidebarBody perfilLabel={perfilLabel} onLogout={logout} />
      </aside>

      <main className="flex-1 overflow-auto min-w-0">
        <Outlet />
      </main>
    </div>
  );
}
