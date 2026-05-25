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
import { DisciplinaDeleteDialog } from "@/features/disciplinas/DisciplinaDeleteDialog";
import { DisciplinaFormDialog } from "@/features/disciplinas/DisciplinaFormDialog";
import { useDisciplinas } from "@/features/disciplinas/hooks";
import type { Disciplina } from "@/types/api";

export function DisciplinasPage() {
  const disciplinasQuery = useDisciplinas();
  const [busca, setBusca] = useState("");
  const [formOpen, setFormOpen] = useState(false);
  const [editando, setEditando] = useState<Disciplina | null>(null);
  const [excluindo, setExcluindo] = useState<Disciplina | null>(null);

  const disciplinasFiltradas = useMemo(() => {
    if (!disciplinasQuery.data) return [];
    const q = busca.trim().toLowerCase();
    if (!q) return disciplinasQuery.data;
    return disciplinasQuery.data.filter((d) =>
      d.nome.toLowerCase().includes(q),
    );
  }, [disciplinasQuery.data, busca]);

  const dialogAberto = formOpen || editando !== null;
  function fecharDialog(open: boolean) {
    if (!open) {
      setFormOpen(false);
      setEditando(null);
    }
  }

  return (
    <div className="p-8 space-y-6">
      <header className="flex items-center justify-between">
        <h1 className="text-3xl font-semibold">Disciplinas</h1>
        <Button onClick={() => setFormOpen(true)}>Nova disciplina</Button>
      </header>

      <DisciplinaFormDialog
        open={dialogAberto}
        onOpenChange={fecharDialog}
        disciplina={editando}
      />
      <DisciplinaDeleteDialog
        disciplina={excluindo}
        onOpenChange={(open) => !open && setExcluindo(null)}
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
              <TableHead className="w-12"></TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {disciplinasQuery.isLoading ? (
              Array.from({ length: 4 }).map((_, i) => (
                <TableRow key={i}>
                  <TableCell>
                    <Skeleton className="h-4 w-40" />
                  </TableCell>
                  <TableCell></TableCell>
                </TableRow>
              ))
            ) : disciplinasQuery.isError ? (
              <TableRow>
                <TableCell
                  colSpan={2}
                  className="text-center text-destructive py-8"
                >
                  Erro ao carregar disciplinas.
                </TableCell>
              </TableRow>
            ) : disciplinasFiltradas.length === 0 ? (
              <TableRow>
                <TableCell
                  colSpan={2}
                  className="text-center text-muted-foreground py-8"
                >
                  {busca
                    ? "Nenhuma disciplina encontrada."
                    : "Nenhuma disciplina cadastrada."}
                </TableCell>
              </TableRow>
            ) : (
              disciplinasFiltradas.map((d) => (
                <TableRow key={d.id}>
                  <TableCell>{d.nome}</TableCell>
                  <TableCell>
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button variant="ghost" size="icon-sm">
                          ⋯
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end">
                        <DropdownMenuItem onClick={() => setEditando(d)}>
                          Editar
                        </DropdownMenuItem>
                        <DropdownMenuItem
                          onClick={() => setExcluindo(d)}
                          className="text-destructive focus:text-destructive"
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
