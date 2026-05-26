import { useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useDisciplinas } from "@/features/disciplinas/hooks";
import { ProfessorDeactivateDialog } from "@/features/professores/ProfessorDeactivateDialog";
import { ProfessorFormDialog } from "@/features/professores/ProfessorFormDialog";
import { useProfessores } from "@/features/professores/hooks";
import type { Professor } from "@/types/api";

// CRUD de Professores. Lista com nome, disciplinas (badges), status,
// e dropdown ⋯ para editar/desativar. Criação envolve dois POSTs em
// sequência (Usuario + Professor) — ver ProfessorFormDialog.
export function ProfessoresPage() {
  const professoresQuery = useProfessores();
  const disciplinasQuery = useDisciplinas();

  const [busca, setBusca] = useState("");
  const [formOpen, setFormOpen] = useState(false);
  const [editando, setEditando] = useState<Professor | null>(null);
  const [desativando, setDesativando] = useState<Professor | null>(null);

  const disciplinasPorId = useMemo(() => {
    const m = new Map<number, string>();
    disciplinasQuery.data?.forEach((d) => m.set(d.id, d.nome));
    return m;
  }, [disciplinasQuery.data]);

  const professoresFiltrados = useMemo(() => {
    if (!professoresQuery.data) return [];
    const q = busca.trim().toLowerCase();
    if (!q) return professoresQuery.data;
    return professoresQuery.data.filter((p) =>
      p.nome_completo.toLowerCase().includes(q),
    );
  }, [professoresQuery.data, busca]);

  const dialogAberto = formOpen || editando !== null;
  function fecharDialog(open: boolean) {
    if (!open) {
      setFormOpen(false);
      setEditando(null);
    }
  }

  return (
    <div className="p-4 md:p-8 space-y-6">
      <header className="flex items-center justify-between">
        <h1 className="text-2xl md:text-3xl font-semibold">Professores</h1>
        <Button onClick={() => setFormOpen(true)}>Novo professor</Button>
      </header>

      <ProfessorFormDialog
        open={dialogAberto}
        onOpenChange={fecharDialog}
        professor={editando}
      />
      <ProfessorDeactivateDialog
        professor={desativando}
        onOpenChange={(open) => !open && setDesativando(null)}
      />

      <Input
        placeholder="Buscar por nome..."
        value={busca}
        onChange={(e) => setBusca(e.target.value)}
        className="max-w-sm"
      />

      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Nome</TableHead>
              {/* Disciplinas só a partir de md — em mobile cabe só nome
                  e ações. Edita pra ver/mudar disciplinas. */}
              <TableHead className="hidden md:table-cell">Disciplinas</TableHead>
              <TableHead className="hidden sm:table-cell">Status</TableHead>
              <TableHead className="w-12"></TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {professoresQuery.isLoading ? (
              Array.from({ length: 4 }).map((_, i) => (
                <TableRow key={i}>
                  <TableCell>
                    <Skeleton className="h-4 w-40" />
                  </TableCell>
                  <TableCell className="hidden md:table-cell">
                    <Skeleton className="h-4 w-48" />
                  </TableCell>
                  <TableCell className="hidden sm:table-cell">
                    <Skeleton className="h-4 w-16" />
                  </TableCell>
                  <TableCell></TableCell>
                </TableRow>
              ))
            ) : professoresQuery.isError ? (
              <TableRow>
                <TableCell
                  colSpan={4}
                  className="text-center text-destructive py-8"
                >
                  Erro ao carregar professores.
                </TableCell>
              </TableRow>
            ) : professoresFiltrados.length === 0 ? (
              <TableRow>
                <TableCell
                  colSpan={4}
                  className="text-center text-muted-foreground py-8"
                >
                  {busca
                    ? "Nenhum professor encontrado."
                    : "Nenhum professor cadastrado."}
                </TableCell>
              </TableRow>
            ) : (
              professoresFiltrados.map((p) => (
                <TableRow key={p.id}>
                  <TableCell>{p.nome_completo || "—"}</TableCell>
                  <TableCell className="hidden md:table-cell">
                    {p.disciplinas.length === 0 ? (
                      <span className="text-xs text-muted-foreground">
                        Nenhuma
                      </span>
                    ) : (
                      <div className="flex flex-wrap gap-1">
                        {p.disciplinas.map((dId) => (
                          <span
                            key={dId}
                            className="text-xs bg-muted px-2 py-0.5 rounded"
                          >
                            {disciplinasPorId.get(dId) ?? `#${dId}`}
                          </span>
                        ))}
                      </div>
                    )}
                  </TableCell>
                  <TableCell className="hidden sm:table-cell">
                    {p.ativo ? (
                      <span className="text-xs text-green-700 bg-green-50 dark:bg-green-950 dark:text-green-300 px-2 py-0.5 rounded">
                        Ativo
                      </span>
                    ) : (
                      <span className="text-xs text-muted-foreground">
                        Inativo
                      </span>
                    )}
                  </TableCell>
                  <TableCell>
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button variant="ghost" size="icon-sm">
                          ⋯
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end">
                        <DropdownMenuItem onClick={() => setEditando(p)}>
                          Editar
                        </DropdownMenuItem>
                        <DropdownMenuItem
                          onClick={() => setDesativando(p)}
                          className="text-destructive focus:text-destructive"
                          disabled={!p.ativo}
                        >
                          Excluir
                        </DropdownMenuItem>
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}
