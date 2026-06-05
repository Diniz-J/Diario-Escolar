import { useMemo, useState } from "react";

import { ExportarMenu } from "@/components/ExportarMenu";
import { Pagination } from "@/components/Pagination";
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
import { usePermissoes } from "@/features/auth/usePermissoes";
import { DisciplinaDeleteDialog } from "@/features/disciplinas/DisciplinaDeleteDialog";
import { DisciplinaFormDialog } from "@/features/disciplinas/DisciplinaFormDialog";
import { useDisciplinasPaginated } from "@/features/disciplinas/hooks";
import type { Disciplina } from "@/types/api";

const PAGE_SIZE = 20;

export function DisciplinasPage() {
  const [page, setPage] = useState(1);
  const disciplinasQuery = useDisciplinasPaginated({
    page,
    page_size: PAGE_SIZE,
  });
  const { podeModificarCadastros } = usePermissoes();
  const [busca, setBusca] = useState("");
  const [formOpen, setFormOpen] = useState(false);
  const [editando, setEditando] = useState<Disciplina | null>(null);
  const [excluindo, setExcluindo] = useState<Disciplina | null>(null);

  const disciplinasFiltradas = useMemo(() => {
    const resultados = disciplinasQuery.data?.results ?? [];
    const q = busca.trim().toLowerCase();
    if (!q) return resultados;
    return resultados.filter((d) => d.nome.toLowerCase().includes(q));
  }, [disciplinasQuery.data, busca]);

  const totalCount = disciplinasQuery.data?.count ?? 0;
  const totalPages = Math.max(1, Math.ceil(totalCount / PAGE_SIZE));

  const dialogAberto = formOpen || editando !== null;
  function fecharDialog(open: boolean) {
    if (!open) {
      setFormOpen(false);
      setEditando(null);
    }
  }

  return (
    <div className="p-4 md:p-8 space-y-6">
      <header className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
        <div className="space-y-3">
          <h1 className="font-heading text-[28px] md:text-[34px] tracking-tight text-tinta leading-[1.15]">
            Disciplinas
          </h1>
          <div className="h-px w-10 bg-ferrugem" />
        </div>
        <div className="flex items-center gap-2">
          <ExportarMenu entidade="disciplinas" />
          {podeModificarCadastros && (
            <Button onClick={() => setFormOpen(true)}>Nova disciplina</Button>
          )}
        </div>
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

      <div className="rounded-lg border border-border bg-paper overflow-hidden">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="text-[11px] uppercase tracking-[0.15em] text-sepia font-normal">
                Nome
              </TableHead>
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
                    {podeModificarCadastros && (
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
                    )}
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>

      <Pagination
        page={page}
        totalPages={totalPages}
        onPageChange={setPage}
        totalLabel={
          totalCount > 0 ? `${totalCount} disciplinas no total` : undefined
        }
      />
    </div>
  );
}
