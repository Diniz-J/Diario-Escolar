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
import { usePermissoes } from "@/features/auth/usePermissoes";
import { TurmaDeleteDialog } from "@/features/turmas/TurmaDeleteDialog";
import { TurmaFormDialog } from "@/features/turmas/TurmaFormDialog";
import { useTurmas } from "@/features/turmas/hooks";
import type { Turma } from "@/types/api";

export function TurmasPage() {
  const navigate = useNavigate();
  const turmasQuery = useTurmas();
  // Carregamos os alunos ativos uma vez e contamos localmente — evita
  // N+1 requests (um por turma). Inativos (soft delete) não entram na
  // contagem porque o número reflete a operação atual, não o histórico
  // cumulativo. TanStack Query compartilha esse cache com o estado
  // padrão da página de Alunos (que também usa `ativo: true`).
  const alunosQuery = useAlunos({ ativo: true });
  const { podeModificarCadastros } = usePermissoes();
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
      <header className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
        <div className="space-y-3">
          <h1 className="font-heading text-[28px] md:text-[34px] tracking-tight text-tinta leading-[1.15]">
            Turmas
          </h1>
          <div className="h-px w-10 bg-ferrugem" />
        </div>
        {podeModificarCadastros && (
          <Button onClick={() => setFormOpen(true)}>Nova turma</Button>
        )}
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

      <div className="rounded-lg border border-border bg-paper overflow-hidden">
        <Table>
          <TableHeader>
            <TableRow>
              {/* Headers em eyebrow mono — padrão do DESIGN.md §7.1.
                  Turno e Ano letivo só em telas maiores. O nome da turma
                  geralmente já carrega o ano ("1º Ano A"); detalhe da
                  turma mostra tudo. */}
              <TableHead className="text-[11px] uppercase tracking-[0.15em] text-sepia font-normal">
                Nome
              </TableHead>
              <TableHead className="hidden md:table-cell text-[11px] uppercase tracking-[0.15em] text-sepia font-normal">
                Turno
              </TableHead>
              <TableHead className="hidden sm:table-cell text-[11px] uppercase tracking-[0.15em] text-sepia font-normal">
                Ano letivo
              </TableHead>
              <TableHead className="text-[11px] uppercase tracking-[0.15em] text-sepia font-normal">
                Alunos
              </TableHead>
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
                  <TableCell className="hidden md:table-cell">
                    {turma.turno_display}
                  </TableCell>
                  <TableCell className="hidden sm:table-cell">
                    {turma.ano_letivo}
                  </TableCell>
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
                    {podeModificarCadastros && (
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
                    )}
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
