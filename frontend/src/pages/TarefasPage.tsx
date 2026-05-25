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
import { TarefaFormDialog } from "@/features/tarefas/TarefaFormDialog";
import { useTarefas } from "@/features/tarefas/hooks";
import { useTurmas } from "@/features/turmas/hooks";

export function TarefasPage() {
  const navigate = useNavigate();
  const tarefasQuery = useTarefas();
  const turmasQuery = useTurmas();
  const disciplinasQuery = useDisciplinas();
  const [busca, setBusca] = useState("");
  const [formOpen, setFormOpen] = useState(false);

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

  const tarefasFiltradas = useMemo(() => {
    if (!tarefasQuery.data) return [];
    const q = busca.trim().toLowerCase();
    if (!q) return tarefasQuery.data;
    return tarefasQuery.data.filter(
      (t) =>
        t.titulo.toLowerCase().includes(q) ||
        (turmasPorId.get(t.turma)?.toLowerCase() ?? "").includes(q) ||
        (disciplinasPorId.get(t.disciplina)?.toLowerCase() ?? "").includes(q),
    );
  }, [tarefasQuery.data, busca, turmasPorId, disciplinasPorId]);

  return (
    <div className="p-8 space-y-6">
      <header className="flex items-center justify-between">
        <h1 className="text-3xl font-semibold">Tarefas</h1>
        <Button onClick={() => setFormOpen(true)}>Nova tarefa</Button>
      </header>

      <TarefaFormDialog open={formOpen} onOpenChange={setFormOpen} />

      <Input
        placeholder="Buscar por título, turma ou disciplina..."
        value={busca}
        onChange={(e) => setBusca(e.target.value)}
        className="max-w-sm"
      />

      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Título</TableHead>
              <TableHead>Turma</TableHead>
              <TableHead>Disciplina</TableHead>
              <TableHead>Lançamento</TableHead>
              <TableHead>Prazo</TableHead>
              <TableHead>Vale nota</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {tarefasQuery.isLoading ? (
              Array.from({ length: 5 }).map((_, i) => (
                <TableRow key={i}>
                  {Array.from({ length: 6 }).map((_, j) => (
                    <TableCell key={j}>
                      <Skeleton className="h-4 w-24" />
                    </TableCell>
                  ))}
                </TableRow>
              ))
            ) : tarefasQuery.isError ? (
              <TableRow>
                <TableCell colSpan={6} className="text-center text-destructive py-8">
                  Erro ao carregar tarefas.
                </TableCell>
              </TableRow>
            ) : tarefasFiltradas.length === 0 ? (
              <TableRow>
                <TableCell
                  colSpan={6}
                  className="text-center text-muted-foreground py-8"
                >
                  {busca
                    ? "Nenhuma tarefa encontrada."
                    : "Nenhuma tarefa cadastrada."}
                </TableCell>
              </TableRow>
            ) : (
              tarefasFiltradas.map((t) => (
                <TableRow
                  key={t.id}
                  className="cursor-pointer"
                  onClick={() => navigate(`/tarefas/${t.id}`)}
                >
                  <TableCell>{t.titulo}</TableCell>
                  <TableCell>{turmasPorId.get(t.turma) ?? `#${t.turma}`}</TableCell>
                  <TableCell>
                    {disciplinasPorId.get(t.disciplina) ?? `#${t.disciplina}`}
                  </TableCell>
                  <TableCell className="tabular-nums whitespace-nowrap">
                    {new Date(t.data_lancamento + "T00:00:00").toLocaleDateString(
                      "pt-BR",
                    )}
                  </TableCell>
                  <TableCell className="tabular-nums whitespace-nowrap">
                    {t.prazo
                      ? new Date(t.prazo + "T00:00:00").toLocaleDateString("pt-BR")
                      : "—"}
                  </TableCell>
                  <TableCell>
                    {t.vale_nota ? (
                      <span className="text-xs text-blue-700 bg-blue-50 dark:bg-blue-950 dark:text-blue-300 px-2 py-0.5 rounded">
                        {t.nota_maxima ? `Vale ${t.nota_maxima}` : "Sim"}
                      </span>
                    ) : (
                      <span className="text-xs text-muted-foreground">Não</span>
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
