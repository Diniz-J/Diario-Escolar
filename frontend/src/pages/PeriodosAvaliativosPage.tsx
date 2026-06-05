import { useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Skeleton } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { usePermissoes } from "@/features/auth/usePermissoes";
import { PeriodoAvaliativoFormDialog } from "@/features/periodos-avaliativos/PeriodoAvaliativoFormDialog";
import {
  useDeactivatePeriodoAvaliativo,
  usePeriodosAvaliativos,
  useReactivatePeriodoAvaliativo,
} from "@/features/periodos-avaliativos/hooks";
import type { PeriodoAvaliativo, PeriodoEstado } from "@/types/api";

// Rótulo PT-BR pra cada estado. Hoje todos os períodos voltam como
// "vazio" (Avaliacao ainda não existe). Quando os PRs seguintes
// adicionarem dependentes, "em_uso" e "fechado" começam a aparecer.
const LABEL_ESTADO: Record<PeriodoEstado, string> = {
  vazio: "Vazio",
  em_uso: "Em uso",
  fechado: "Fechado",
};

// Classes shadcn-style por estado, alinhadas com a paleta da marca
// (mesmo princípio dos badges de ocorrência).
const CLASSE_ESTADO: Record<PeriodoEstado, string> = {
  vazio: "bg-muted text-sepia",
  em_uso: "bg-[#FCE7BC] text-[#854D0E]",
  fechado: "bg-[#D7DCC1] text-[#3A4524]",
};

function formatarDataBR(iso: string): string {
  const [ano, mes, dia] = iso.split("-");
  return `${dia}/${mes}/${ano}`;
}

// Tela de configuração da régua de avaliação da escola. Acesso restrito
// a admin/diretor/secretaria (gating via `podeModificarCadastros`).
//
// Cada escola decide quantos períodos quer (trimestre=3, bimestre=4,
// semestre=2) — não há seed automático. Estado computado server-side
// (`vazio` / `em_uso` / `fechado`) vai pautar a UI nos PRs seguintes
// pra travar edição quando o boletim já tiver sido lançado; por
// enquanto tudo é "vazio" e edição é livre.
export function PeriodosAvaliativosPage() {
  const { podeModificarCadastros } = usePermissoes();
  const [mostrarInativos, setMostrarInativos] = useState(false);
  const periodosQuery = usePeriodosAvaliativos(
    mostrarInativos ? { ativo: false } : { ativo: true },
  );
  const desativar = useDeactivatePeriodoAvaliativo();
  const reativar = useReactivatePeriodoAvaliativo();

  const [formOpen, setFormOpen] = useState(false);
  const [editando, setEditando] = useState<PeriodoAvaliativo | null>(null);

  const dialogAberto = formOpen || editando !== null;
  function fecharDialog(open: boolean) {
    if (!open) {
      setFormOpen(false);
      setEditando(null);
    }
  }

  // Agrupa por ano letivo em ordem decrescente (mais recente em cima),
  // mantendo a ordem interna por `ordem` que o backend já devolve.
  const agrupado = useMemo(() => {
    const dados = periodosQuery.data ?? [];
    const mapa = new Map<number, PeriodoAvaliativo[]>();
    for (const p of dados) {
      const lista = mapa.get(p.ano_letivo) ?? [];
      lista.push(p);
      mapa.set(p.ano_letivo, lista);
    }
    return Array.from(mapa.entries()).sort((a, b) => b[0] - a[0]);
  }, [periodosQuery.data]);

  // Pra abrir o "Novo período" já com ano sugerido razoável: pega o ano
  // do primeiro grupo (se houver). Senão, o dialog cai no ano atual.
  const anoDefault = agrupado[0]?.[0];

  return (
    <div className="p-4 md:p-8 space-y-6">
      <header className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
        <div className="space-y-3">
          <p className="text-[11px] uppercase tracking-[0.2em] text-sepia">
            Configuração
          </p>
          <h1 className="font-heading text-[28px] md:text-[34px] tracking-tight text-tinta leading-[1.15]">
            Períodos avaliativos
          </h1>
          <div className="h-px w-10 bg-ferrugem" />
          <p className="text-sm text-sepia max-w-xl">
            A régua de avaliação da escola — bimestre, trimestre ou
            semestre. Cada período define só a faixa de datas; o sistema
            armazena as notas, a escola continua decidindo a média.
          </p>
        </div>
        <div className="flex items-center gap-2">
          {podeModificarCadastros && (
            <Button onClick={() => setFormOpen(true)}>Novo período</Button>
          )}
        </div>
      </header>

      <PeriodoAvaliativoFormDialog
        open={dialogAberto}
        onOpenChange={fecharDialog}
        periodo={editando}
        anoLetivoDefault={anoDefault}
      />

      <div className="flex items-center gap-3">
        <Switch
          id="mostrar-inativos"
          checked={mostrarInativos}
          onCheckedChange={setMostrarInativos}
        />
        <label
          htmlFor="mostrar-inativos"
          className="text-[11px] uppercase tracking-[0.18em] text-sepia cursor-pointer"
        >
          Mostrar inativos
        </label>
      </div>

      {periodosQuery.isLoading ? (
        <div className="space-y-2">
          <Skeleton className="h-12 w-full" />
          <Skeleton className="h-12 w-full" />
          <Skeleton className="h-12 w-3/4" />
        </div>
      ) : periodosQuery.isError ? (
        <p className="text-destructive">Erro ao carregar períodos.</p>
      ) : agrupado.length === 0 ? (
        <div className="rounded-lg border border-border bg-paper p-6 text-sepia">
          {mostrarInativos
            ? "Nenhum período inativo."
            : "Nenhum período cadastrado. Crie o primeiro pra começar a configurar avaliação."}
        </div>
      ) : (
        <div className="space-y-6">
          {agrupado.map(([ano, periodos]) => (
            <section key={ano} className="space-y-2">
              <h2 className="font-heading text-xl text-tinta">{ano}</h2>
              <div className="rounded-lg border border-border bg-paper overflow-hidden">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead className="w-12 text-[11px] uppercase tracking-[0.15em] text-sepia font-normal">
                        #
                      </TableHead>
                      <TableHead className="text-[11px] uppercase tracking-[0.15em] text-sepia font-normal">
                        Nome
                      </TableHead>
                      <TableHead className="text-[11px] uppercase tracking-[0.15em] text-sepia font-normal">
                        Início
                      </TableHead>
                      <TableHead className="text-[11px] uppercase tracking-[0.15em] text-sepia font-normal">
                        Fim
                      </TableHead>
                      <TableHead className="text-[11px] uppercase tracking-[0.15em] text-sepia font-normal">
                        Estado
                      </TableHead>
                      <TableHead className="w-12"></TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {periodos.map((p) => (
                      <TableRow key={p.id}>
                        <TableCell className="font-mono text-sepia">
                          {p.ordem}
                        </TableCell>
                        <TableCell>
                          <span className="text-tinta">{p.nome}</span>
                          {!p.ativo && (
                            <span className="ml-2 text-[10px] uppercase tracking-wider text-sepia">
                              [ inativo ]
                            </span>
                          )}
                        </TableCell>
                        <TableCell className="text-sepia tabular-nums">
                          {formatarDataBR(p.data_inicio)}
                        </TableCell>
                        <TableCell className="text-sepia tabular-nums">
                          {formatarDataBR(p.data_fim)}
                        </TableCell>
                        <TableCell>
                          <span
                            className={`text-[10px] uppercase tracking-wider px-2 py-0.5 rounded ${CLASSE_ESTADO[p.estado]}`}
                          >
                            {LABEL_ESTADO[p.estado]}
                          </span>
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
                                {p.ativo ? (
                                  <DropdownMenuItem
                                    onClick={() => desativar.mutate(p.id)}
                                    className="text-destructive focus:text-destructive"
                                  >
                                    Desativar
                                  </DropdownMenuItem>
                                ) : (
                                  <DropdownMenuItem
                                    onClick={() => reativar.mutate(p.id)}
                                  >
                                    Reativar
                                  </DropdownMenuItem>
                                )}
                              </DropdownMenuContent>
                            </DropdownMenu>
                          )}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            </section>
          ))}
        </div>
      )}
    </div>
  );
}
