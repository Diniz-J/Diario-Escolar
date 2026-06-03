import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import { Pagination } from "@/components/Pagination";
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
import { useTarefasPaginated } from "@/features/tarefas/hooks";
import { useTurmas } from "@/features/turmas/hooks";

const PAGE_SIZE = 20;

export function TarefasPage() {
  const navigate = useNavigate();
  const [page, setPage] = useState(1);
  const tarefasQuery = useTarefasPaginated({}, { page, page_size: PAGE_SIZE });
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
    const resultados = tarefasQuery.data?.results ?? [];
    const q = busca.trim().toLowerCase();
    if (!q) return resultados;
    return resultados.filter(
      (t) =>
        t.titulo.toLowerCase().includes(q) ||
        (turmasPorId.get(t.turma)?.toLowerCase() ?? "").includes(q) ||
        (disciplinasPorId.get(t.disciplina)?.toLowerCase() ?? "").includes(q),
    );
  }, [tarefasQuery.data, busca, turmasPorId, disciplinasPorId]);

  const totalCount = tarefasQuery.data?.count ?? 0;
  const totalPages = Math.max(1, Math.ceil(totalCount / PAGE_SIZE));

  return (
    <div className="p-4 md:p-8 space-y-6">
      <header className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
        <div className="space-y-3">
          <h1 className="font-heading text-[28px] md:text-[34px] tracking-tight text-tinta leading-[1.15]">
            Tarefas
          </h1>
          <div className="h-px w-10 bg-ferrugem" />
        </div>
        <Button onClick={() => setFormOpen(true)}>Nova tarefa</Button>
      </header>

      <TarefaFormDialog open={formOpen} onOpenChange={setFormOpen} />

      <Input
        placeholder="Buscar por título, turma ou disciplina..."
        value={busca}
        onChange={(e) => setBusca(e.target.value)}
        className="max-w-sm"
      />

      <div className="rounded-lg border border-border bg-paper overflow-hidden">
        <Table>
          <TableHeader>
            <TableRow>
              {/* Headers em eyebrow mono — padrão do DESIGN.md §7.1.
                  Em mobile escondemos colunas pra evitar o scroll horizontal
                  grosso do Windows. As infos completas continuam acessíveis
                  ao clicar na linha (rota de detalhe). */}
              <TableHead className="text-[11px] uppercase tracking-[0.15em] text-sepia font-normal">
                Título
              </TableHead>
              <TableHead className="text-[11px] uppercase tracking-[0.15em] text-sepia font-normal">
                Turma
              </TableHead>
              <TableHead className="hidden md:table-cell text-[11px] uppercase tracking-[0.15em] text-sepia font-normal">
                Disciplina
              </TableHead>
              <TableHead className="hidden md:table-cell text-[11px] uppercase tracking-[0.15em] text-sepia font-normal">
                Lançamento
              </TableHead>
              <TableHead className="hidden lg:table-cell text-[11px] uppercase tracking-[0.15em] text-sepia font-normal">
                Prazo
              </TableHead>
              <TableHead className="hidden lg:table-cell text-[11px] uppercase tracking-[0.15em] text-sepia font-normal">
                Vale nota
              </TableHead>
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
                  <TableCell className="hidden md:table-cell">
                    {disciplinasPorId.get(t.disciplina) ?? `#${t.disciplina}`}
                  </TableCell>
                  <TableCell className="hidden md:table-cell tabular-nums whitespace-nowrap">
                    {new Date(t.data_lancamento + "T00:00:00").toLocaleDateString(
                      "pt-BR",
                    )}
                  </TableCell>
                  <TableCell className="hidden lg:table-cell tabular-nums whitespace-nowrap">
                    {t.prazo
                      ? new Date(t.prazo + "T00:00:00").toLocaleDateString("pt-BR")
                      : "—"}
                  </TableCell>
                  <TableCell className="hidden lg:table-cell">
                    {t.vale_nota ? (
                      <span className="text-xs text-ferrugem bg-ferrugem/10 px-2 py-0.5 rounded">
                        {t.nota_maxima ? `Vale ${t.nota_maxima}` : "Sim"}
                      </span>
                    ) : (
                      <span className="text-xs text-sepia">Não</span>
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
          totalCount > 0 ? `${totalCount} tarefas no total` : undefined
        }
      />
    </div>
  );
}
