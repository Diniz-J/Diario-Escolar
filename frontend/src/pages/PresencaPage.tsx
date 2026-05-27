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

export function PresencaPage() {
  const navigate = useNavigate();
  const [dataInicio, setDataInicio] = useState("");
  const [dataFim, setDataFim] = useState("");
  // Range de datas filtrado server-side; busca por turma continua client-side.
  const registrosQuery = useRegistros({
    ...(dataInicio ? { data_inicio: dataInicio } : {}),
    ...(dataFim ? { data_fim: dataFim } : {}),
  });
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
    return registrosOrdenados.filter((r) => {
      const nomeTurma = turmasPorId.get(r.turma)?.toLowerCase() ?? "";
      // Casamos tanto contra a data crua (ISO YYYY-MM-DD) quanto contra
      // a versão pt-BR (DD/MM/YYYY) — assim o usuário pode buscar como
      // "22/05" ou "22/05/2026" sem precisar saber o formato interno.
      const dataBR = new Date(r.data + "T00:00:00").toLocaleDateString(
        "pt-BR",
      );
      return (
        nomeTurma.includes(q) ||
        r.data.includes(q) ||
        dataBR.includes(q)
      );
    });
  }, [registrosOrdenados, busca, turmasPorId]);

  return (
    <div className="p-4 md:p-8 space-y-6">
      <header className="flex items-center justify-between">
        <h1 className="text-2xl md:text-3xl font-semibold">Presença</h1>
        <Button onClick={() => setFormOpen(true)}>Nova chamada</Button>
      </header>

      <RegistroFormDialog
        open={formOpen}
        onOpenChange={setFormOpen}
        onCreated={(id) => navigate(`/presenca/${id}`)}
      />

      <div className="flex flex-wrap gap-3 items-end">
        <Input
          placeholder="Buscar por turma ou data..."
          value={busca}
          onChange={(e) => setBusca(e.target.value)}
          className="max-w-sm"
        />
        <div className="flex flex-col gap-1">
          <label htmlFor="data-inicio" className="text-xs text-muted-foreground">
            De
          </label>
          <Input
            id="data-inicio"
            type="date"
            value={dataInicio}
            max={dataFim || undefined}
            onChange={(e) => setDataInicio(e.target.value)}
            className="w-[160px]"
          />
        </div>
        <div className="flex flex-col gap-1">
          <label htmlFor="data-fim" className="text-xs text-muted-foreground">
            Até
          </label>
          <Input
            id="data-fim"
            type="date"
            value={dataFim}
            min={dataInicio || undefined}
            onChange={(e) => setDataFim(e.target.value)}
            className="w-[160px]"
          />
        </div>
        {(dataInicio || dataFim) && (
          <Button
            variant="ghost"
            size="sm"
            onClick={() => {
              setDataInicio("");
              setDataFim("");
            }}
          >
            Limpar datas
          </Button>
        )}
      </div>

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
