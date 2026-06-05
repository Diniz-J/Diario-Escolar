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
import { usePermissoes } from "@/features/auth/usePermissoes";
import { cn } from "@/lib/utils";

// Layout para todas as rotas autenticadas — paleta olive/linho (Diário
// Diniz).
//
// Desktop (>=768px): sidebar fixa à esquerda, fundo olive-dark, texto
// creme. Conteúdo principal em fundo linho.
//
// Mobile (<768px): sidebar some, vira drawer (Sheet) acionado por um
// botão hamburguer num header superior também olive-dark. O drawer
// fecha automaticamente quando o usuário escolhe uma rota — evita
// ficar aberto sobre o conteúdo após a navegação.

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
  podeImportar: boolean;
  podeConfigurarEscola: boolean;
}

// Itens da seção "Configuração" — visíveis pra admin/diretor/secretaria
// (perfis que configuram a régua da escola). Crescem aqui conforme novos
// itens de config vão sendo criados (futuro: regras de boletim, política
// de notas, etc.).
const CONFIG_ITEMS = [
  { to: "/configuracao/periodos", label: "Períodos avaliativos" },
];

// Conteúdo da sidebar — extraído pra ser reaproveitado entre o painel
// fixo do desktop e o Sheet do mobile.
//
// A sidebar inverte a paleta: fundo escuro (olive-dark) + texto creme.
// Cria contraste forte com o conteúdo principal em linho, hierarquia
// visual clara e dá identidade à navegação.
function SidebarBody({
  perfilLabel,
  onNavigate,
  onLogout,
  podeImportar,
  podeConfigurarEscola,
}: SidebarBodyProps) {
  return (
    <div className="flex flex-col h-full bg-sidebar text-sidebar-foreground">
      {/* Marca — placeholder até definirmos o logo real. Por ora, só
          o nome em Fraunces com um pingo ferrugem discreto à esquerda
          servindo de marcador visual. Trocar quando o logo chegar. */}
      <div className="px-5 pt-6 pb-5">
        <div className="flex items-baseline gap-2">
          <span
            className="inline-block w-1.5 h-1.5 rounded-full translate-y-[-2px]"
            style={{ background: "var(--ferrugem)" }}
          />
          <span className="font-heading text-[18px] tracking-tight">
            Diário Diniz
          </span>
        </div>
        <p className="mt-3 text-[10px] uppercase tracking-[0.2em] opacity-60">
          {perfilLabel}
        </p>
      </div>

      <nav className="flex-1 px-2 py-2 space-y-0.5 overflow-y-auto">
        {NAV_ITEMS.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            onClick={onNavigate}
            className={({ isActive }) =>
              cn(
                // Base: texto creme com opacidade reduzida; padding
                // generoso; transição suave. Barra esquerda é o
                // espaço pra `border-l-2` aparecer no ativo sem
                // empurrar o texto (a base aplica `border-l-2 border-transparent`).
                "relative block pl-4 pr-3 py-2 text-sm rounded-md transition-colors border-l-2 border-transparent",
                isActive
                  ? "border-l-ferrugem font-medium text-creme bg-white/[0.04]"
                  : "text-creme/75 hover:text-creme hover:bg-white/[0.04]",
              )
            }
          >
            {item.label}
          </NavLink>
        ))}
        {podeImportar && (
          <NavLink
            to="/import"
            onClick={onNavigate}
            className={({ isActive }) =>
              cn(
                "relative block pl-4 pr-3 py-2 text-sm rounded-md transition-colors border-l-2 border-transparent mt-3",
                isActive
                  ? "border-l-ferrugem font-medium text-creme bg-white/[0.04]"
                  : "text-creme/75 hover:text-creme hover:bg-white/[0.04]",
              )
            }
          >
            Importar em lote
          </NavLink>
        )}

        {/* Seção "Configuração" — admin/diretor/secretaria. Cabeçalho
            sutil em uppercase pra separar visualmente da navegação
            operacional acima sem precisar de divisor harsh. */}
        {podeConfigurarEscola && CONFIG_ITEMS.length > 0 && (
          <>
            <p className="px-4 pt-5 pb-1 text-[10px] uppercase tracking-[0.2em] text-creme/40">
              Configuração
            </p>
            {CONFIG_ITEMS.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                onClick={onNavigate}
                className={({ isActive }) =>
                  cn(
                    "relative block pl-4 pr-3 py-2 text-sm rounded-md transition-colors border-l-2 border-transparent",
                    isActive
                      ? "border-l-ferrugem font-medium text-creme bg-white/[0.04]"
                      : "text-creme/75 hover:text-creme hover:bg-white/[0.04]",
                  )
                }
              >
                {item.label}
              </NavLink>
            ))}
          </>
        )}
      </nav>

      {/* Filete ferrugem fininho + minha conta + logout + versão. */}
      <div className="px-5 pb-5 pt-3">
        <div
          className="h-px w-8 mb-4"
          style={{ background: "var(--ferrugem)" }}
        />
        {podeImportar && (
          <NavLink
            to="/import"
            onClick={onNavigate}
            className="block text-sm text-creme/75 hover:text-creme transition-colors mb-2"
          >
            Importar e exportar
          </NavLink>
        )}
        <NavLink
          to="/conta/senha"
          onClick={onNavigate}
          className="block text-sm text-creme/75 hover:text-creme transition-colors mb-2"
        >
          Trocar minha senha
        </NavLink>
        <button
          type="button"
          onClick={onLogout}
          className="text-sm text-creme/75 hover:text-creme transition-colors"
        >
          Sair
        </button>
        <p className="mt-3 text-[10px] uppercase tracking-[0.18em] opacity-40">
          v1.0
        </p>
      </div>
    </div>
  );
}

export function AppLayout() {
  const { user, logout } = useAuth();
  const { podeImportar, podeModificarCadastros } = usePermissoes();
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
    <div className="min-h-screen flex flex-col md:flex-row bg-background text-foreground">
      {/* Header mobile — só aparece abaixo de md. Mesma paleta olive-dark
          da sidebar pra dar continuidade visual ao abrir o drawer. */}
      <header className="md:hidden flex items-center gap-3 px-3 h-12 bg-sidebar text-sidebar-foreground sticky top-0 z-30">
        <Sheet open={drawerOpen} onOpenChange={setDrawerOpen}>
          <SheetTrigger asChild>
            <Button
              variant="ghost"
              size="icon-sm"
              aria-label="Abrir menu"
              className="text-creme hover:bg-white/10 hover:text-creme"
            >
              <MenuIcon className="size-5" />
            </Button>
          </SheetTrigger>
          <SheetContent
            side="left"
            className="w-64 max-w-[80vw] p-0 bg-sidebar border-r-0"
          >
            <SheetHeader className="sr-only">
              <SheetTitle>Menu de navegação</SheetTitle>
            </SheetHeader>
            <SidebarBody
              perfilLabel={perfilLabel}
              onNavigate={() => setDrawerOpen(false)}
              onLogout={logout}
              podeImportar={podeImportar}
              podeConfigurarEscola={podeModificarCadastros}
            />
          </SheetContent>
        </Sheet>
        <span className="font-heading text-[15px] tracking-tight">
          Diário Diniz
        </span>
      </header>

      {/* Sidebar desktop — só a partir de md. Largura levemente maior
          (60 vs 56) pra acomodar o padding mais respirado da nova
          identidade. */}
      <aside className="hidden md:flex w-60 flex-col shrink-0">
        <SidebarBody
          perfilLabel={perfilLabel}
          onLogout={logout}
          podeImportar={podeImportar}
          podeConfigurarEscola={podeModificarCadastros}
        />
      </aside>

      <main className="flex-1 overflow-auto min-w-0">
        <Outlet />
      </main>
    </div>
  );
}
