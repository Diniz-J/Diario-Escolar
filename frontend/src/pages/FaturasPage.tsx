import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { Pagination } from "@/components/Pagination";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
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
import { FaturaCancelDialog } from "@/features/financeiro/FaturaCancelDialog";
import { FaturaDetalheDialog } from "@/features/financeiro/FaturaDetalheDialog";
import { FaturaFormDialog } from "@/features/financeiro/FaturaFormDialog";
import { FinanceiroTabs } from "@/features/financeiro/FinanceiroTabs";
import { PagamentoFormDialog } from "@/features/financeiro/PagamentoFormDialog";
import {
  STATUS_FATURA,
  competenciaDoMes,
  formatarBRL,
  formatarCompetencia,
  formatarData,
} from "@/features/financeiro/constants";
import { useFaturasPaginated } from "@/features/financeiro/hooks";
import { useTurmas } from "@/features/turmas/hooks";
import type { Fatura, FaturaStatus } from "@/types/api";

const FILTRO_TODOS = "__all__";
const PAGE_SIZE = 20;

const STATUS_ORDEM: FaturaStatus[] = [
  "pendente",
  "vencido",
  "pago",
  "cancelado",
];

// Contas a receber — a tela da secretaria. O backend já chega escopado por
// escola e restrito a nível-diretor (professor e inspetor levam 403 até na
// leitura), então a sidebar esconde o item pra eles.
export function FaturasPage() {
  const turmasQuery = useTurmas();
  // `?turma=<id>` na URL pré-filtra a lista. É como a TurmaDetalhePage
  // manda pra cá ("Financeiro" no cabeçalho da turma): a pergunta de lá é
  // "como está a situação financeira desta turma".
  const [searchParams] = useSearchParams();

  const [filtroStatus, setFiltroStatus] = useState<string>(FILTRO_TODOS);
  const [filtroTurma, setFiltroTurma] = useState<string>(
    searchParams.get("turma") ?? FILTRO_TODOS,
  );
  const [filtroMes, setFiltroMes] = useState<string>("");
  const [busca, setBusca] = useState("");
  const [buscaAplicada, setBuscaAplicada] = useState("");
  const [page, setPage] = useState(1);

  const [formAberto, setFormAberto] = useState(false);
  const [formKey, setFormKey] = useState(0);
  const [editando, setEditando] = useState<Fatura | null>(null);
  const [detalhe, setDetalhe] = useState<Fatura | null>(null);
  const [pagando, setPagando] = useState<Fatura | null>(null);
  const [cancelando, setCancelando] = useState<Fatura | null>(null);

  // Busca server-side por nome e matrícula, com atraso pra não disparar
  // uma request por tecla. Reset de página no handler, não em efeito.
  useEffect(() => {
    const t = setTimeout(() => {
      setBuscaAplicada(busca.trim());
      setPage(1);
    }, 350);
    return () => clearTimeout(t);
  }, [busca]);

  function filtrar<T>(setter: (valor: T) => void) {
    return (valor: T) => {
      setter(valor);
      setPage(1);
    };
  }

  const faturasQuery = useFaturasPaginated(
    {
      ...(filtroStatus !== FILTRO_TODOS && {
        status: filtroStatus as FaturaStatus,
      }),
      ...(filtroTurma !== FILTRO_TODOS && { turma: Number(filtroTurma) }),
      ...(filtroMes && { competencia: competenciaDoMes(filtroMes) }),
      ...(buscaAplicada && { search: buscaAplicada }),
    },
    { page, page_size: PAGE_SIZE },
  );

  const faturas = faturasQuery.data?.results ?? [];
  const totalCount = faturasQuery.data?.count ?? 0;
  const totalPages = Math.max(1, Math.ceil(totalCount / PAGE_SIZE));

  // Cancelar tira a fatura do filtro "pendente". Se era a única da página,
  // ela deixa de existir e o DRF responde 404 — volta uma antes do refetch.
  function voltarSeEsvaziou() {
    if (faturas.length === 1 && page > 1) setPage((p) => p - 1);
  }

  function abrirForm(fatura: Fatura | null) {
    setEditando(fatura);
    setFormKey((k) => k + 1);
    setFormAberto(true);
  }

  // Fecha o detalhe antes de abrir o pagamento: dois dialogs abertos
  // brigam por foco e travam o scroll do body.
  function registrarPagamento(fatura: Fatura) {
    setDetalhe(null);
    setPagando(fatura);
  }

  return (
    <div className="p-4 md:p-8 space-y-6">
      <header className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
        <div className="space-y-3">
          <h1 className="font-heading text-[28px] md:text-[34px] tracking-tight text-tinta leading-[1.15]">
            Financeiro
          </h1>
          <div className="h-px w-10 bg-ferrugem" />
          <p className="text-sm text-muted-foreground max-w-xl">
            Mensalidades a receber. A geração mensal cria as faturas a partir
            dos planos de cobrança; aqui a secretaria acompanha e registra o
            que entrou.
          </p>
        </div>
        <Button onClick={() => abrirForm(null)}>Nova fatura</Button>
      </header>

      <FinanceiroTabs />

      <FaturaFormDialog
        key={formKey}
        open={formAberto}
        onOpenChange={setFormAberto}
        fatura={editando}
      />
      <FaturaDetalheDialog
        fatura={detalhe}
        onOpenChange={(aberto) => !aberto && setDetalhe(null)}
        onRegistrarPagamento={registrarPagamento}
      />
      <PagamentoFormDialog
        key={pagando?.id ?? "nenhum"}
        fatura={pagando}
        onOpenChange={(aberto) => !aberto && setPagando(null)}
      />
      <FaturaCancelDialog
        fatura={cancelando}
        onOpenChange={(aberto) => !aberto && setCancelando(null)}
        onCancelada={voltarSeEsvaziou}
      />

      <div className="flex flex-wrap gap-3 items-end">
        <Select value={filtroStatus} onValueChange={filtrar(setFiltroStatus)}>
          <SelectTrigger className="w-44">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={FILTRO_TODOS}>Todos os status</SelectItem>
            {STATUS_ORDEM.map((s) => (
              <SelectItem key={s} value={s}>
                {STATUS_FATURA[s].label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Select value={filtroTurma} onValueChange={filtrar(setFiltroTurma)}>
          <SelectTrigger className="w-48">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={FILTRO_TODOS}>Todas as turmas</SelectItem>
            {(turmasQuery.data ?? []).map((t) => (
              <SelectItem key={t.id} value={String(t.id)}>
                {t.nome}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Input
          type="month"
          className="w-40"
          value={filtroMes}
          onChange={(e) => filtrar(setFiltroMes)(e.target.value)}
          aria-label="Competência"
        />
        <Input
          className="w-56"
          placeholder="Buscar por aluno ou matrícula"
          value={busca}
          onChange={(e) => setBusca(e.target.value)}
        />
      </div>

      {faturasQuery.isLoading ? (
        <div className="space-y-2">
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-10 w-full" />
        </div>
      ) : faturas.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          Nenhuma fatura neste recorte.
        </p>
      ) : (
        <>
          <div className="rounded-md border border-border bg-paper">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Aluno</TableHead>
                  <TableHead className="hidden sm:table-cell">
                    Competência
                  </TableHead>
                  <TableHead className="hidden md:table-cell">
                    Vencimento
                  </TableHead>
                  <TableHead className="text-right">Valor</TableHead>
                  <TableHead className="hidden lg:table-cell text-right">
                    Saldo
                  </TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="w-10" />
                </TableRow>
              </TableHeader>
              <TableBody>
                {faturas.map((fatura) => {
                  const status = STATUS_FATURA[fatura.status];
                  return (
                    <TableRow
                      key={fatura.id}
                      className="cursor-pointer"
                      onClick={() => setDetalhe(fatura)}
                    >
                      <TableCell>
                        {/* Leva à ficha do aluno. `stopPropagation` porque
                            a linha inteira abre o detalhe da fatura. */}
                        <Link
                          to={`/financeiro/alunos/${fatura.aluno}`}
                          onClick={(e) => e.stopPropagation()}
                          className="hover:text-ferrugem hover:underline"
                        >
                          {fatura.aluno_nome}
                        </Link>
                      </TableCell>
                      <TableCell className="hidden sm:table-cell">
                        {formatarCompetencia(fatura.competencia)}
                      </TableCell>
                      <TableCell className="hidden md:table-cell">
                        {formatarData(fatura.vencimento)}
                      </TableCell>
                      <TableCell className="text-right">
                        {formatarBRL(fatura.valor)}
                      </TableCell>
                      <TableCell className="hidden lg:table-cell text-right">
                        {formatarBRL(fatura.saldo)}
                      </TableCell>
                      <TableCell>
                        <span
                          className={`inline-flex rounded px-2 py-0.5 text-[11px] uppercase tracking-[0.14em] ${status.className}`}
                        >
                          {status.label}
                        </span>
                      </TableCell>
                      <TableCell onClick={(e) => e.stopPropagation()}>
                        <DropdownMenu>
                          <DropdownMenuTrigger asChild>
                            <Button
                              variant="ghost"
                              size="icon-sm"
                              aria-label="Ações da fatura"
                            >
                              ⋯
                            </Button>
                          </DropdownMenuTrigger>
                          <DropdownMenuContent align="end">
                            {fatura.status !== "cancelado" &&
                              Number(fatura.saldo) > 0 && (
                                <DropdownMenuItem
                                  onClick={() => setPagando(fatura)}
                                >
                                  Registrar pagamento
                                </DropdownMenuItem>
                              )}
                            <DropdownMenuItem onClick={() => abrirForm(fatura)}>
                              Editar
                            </DropdownMenuItem>
                            {fatura.status !== "cancelado" && (
                              <DropdownMenuItem
                                onClick={() => setCancelando(fatura)}
                              >
                                Cancelar fatura
                              </DropdownMenuItem>
                            )}
                          </DropdownMenuContent>
                        </DropdownMenu>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </div>
          <Pagination
            page={page}
            totalPages={totalPages}
            onPageChange={setPage}
            totalLabel={`${totalCount} fatura(s)`}
          />
        </>
      )}
    </div>
  );
}
