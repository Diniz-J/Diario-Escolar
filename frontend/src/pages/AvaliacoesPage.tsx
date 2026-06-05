import { useMemo, useState } from "react";
import { Link } from "react-router-dom";

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
import { usePermissoes } from "@/features/auth/usePermissoes";
import { AvaliacaoFormDialog } from "@/features/avaliacoes/AvaliacaoFormDialog";
import {
  useAvaliacoes,
  useDeactivateAvaliacao,
} from "@/features/avaliacoes/hooks";
import type { Avaliacao, AvaliacaoTipo } from "@/types/api";

// Paleta dos tipos alinhada com a identidade do projeto — pastels
// terrosos pra ficar coerente com os badges de presenca e ocorrencia.
const TIPO_STYLE: Record<AvaliacaoTipo, string> = {
  prova: "bg-[#F4DAD3] text-[#7C2D1A]", // ferrugem claro — peso maior
  trabalho: "bg-[#FCE7BC] text-[#854D0E]", // mostarda
  atividade: "bg-[#C4D4D2] text-[#1F3A37]", // petrol claro
  participacao: "bg-[#D7DCC1] text-[#3A4524]", // olive
};

function formatarDataBR(iso: string): string {
  const [ano, mes, dia] = iso.split("-");
  return `${dia}/${mes}/${ano}`;
}

export function AvaliacoesPage() {
  const avaliacoesQuery = useAvaliacoes({ ativo: true });
  const desativar = useDeactivateAvaliacao();
  const { podeModificarCadastros } = usePermissoes();

  const [busca, setBusca] = useState("");
  const [formOpen, setFormOpen] = useState(false);
  const [editando, setEditando] = useState<Avaliacao | null>(null);

  const filtradas = useMemo(() => {
    const lista = avaliacoesQuery.data ?? [];
    const q = busca.trim().toLowerCase();
    if (!q) return lista;
    return lista.filter(
      (a) =>
        a.titulo.toLowerCase().includes(q) ||
        a.disciplina_nome.toLowerCase().includes(q) ||
        a.turma_nome.toLowerCase().includes(q),
    );
  }, [avaliacoesQuery.data, busca]);

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
            Avaliações
          </h1>
          <div className="h-px w-10 bg-ferrugem" />
          <p className="text-sm text-sepia max-w-xl">
            Provas, trabalhos e atividades avaliativas. O sistema
            armazena as notas — a média final continua na régua da
            escola.
          </p>
        </div>
        {podeModificarCadastros && (
          <Button onClick={() => setFormOpen(true)}>Nova avaliação</Button>
        )}
      </header>

      <AvaliacaoFormDialog
        open={dialogAberto}
        onOpenChange={fecharDialog}
        avaliacao={editando}
      />

      <Input
        placeholder="Buscar por título, turma ou disciplina..."
        value={busca}
        onChange={(e) => setBusca(e.target.value)}
        className="max-w-md"
      />

      <div className="rounded-lg border border-border bg-paper overflow-hidden">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="text-[11px] uppercase tracking-[0.15em] text-sepia font-normal">
                Título
              </TableHead>
              <TableHead className="text-[11px] uppercase tracking-[0.15em] text-sepia font-normal hidden md:table-cell">
                Tipo
              </TableHead>
              <TableHead className="text-[11px] uppercase tracking-[0.15em] text-sepia font-normal">
                Turma
              </TableHead>
              <TableHead className="text-[11px] uppercase tracking-[0.15em] text-sepia font-normal hidden lg:table-cell">
                Disciplina
              </TableHead>
              <TableHead className="text-[11px] uppercase tracking-[0.15em] text-sepia font-normal">
                Data
              </TableHead>
              <TableHead className="text-[11px] uppercase tracking-[0.15em] text-sepia font-normal text-right">
                Notas
              </TableHead>
              <TableHead className="w-12"></TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {avaliacoesQuery.isLoading ? (
              Array.from({ length: 4 }).map((_, i) => (
                <TableRow key={i}>
                  {Array.from({ length: 7 }).map((__, j) => (
                    <TableCell key={j}>
                      <Skeleton className="h-4 w-full" />
                    </TableCell>
                  ))}
                </TableRow>
              ))
            ) : avaliacoesQuery.isError ? (
              <TableRow>
                <TableCell
                  colSpan={7}
                  className="text-center text-destructive py-8"
                >
                  Erro ao carregar avaliações.
                </TableCell>
              </TableRow>
            ) : filtradas.length === 0 ? (
              <TableRow>
                <TableCell
                  colSpan={7}
                  className="text-center text-muted-foreground py-8"
                >
                  {busca
                    ? "Nenhuma avaliação encontrada."
                    : "Nenhuma avaliação cadastrada. Crie a primeira pra começar a lançar notas."}
                </TableCell>
              </TableRow>
            ) : (
              filtradas.map((a) => (
                <TableRow
                  key={a.id}
                  className="cursor-pointer hover:bg-linho/40"
                >
                  <TableCell>
                    <Link
                      to={`/avaliacoes/${a.id}`}
                      className="text-tinta hover:text-ferrugem transition-colors block"
                    >
                      {a.titulo}
                    </Link>
                  </TableCell>
                  <TableCell className="hidden md:table-cell">
                    <span
                      className={`text-[10px] uppercase tracking-wider px-2 py-0.5 rounded ${TIPO_STYLE[a.tipo]}`}
                    >
                      {a.tipo_display}
                    </span>
                  </TableCell>
                  <TableCell className="text-sepia">{a.turma_nome}</TableCell>
                  <TableCell className="hidden lg:table-cell text-sepia">
                    {a.disciplina_nome}
                  </TableCell>
                  <TableCell className="text-sepia tabular-nums">
                    {formatarDataBR(a.data)}
                  </TableCell>
                  <TableCell className="text-right text-sepia tabular-nums font-mono text-sm">
                    {a.notas_lancadas}/{a.total_alunos}
                  </TableCell>
                  <TableCell onClick={(e) => e.stopPropagation()}>
                    {podeModificarCadastros && (
                      <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                          <Button variant="ghost" size="icon-sm">
                            ⋯
                          </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end">
                          <DropdownMenuItem onClick={() => setEditando(a)}>
                            Editar
                          </DropdownMenuItem>
                          <DropdownMenuItem
                            onClick={() => desativar.mutate(a.id)}
                            className="text-destructive focus:text-destructive"
                          >
                            Desativar
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
