import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import { ExportarMenu } from "@/components/ExportarMenu";
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
import { PlanoEnsinoCreateDialog } from "@/features/planos-ensino/PlanoEnsinoCreateDialog";
import { usePlanosEnsinoPaginated } from "@/features/planos-ensino/hooks";
import { useTurmas } from "@/features/turmas/hooks";
import type { PlanoEnsino } from "@/types/api";

// Heurística de "está preenchido": considera ementa OU conteúdo
// programático com algum texto. Não precisa estar tudo cheio pra contar
// como preenchido.
function isPreenchido(p: PlanoEnsino): boolean {
  return p.ementa.trim().length > 0 || p.conteudo_programatico.trim().length > 0;
}

const PAGE_SIZE = 20;

export function PlanosEnsinoPage() {
  const navigate = useNavigate();
  const [page, setPage] = useState(1);
  const planosQuery = usePlanosEnsinoPaginated(
    {},
    { page, page_size: PAGE_SIZE },
  );
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
    const resultados = planosQuery.data?.results ?? [];
    const q = busca.trim().toLowerCase();
    if (!q) return resultados;
    return resultados.filter((p) => {
      const turma = turmasPorId.get(p.turma)?.toLowerCase() ?? "";
      const disciplina = disciplinasPorId.get(p.disciplina)?.toLowerCase() ?? "";
      return (
        turma.includes(q) ||
        disciplina.includes(q) ||
        String(p.ano_letivo).includes(q)
      );
    });
  }, [planosQuery.data, busca, turmasPorId, disciplinasPorId]);

  const totalCount = planosQuery.data?.count ?? 0;
  const totalPages = Math.max(1, Math.ceil(totalCount / PAGE_SIZE));

  return (
    <div className="p-4 md:p-8 space-y-6">
      <header className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
        <div className="space-y-3">
          <h1 className="font-heading text-[28px] md:text-[34px] tracking-tight text-tinta leading-[1.15]">
            Planos de ensino
          </h1>
          <div className="h-px w-10 bg-ferrugem" />
        </div>
        <div className="flex items-center gap-2">
          <ExportarMenu entidade="planos-ensino" />
          <Button onClick={() => setCreateOpen(true)}>Novo plano</Button>
        </div>
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

      <div className="rounded-lg border border-border bg-paper overflow-hidden">
        <Table>
          <TableHeader>
            <TableRow>
              {/* Headers em eyebrow mono — padrão do DESIGN.md §7.1.
                  Ano só em sm+ — em mobile o ano já costuma estar no
                  nome da turma. Status sempre visível porque sinaliza
                  o que o usuário ainda precisa preencher. */}
              <TableHead className="text-[11px] uppercase tracking-[0.15em] text-sepia font-normal">
                Turma
              </TableHead>
              <TableHead className="text-[11px] uppercase tracking-[0.15em] text-sepia font-normal">
                Disciplina
              </TableHead>
              <TableHead className="hidden sm:table-cell text-[11px] uppercase tracking-[0.15em] text-sepia font-normal">
                Ano
              </TableHead>
              <TableHead className="text-[11px] uppercase tracking-[0.15em] text-sepia font-normal">
                Status
              </TableHead>
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
                  <TableCell className="hidden sm:table-cell tabular-nums">
                    {p.ano_letivo}
                  </TableCell>
                  <TableCell>
                    {!p.ativo ? (
                      <span className="text-[10px] uppercase tracking-wide text-sepia">
                        Inativo
                      </span>
                    ) : isPreenchido(p) ? (
                      <span className="text-[10px] uppercase tracking-wide text-olive bg-olive/10 px-1.5 py-0.5 rounded">
                        Preenchido
                      </span>
                    ) : (
                      // Mostarda pastel — mesmo hex do "em andamento" de
                      // ocorrências (DESIGN.md §6.1) e do "rascunho" das
                      // aulas. Pattern compartilhado pra status "em curso";
                      // não existe utility/token correspondente.
                      <span className="text-[10px] uppercase tracking-wide bg-[#FCE7BC] text-[#854D0E] px-1.5 py-0.5 rounded">
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

      <Pagination
        page={page}
        totalPages={totalPages}
        onPageChange={setPage}
        totalLabel={totalCount > 0 ? `${totalCount} planos no total` : undefined}
      />
    </div>
  );
}
