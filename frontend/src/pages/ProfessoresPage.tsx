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
import { useLecionamentos } from "@/features/lecionamentos/hooks";
import { ProfessorDeactivateDialog } from "@/features/professores/ProfessorDeactivateDialog";
import { ProfessorFormDialog } from "@/features/professores/ProfessorFormDialog";
import { useProfessores } from "@/features/professores/hooks";
import { usePermissoes } from "@/features/auth/usePermissoes";
import { useTurmas } from "@/features/turmas/hooks";
import type { Professor } from "@/types/api";

// CRUD de Professores. Lista com nome, turmas e disciplinas (badges
// agregadas a partir dos lecionamentos), status e dropdown ⋯.
// Criação envolve POSTs em sequência (Usuario + Professor + Lecionamentos)
// — ver ProfessorFormDialog.
export function ProfessoresPage() {
  const professoresQuery = useProfessores();
  const disciplinasQuery = useDisciplinas();
  const turmasQuery = useTurmas();
  // Carregamos todos os lecionamentos de uma vez e agrupamos por
  // professor no front — evita N+1 (um GET por professor).
  const lecionamentosQuery = useLecionamentos();
  const { podeModificarCadastros } = usePermissoes();

  const [busca, setBusca] = useState("");
  const [formOpen, setFormOpen] = useState(false);
  const [editando, setEditando] = useState<Professor | null>(null);
  const [desativando, setDesativando] = useState<Professor | null>(null);

  const disciplinasPorId = useMemo(() => {
    const m = new Map<number, string>();
    disciplinasQuery.data?.forEach((d) => m.set(d.id, d.nome));
    return m;
  }, [disciplinasQuery.data]);

  const turmasPorId = useMemo(() => {
    const m = new Map<number, string>();
    turmasQuery.data?.forEach((t) => m.set(t.id, t.nome));
    return m;
  }, [turmasQuery.data]);

  // Mapa professor → { turmas distintas, disciplinas distintas } —
  // usado pra montar os badges na listagem sem chamadas extras.
  const agregadoPorProfessor = useMemo(() => {
    const m = new Map<number, { turmas: number[]; disciplinas: number[] }>();
    for (const l of lecionamentosQuery.data ?? []) {
      const atual = m.get(l.professor) ?? { turmas: [], disciplinas: [] };
      if (!atual.turmas.includes(l.turma)) atual.turmas.push(l.turma);
      if (!atual.disciplinas.includes(l.disciplina)) {
        atual.disciplinas.push(l.disciplina);
      }
      m.set(l.professor, atual);
    }
    return m;
  }, [lecionamentosQuery.data]);

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
        {podeModificarCadastros && (
          <Button onClick={() => setFormOpen(true)}>Novo professor</Button>
        )}
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
              {/* Turmas e Disciplinas só a partir de md — em mobile cabe
                  só nome e ações. Detalhe via "Editar" mostra tudo. */}
              <TableHead className="hidden md:table-cell">Turmas</TableHead>
              <TableHead className="hidden lg:table-cell">Disciplinas</TableHead>
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
                    <Skeleton className="h-4 w-32" />
                  </TableCell>
                  <TableCell className="hidden lg:table-cell">
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
                  colSpan={5}
                  className="text-center text-destructive py-8"
                >
                  Erro ao carregar professores.
                </TableCell>
              </TableRow>
            ) : professoresFiltrados.length === 0 ? (
              <TableRow>
                <TableCell
                  colSpan={5}
                  className="text-center text-muted-foreground py-8"
                >
                  {busca
                    ? "Nenhum professor encontrado."
                    : "Nenhum professor cadastrado."}
                </TableCell>
              </TableRow>
            ) : (
              professoresFiltrados.map((p) => {
                const agg = agregadoPorProfessor.get(p.id) ?? {
                  turmas: [],
                  disciplinas: [],
                };
                return (
                <TableRow key={p.id}>
                  <TableCell>{p.nome_completo || "—"}</TableCell>
                  <TableCell className="hidden md:table-cell">
                    {agg.turmas.length === 0 ? (
                      <span className="text-xs text-muted-foreground">
                        Nenhuma
                      </span>
                    ) : (
                      <div className="flex flex-wrap gap-1">
                        {agg.turmas.map((tId) => (
                          <span
                            key={tId}
                            className="text-xs bg-blue-50 text-blue-700 dark:bg-blue-950 dark:text-blue-300 px-2 py-0.5 rounded"
                          >
                            {turmasPorId.get(tId) ?? `#${tId}`}
                          </span>
                        ))}
                      </div>
                    )}
                  </TableCell>
                  <TableCell className="hidden lg:table-cell">
                    {agg.disciplinas.length === 0 ? (
                      <span className="text-xs text-muted-foreground">
                        Nenhuma
                      </span>
                    ) : (
                      <div className="flex flex-wrap gap-1">
                        {agg.disciplinas.map((dId) => (
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
                    {podeModificarCadastros && (
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
                    )}
                  </TableCell>
                </TableRow>
                );
              })
            )}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}
