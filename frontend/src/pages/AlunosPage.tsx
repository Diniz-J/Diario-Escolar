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
import { AlunoDeleteDialog } from "@/features/alunos/AlunoDeleteDialog";
import { AlunoFormDialog } from "@/features/alunos/AlunoFormDialog";
import { useAlunos } from "@/features/alunos/hooks";
import { useTurmas } from "@/features/turmas/hooks";
import type { Aluno } from "@/types/api";

export function AlunosPage() {
  const navigate = useNavigate();
  const alunosQuery = useAlunos();
  const turmasQuery = useTurmas();
  const [busca, setBusca] = useState("");
  const [formOpen, setFormOpen] = useState(false);
  // Aluno em edição: null fecha o dialog; objeto abre em modo edição.
  const [editando, setEditando] = useState<Aluno | null>(null);
  const [excluindo, setExcluindo] = useState<Aluno | null>(null);

  const turmasPorId = useMemo(() => {
    const map = new Map<number, string>();
    turmasQuery.data?.forEach((t) => map.set(t.id, t.nome));
    return map;
  }, [turmasQuery.data]);

  const alunosFiltrados = useMemo(() => {
    if (!alunosQuery.data) return [];
    const q = busca.trim().toLowerCase();
    if (!q) return alunosQuery.data;
    return alunosQuery.data.filter(
      (a) =>
        a.nome_completo.toLowerCase().includes(q) ||
        a.matricula.toLowerCase().includes(q),
    );
  }, [alunosQuery.data, busca]);

  // Unifica criação e edição no mesmo dialog: `editando=null` + `formOpen`
  // = modo criar; `editando=aluno` = modo editar.
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
        <h1 className="text-2xl md:text-3xl font-semibold">Alunos</h1>
        <Button onClick={() => setFormOpen(true)}>Novo aluno</Button>
      </header>

      <AlunoFormDialog
        open={dialogAberto}
        onOpenChange={fecharDialog}
        aluno={editando}
      />
      <AlunoDeleteDialog
        aluno={excluindo}
        onOpenChange={(open) => !open && setExcluindo(null)}
      />

      <Input
        placeholder="Buscar por nome ou matrícula..."
        value={busca}
        onChange={(e) => setBusca(e.target.value)}
        className="max-w-sm"
      />

      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              {/* Em mobile mostramos só Nome + Turma + ⋯; o resto fica
                  no boletim (linha clicável). Matrícula volta em sm,
                  Status em md. */}
              <TableHead className="hidden sm:table-cell">Matrícula</TableHead>
              <TableHead>Nome completo</TableHead>
              <TableHead>Turma</TableHead>
              <TableHead className="hidden md:table-cell">Status</TableHead>
              <TableHead className="w-12"></TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {alunosQuery.isLoading ? (
              Array.from({ length: 5 }).map((_, i) => (
                <TableRow key={i}>
                  <TableCell>
                    <Skeleton className="h-4 w-24" />
                  </TableCell>
                  <TableCell>
                    <Skeleton className="h-4 w-48" />
                  </TableCell>
                  <TableCell>
                    <Skeleton className="h-4 w-32" />
                  </TableCell>
                  <TableCell>
                    <Skeleton className="h-4 w-16" />
                  </TableCell>
                  <TableCell></TableCell>
                </TableRow>
              ))
            ) : alunosQuery.isError ? (
              <TableRow>
                <TableCell
                  colSpan={5}
                  className="text-center text-destructive py-8"
                >
                  Erro ao carregar alunos.
                </TableCell>
              </TableRow>
            ) : alunosFiltrados.length === 0 ? (
              <TableRow>
                <TableCell
                  colSpan={5}
                  className="text-center text-muted-foreground py-8"
                >
                  {busca
                    ? "Nenhum aluno encontrado para essa busca."
                    : "Nenhum aluno cadastrado."}
                </TableCell>
              </TableRow>
            ) : (
              alunosFiltrados.map((aluno) => (
                <TableRow
                  key={aluno.id}
                  className="cursor-pointer"
                  onClick={() => navigate(`/boletim/${aluno.id}`)}
                >
                  <TableCell className="hidden sm:table-cell font-mono text-xs">
                    {aluno.matricula}
                  </TableCell>
                  <TableCell>{aluno.nome_completo}</TableCell>
                  <TableCell>
                    {turmasPorId.get(aluno.turma) ?? "—"}
                  </TableCell>
                  <TableCell className="hidden md:table-cell">
                    {aluno.ativo ? (
                      <span className="text-xs text-green-700 bg-green-50 dark:bg-green-950 dark:text-green-300 px-2 py-0.5 rounded">
                        Ativo
                      </span>
                    ) : (
                      <span className="text-xs text-muted-foreground">
                        Inativo
                      </span>
                    )}
                  </TableCell>
                  <TableCell
                    // Bloqueia bubble-up: clicar no menu de ações não
                    // dispara a navegação pro boletim.
                    onClick={(e) => e.stopPropagation()}
                  >
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button variant="ghost" size="icon-sm">
                          ⋯
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end">
                        <DropdownMenuItem onClick={() => setEditando(aluno)}>
                          Editar
                        </DropdownMenuItem>
                        <DropdownMenuItem
                          onClick={() => setExcluindo(aluno)}
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
