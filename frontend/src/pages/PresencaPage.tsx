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
import { RegistroFormDialog } from "@/features/presenca/RegistroFormDialog";
import { useRegistros } from "@/features/presenca/hooks";
import { useTurmas } from "@/features/turmas/hooks";
import { brToIso, isoToBr } from "@/lib/dates";

export function PresencaPage() {
  const navigate = useNavigate();
  const registrosQuery = useRegistros();
  const turmasQuery = useTurmas();
  const [busca, setBusca] = useState("");
  const [formOpen, setFormOpen] = useState(false);

  const turmasPorId = useMemo(() => {
    const map = new Map<number, string>();
    turmasQuery.data?.forEach((t) => map.set(t.id, t.nome));
    return map;
  }, [turmasQuery.data]);

  // Ordena por data desc (mais recente primeiro) — chamadas do dia
  // sempre no topo.
  const registrosOrdenados = useMemo(() => {
    if (!registrosQuery.data) return [];
    return [...registrosQuery.data].sort((a, b) =>
      b.data.localeCompare(a.data),
    );
  }, [registrosQuery.data]);

  const registrosFiltrados = useMemo(() => {
    const q = busca.trim().toLowerCase();
    if (!q) return registrosOrdenados;
    // O usuário pode digitar a data no formato pt-BR (dd/mm ou
    // dd/mm/aaaa). Convertendo pra ISO antes da comparação, a busca
    // funciona sem expor o formato cru "YYYY-MM-DD" no placeholder.
    const isoQuery = brToIso(q);
    return registrosOrdenados.filter((r) => {
      const nomeTurma = turmasPorId.get(r.turma)?.toLowerCase() ?? "";
      const dataBr = isoToBr(r.data);
      return (
        nomeTurma.includes(q) ||
        dataBr.includes(q) ||
        (isoQuery !== null && r.data.startsWith(isoQuery))
      );
    });
  }, [registrosOrdenados, busca, turmasPorId]);

  return (
    <div className="p-8 space-y-6">
      <header className="flex items-center justify-between">
        <h1 className="text-3xl font-semibold">Presença</h1>
        <Button onClick={() => setFormOpen(true)}>Nova chamada</Button>
      </header>

      <RegistroFormDialog
        open={formOpen}
        onOpenChange={setFormOpen}
        onCreated={(id) => navigate(`/presenca/${id}`)}
      />

      <Input
        placeholder="Buscar por turma ou data..."
        value={busca}
        onChange={(e) => setBusca(e.target.value)}
        className="max-w-sm"
      />

      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Turma</TableHead>
              <TableHead>Data</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {registrosQuery.isLoading ? (
              Array.from({ length: 5 }).map((_, i) => (
                <TableRow key={i}>
                  <TableCell>
                    <Skeleton className="h-4 w-32" />
                  </TableCell>
                  <TableCell>
                    <Skeleton className="h-4 w-24" />
                  </TableCell>
                </TableRow>
              ))
            ) : registrosQuery.isError ? (
              <TableRow>
                <TableCell
                  colSpan={2}
                  className="text-center text-destructive py-8"
                >
                  Erro ao carregar chamadas.
                </TableCell>
              </TableRow>
            ) : registrosFiltrados.length === 0 ? (
              <TableRow>
                <TableCell
                  colSpan={2}
                  className="text-center text-muted-foreground py-8"
                >
                  {busca
                    ? "Nenhuma chamada encontrada."
                    : "Nenhuma chamada registrada."}
                </TableCell>
              </TableRow>
            ) : (
              registrosFiltrados.map((r) => (
                <TableRow
                  key={r.id}
                  className="cursor-pointer"
                  onClick={() => navigate(`/presenca/${r.id}`)}
                >
                  <TableCell>
                    {turmasPorId.get(r.turma) ?? `#${r.turma}`}
                  </TableCell>
                  <TableCell className="tabular-nums whitespace-nowrap">
                    {new Date(r.data + "T00:00:00").toLocaleDateString(
                      "pt-BR",
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
