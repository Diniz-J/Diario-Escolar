import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

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
import { useAlunos } from "@/features/alunos/hooks";
import { TurmaDeleteDialog } from "@/features/turmas/TurmaDeleteDialog";
import { TurmaFormDialog } from "@/features/turmas/TurmaFormDialog";
import { useTurmas } from "@/features/turmas/hooks";
import type { Turma } from "@/types/api";

export function TurmasPage() {
  const navigate = useNavigate();
  const turmasQuery = useTurmas();
  // Carregamos todos os alunos uma vez e contamos localmente — evita
  // N+1 requests (um por turma). TanStack Query compartilha esse cache
  // com a página de Alunos, então não há custo adicional na navegação.
  const alunosQuery = useAlunos();
  const [busca, setBusca] = useState("");
  const [formOpen, setFormOpen] = useState(false);
  const [editando, setEditando] = useState<Turma | null>(null);
  const [excluindo, setExcluindo] = useState<Turma | null>(null);

  const alunosPorTurma = useMemo(() => {
    const map = new Map<number, number>();
    alunosQuery.data?.forEach((a) => {
      map.set(a.turma, (map.get(a.turma) ?? 0) + 1);
    });
    return map;
  }, [alunosQuery.data]);

  const turmasFiltradas = useMemo(() => {
    if (!turmasQuery.data) return [];
    const q = busca.trim().toLowerCase();
    if (!q) return turmasQuery.data;
    return turmasQuery.data.filter(
      (t) =>
        t.nome.toLowerCase().includes(q) ||
        String(t.ano_letivo).includes(q),
    );
  }, [turmasQuery.data, busca]);

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
        <h1 className="text-2xl md:text-3xl font-semibold">Turmas</h1>
        <Button onClick={() => setFormOpen(true)}>Nova turma</Button>
      </header>

      <TurmaFormDialog
        open={dialogAberto}
        onOpenChange={fecharDialog}
        turma={editando}
      />
      <TurmaDeleteDialog
        turma={excluindo}
        onOpenChange={(open) => !open && setExcluindo(null)}
      />

      <Input
        placeholder="Buscar por nome ou ano letivo..."
        value={busca}
        onChange={(e) => setBusca(e.target.value)}
        className="max-w-sm"
      />

      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Nome</TableHead>
              <TableHead>Turno</TableHead>
              <TableHead>Ano letivo</TableHead>
              <TableHead>Alunos</TableHead>
              <TableHead className="w-12"></TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {turmasQuery.isLoading ? (
              Array.from({ length: 5 }).map((_, i) => (
                <TableRow key={i}>
                  <TableCell>
                    <Skeleton className="h-4 w-32" />
                  </TableCell>
                  <TableCell>
                    <Skeleton className="h-4 w-20" />
                  </TableCell>
                  <TableCell>
                    <Skeleton className="h-4 w-14" />
                  </TableCell>
                  <TableCell>
                    <Skeleton className="h-4 w-10" />
                  </TableCell>
                  <TableCell></TableCell>
                </TableRow>
              ))
            ) : turmasQuery.isError ? (
              <TableRow>
                <TableCell
                  colSpan={5}
                  className="text-center text-destructive py-8"
                >
                  Erro ao carregar turmas.
                </TableCell>
              </TableRow>
            ) : turmasFiltradas.length === 0 ? (
              <TableRow>
                <TableCell
                  colSpan={5}
                  className="text-center text-muted-foreground py-8"
                >
                  {busca
                    ? "Nenhuma turma encontrada para essa busca."
                    : "Nenhuma turma cadastrada."}
                </TableCell>
              </TableRow>
            ) : (
              turmasFiltradas.map((turma) => (
                <TableRow
                  key={turma.id}
                  className="cursor-pointer"
                  onClick={() => navigate(`/turmas/${turma.id}`)}
                >
                  <TableCell>{turma.nome}</TableCell>
                  <TableCell>{turma.turno_display}</TableCell>
                  <TableCell>{turma.ano_letivo}</TableCell>
                  <TableCell className="tabular-nums">
                    {alunosQuery.isLoading ? (
                      <Skeleton className="h-4 w-8" />
                    ) : (
                      alunosPorTurma.get(turma.id) ?? 0
                    )}
                  </TableCell>
                  <TableCell
                    // Bloqueia bubble-up: clicar no menu de ações não
                    // dispara a navegação da linha inteira.
                    onClick={(e) => e.stopPropagation()}
                  >
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button variant="ghost" size="icon-sm">
                          ⋯
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end">
                        <DropdownMenuItem onClick={() => setEditando(turma)}>
                          Editar
                        </DropdownMenuItem>
                        <DropdownMenuItem
                          onClick={() => setExcluindo(turma)}
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
