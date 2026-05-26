import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
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
import { OcorrenciaFormDialog } from "@/features/ocorrencias/OcorrenciaFormDialog";
import {
  STATUS_BADGE,
  STATUS_LABEL,
  STATUS_OPTIONS,
  STATUS_ORDEM,
} from "@/features/ocorrencias/constants";
import { useOcorrencias } from "@/features/ocorrencias/hooks";
import { useTurmas } from "@/features/turmas/hooks";
import type { OcorrenciaStatus } from "@/types/api";

const FILTRO_TODOS = "__all__";

export function OcorrenciasPage() {
  const navigate = useNavigate();
  const [filtroStatus, setFiltroStatus] = useState<string>(FILTRO_TODOS);
  const [busca, setBusca] = useState("");
  const [formOpen, setFormOpen] = useState(false);

  const ocorrenciasQuery = useOcorrencias(
    filtroStatus !== FILTRO_TODOS
      ? { status: filtroStatus as OcorrenciaStatus }
      : {},
  );
  const alunosQuery = useAlunos();
  const turmasQuery = useTurmas();

  const alunosPorId = useMemo(() => {
    const map = new Map<number, string>();
    alunosQuery.data?.forEach((a) => map.set(a.id, a.nome_completo));
    return map;
  }, [alunosQuery.data]);

  const turmasPorId = useMemo(() => {
    const map = new Map<number, string>();
    turmasQuery.data?.forEach((t) => map.set(t.id, t.nome));
    return map;
  }, [turmasQuery.data]);

  // Ordenação composta:
  // 1. Status (abertas primeiro, arquivadas por último — ver STATUS_ORDEM).
  // 2. Data desc dentro do mesmo status (mais recente primeiro).
  // Reflete a UX desejada: o que precisa de ação aparece em cima.
  const ocorrenciasOrdenadas = useMemo(() => {
    if (!ocorrenciasQuery.data) return [];
    return [...ocorrenciasQuery.data].sort((a, b) => {
      const diffStatus = STATUS_ORDEM[a.status] - STATUS_ORDEM[b.status];
      if (diffStatus !== 0) return diffStatus;
      return b.data_ocorrencia.localeCompare(a.data_ocorrencia);
    });
  }, [ocorrenciasQuery.data]);

  const ocorrenciasFiltradas = useMemo(() => {
    const q = busca.trim().toLowerCase();
    if (!q) return ocorrenciasOrdenadas;
    return ocorrenciasOrdenadas.filter((o) => {
      const nomeAluno = alunosPorId.get(o.aluno)?.toLowerCase() ?? "";
      const nomeTurma = turmasPorId.get(o.turma)?.toLowerCase() ?? "";
      return nomeAluno.includes(q) || nomeTurma.includes(q);
    });
  }, [ocorrenciasOrdenadas, busca, alunosPorId, turmasPorId]);

  return (
    <div className="p-4 md:p-8 space-y-6">
      <header className="flex items-center justify-between">
        <h1 className="text-2xl md:text-3xl font-semibold">Ocorrências</h1>
        <Button onClick={() => setFormOpen(true)}>Nova ocorrência</Button>
      </header>

      <OcorrenciaFormDialog open={formOpen} onOpenChange={setFormOpen} />

      <div className="flex gap-3 items-center">
        <Input
          placeholder="Buscar por aluno ou turma..."
          value={busca}
          onChange={(e) => setBusca(e.target.value)}
          className="max-w-sm"
        />
        <Select value={filtroStatus} onValueChange={setFiltroStatus}>
          <SelectTrigger className="w-44">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={FILTRO_TODOS}>Todos os status</SelectItem>
            {STATUS_OPTIONS.map((s) => (
              <SelectItem key={s.value} value={s.value}>
                {s.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Data</TableHead>
              {/* Turma e Status só a partir de md (≥768px) — em mobile
                  cabem só Data + Aluno; o resto fica no detalhe da
                  ocorrência (linha clicável). */}
              <TableHead className="hidden md:table-cell">Turma</TableHead>
              <TableHead>Aluno</TableHead>
              <TableHead className="hidden md:table-cell">Status</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {ocorrenciasQuery.isLoading ? (
              Array.from({ length: 5 }).map((_, i) => (
                <TableRow key={i}>
                  <TableCell>
                    <Skeleton className="h-4 w-20" />
                  </TableCell>
                  <TableCell>
                    <Skeleton className="h-4 w-28" />
                  </TableCell>
                  <TableCell>
                    <Skeleton className="h-4 w-32" />
                  </TableCell>
                  <TableCell>
                    <Skeleton className="h-4 w-16" />
                  </TableCell>
                </TableRow>
              ))
            ) : ocorrenciasQuery.isError ? (
              <TableRow>
                <TableCell
                  colSpan={4}
                  className="text-center text-destructive py-8"
                >
                  Erro ao carregar ocorrências.
                </TableCell>
              </TableRow>
            ) : ocorrenciasFiltradas.length === 0 ? (
              <TableRow>
                <TableCell
                  colSpan={4}
                  className="text-center text-muted-foreground py-8"
                >
                  {busca || filtroStatus !== FILTRO_TODOS
                    ? "Nenhuma ocorrência encontrada."
                    : "Nenhuma ocorrência registrada."}
                </TableCell>
              </TableRow>
            ) : (
              ocorrenciasFiltradas.map((o) => (
                <TableRow
                  key={o.id}
                  className="cursor-pointer"
                  onClick={() => navigate(`/ocorrencias/${o.id}`)}
                >
                  <TableCell className="tabular-nums whitespace-nowrap">
                    {new Date(o.data_ocorrencia + "T00:00:00").toLocaleDateString(
                      "pt-BR",
                    )}
                  </TableCell>
                  <TableCell className="hidden md:table-cell">
                    {turmasPorId.get(o.turma) ?? `#${o.turma}`}
                  </TableCell>
                  <TableCell>
                    {alunosPorId.get(o.aluno) ?? `#${o.aluno}`}
                  </TableCell>
                  <TableCell className="hidden md:table-cell">
                    <span
                      className={`text-xs px-2 py-0.5 rounded ${STATUS_BADGE[o.status]}`}
                    >
                      {STATUS_LABEL[o.status]}
                    </span>
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
