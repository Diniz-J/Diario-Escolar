import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import { Button } from "@/components/ui/button";
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
import { PlanoEnsinoCreateDialog } from "@/features/planos-ensino/PlanoEnsinoCreateDialog";
import { usePlanosEnsino } from "@/features/planos-ensino/hooks";
import { useTurmas } from "@/features/turmas/hooks";
import type { PlanoEnsino } from "@/types/api";

// Heurística de "está preenchido": considera ementa OU conteúdo
// programático com algum texto. Não precisa estar tudo cheio pra contar
// como preenchido.
function isPreenchido(p: PlanoEnsino): boolean {
  return p.ementa.trim().length > 0 || p.conteudo_programatico.trim().length > 0;
}

export function PlanosEnsinoPage() {
  const navigate = useNavigate();
  const planosQuery = usePlanosEnsino();
  const turmasQuery = useTurmas();
  const disciplinasQuery = useDisciplinas();
  const [busca, setBusca] = useState("");
  const [createOpen, setCreateOpen] = useState(false);

  const turmasPorId = useMemo(() => {
    const map = new Map<number, string>();
    turmasQuery.data?.forEach((t) => map.set(t.id, t.nome));
    return map;
  }, [turmasQuery.data]);

  const disciplinasPorId = useMemo(() => {
    const map = new Map<number, string>();
    disciplinasQuery.data?.forEach((d) => map.set(d.id, d.nome));
    return map;
  }, [disciplinasQuery.data]);

  const planosFiltrados = useMemo(() => {
    if (!planosQuery.data) return [];
    const q = busca.trim().toLowerCase();
    if (!q) return planosQuery.data;
    return planosQuery.data.filter((p) => {
      const turma = turmasPorId.get(p.turma)?.toLowerCase() ?? "";
      const disciplina = disciplinasPorId.get(p.disciplina)?.toLowerCase() ?? "";
      return (
        turma.includes(q) ||
        disciplina.includes(q) ||
        String(p.ano_letivo).includes(q)
      );
    });
  }, [planosQuery.data, busca, turmasPorId, disciplinasPorId]);

  return (
    <div className="p-4 md:p-8 space-y-6">
      <header className="flex items-center justify-between">
        <h1 className="text-2xl md:text-3xl font-semibold">Planos de ensino</h1>
        <Button onClick={() => setCreateOpen(true)}>Novo plano</Button>
      </header>

      <PlanoEnsinoCreateDialog
        open={createOpen}
        onOpenChange={setCreateOpen}
        onCreated={(id) => navigate(`/planos-ensino/${id}`)}
      />

      <Input
        placeholder="Buscar por turma, disciplina ou ano..."
        value={busca}
        onChange={(e) => setBusca(e.target.value)}
        className="max-w-sm"
      />

      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Turma</TableHead>
              <TableHead>Disciplina</TableHead>
              <TableHead>Ano</TableHead>
              <TableHead>Status</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {planosQuery.isLoading ? (
              Array.from({ length: 5 }).map((_, i) => (
                <TableRow key={i}>
                  {Array.from({ length: 4 }).map((_, j) => (
                    <TableCell key={j}>
                      <Skeleton className="h-4 w-24" />
                    </TableCell>
                  ))}
                </TableRow>
              ))
            ) : planosQuery.isError ? (
              <TableRow>
                <TableCell
                  colSpan={4}
                  className="text-center text-destructive py-8"
                >
                  Erro ao carregar planos.
                </TableCell>
              </TableRow>
            ) : planosFiltrados.length === 0 ? (
              <TableRow>
                <TableCell
                  colSpan={4}
                  className="text-center text-muted-foreground py-8"
                >
                  {busca
                    ? "Nenhum plano encontrado."
                    : "Nenhum plano de ensino cadastrado."}
                </TableCell>
              </TableRow>
            ) : (
              planosFiltrados.map((p) => (
                <TableRow
                  key={p.id}
                  className="cursor-pointer"
                  onClick={() => navigate(`/planos-ensino/${p.id}`)}
                >
                  <TableCell>
                    {turmasPorId.get(p.turma) ?? `#${p.turma}`}
                  </TableCell>
                  <TableCell>
                    {disciplinasPorId.get(p.disciplina) ?? `#${p.disciplina}`}
                  </TableCell>
                  <TableCell className="tabular-nums">{p.ano_letivo}</TableCell>
                  <TableCell>
                    {!p.ativo ? (
                      <span className="text-xs text-muted-foreground">
                        Inativo
                      </span>
                    ) : isPreenchido(p) ? (
                      <span className="text-xs text-green-700 bg-green-50 dark:bg-green-950 dark:text-green-300 px-2 py-0.5 rounded">
                        Preenchido
                      </span>
                    ) : (
                      <span className="text-xs text-amber-700 bg-amber-50 dark:bg-amber-950 dark:text-amber-300 px-2 py-0.5 rounded">
                        Em branco
                      </span>
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
