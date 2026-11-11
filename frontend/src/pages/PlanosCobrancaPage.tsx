import { useEffect, useState } from "react";

import { Pagination } from "@/components/Pagination";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
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
import { FinanceiroTabs } from "@/features/financeiro/FinanceiroTabs";
import { PlanoCobrancaFormDialog } from "@/features/financeiro/PlanoCobrancaFormDialog";
import { formatarBRL } from "@/features/financeiro/constants";
import {
  useDesativarPlanoCobranca,
  usePlanosCobrancaPaginated,
  useReativarPlanoCobranca,
} from "@/features/financeiro/hooks";
import { formatarDataPura } from "@/lib/datas";
import type { PlanoCobranca } from "@/types/api";

const PAGE_SIZE = 20;

function descricaoDesconto(plano: PlanoCobranca): string {
  if (plano.desconto_tipo === "percentual") {
    return `${Number(plano.desconto_valor).toLocaleString("pt-BR")}%`;
  }
  if (plano.desconto_tipo === "fixo") {
    return formatarBRL(plano.desconto_valor);
  }
  return "—";
}

function descricaoVigencia(plano: PlanoCobranca): string {
  const inicio = formatarDataPura(plano.vigencia_inicio);
  return plano.vigencia_fim
    ? `${inicio} a ${formatarDataPura(plano.vigencia_fim)}`
    : `desde ${inicio}`;
}

// Planos de cobrança — o contrato financeiro de cada aluno, que é o que a
// geração mensal lê pra criar as faturas. Cadastro raro: fica em aba
// dentro do financeiro, não como item próprio da sidebar.
export function PlanosCobrancaPage() {
  const [busca, setBusca] = useState("");
  const [buscaAplicada, setBuscaAplicada] = useState("");
  const [mostrarEncerrados, setMostrarEncerrados] = useState(false);
  const [page, setPage] = useState(1);
  const [formAberto, setFormAberto] = useState(false);
  const [formKey, setFormKey] = useState(0);
  const [editando, setEditando] = useState<PlanoCobranca | null>(null);

  const desativar = useDesativarPlanoCobranca();
  const reativar = useReativarPlanoCobranca();

  useEffect(() => {
    const t = setTimeout(() => {
      setBuscaAplicada(busca.trim());
      setPage(1);
    }, 350);
    return () => clearTimeout(t);
  }, [busca]);

  const planosQuery = usePlanosCobrancaPaginated(
    {
      // Padrão do projeto em listagem com soft delete: só ativos, e o
      // toggle inverte pra mostrar só os encerrados.
      ativo: !mostrarEncerrados,
      ...(buscaAplicada && { search: buscaAplicada }),
    },
    { page, page_size: PAGE_SIZE },
  );

  const planos = planosQuery.data?.results ?? [];
  const totalCount = planosQuery.data?.count ?? 0;
  const totalPages = Math.max(1, Math.ceil(totalCount / PAGE_SIZE));

  function voltarSeEsvaziou() {
    if (planos.length === 1 && page > 1) setPage((p) => p - 1);
  }

  function abrirForm(plano: PlanoCobranca | null) {
    setEditando(plano);
    setFormKey((k) => k + 1);
    setFormAberto(true);
  }

  return (
    <div className="p-4 md:p-8 space-y-6">
      <header className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
        <div className="space-y-3">
          <h1 className="font-heading text-[28px] md:text-[34px] tracking-tight text-tinta leading-[1.15]">
            Planos de cobrança
          </h1>
          <div className="h-px w-10 bg-ferrugem" />
          <p className="text-sm text-muted-foreground max-w-xl">
            O contrato financeiro de cada aluno: valor, dia do vencimento,
            desconto e vigência. É daqui que saem as faturas mensais.
          </p>
        </div>
        <Button onClick={() => abrirForm(null)}>Novo plano</Button>
      </header>

      <FinanceiroTabs />

      <PlanoCobrancaFormDialog
        key={formKey}
        open={formAberto}
        onOpenChange={setFormAberto}
        plano={editando}
      />

      <div className="flex flex-wrap gap-4 items-center">
        <Input
          className="w-56"
          placeholder="Buscar por aluno ou matrícula"
          value={busca}
          onChange={(e) => setBusca(e.target.value)}
        />
        <div className="flex items-center gap-2">
          <Switch
            id="mostrar-encerrados"
            checked={mostrarEncerrados}
            onCheckedChange={(valor) => {
              setMostrarEncerrados(valor);
              setPage(1);
            }}
          />
          <Label
            htmlFor="mostrar-encerrados"
            className="text-[11px] uppercase tracking-[0.18em] text-sepia"
          >
            Mostrar encerrados
          </Label>
        </div>
      </div>

      {planosQuery.isLoading ? (
        <div className="space-y-2">
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-10 w-full" />
        </div>
      ) : planosQuery.isError ? (
        <p className="text-sm text-destructive">
          Não foi possível carregar os planos. Recarregue a página antes de
          cadastrar — o contrato do aluno pode já existir.
        </p>
      ) : planos.length === 0 ? (
        <div className="rounded-lg border border-border bg-paper p-6 space-y-2">
          <p className="font-heading text-lg text-tinta">
            {mostrarEncerrados
              ? "Nenhum plano encerrado"
              : "Nenhum plano ativo"}
          </p>
          <p className="text-sm text-sepia max-w-xl">
            {mostrarEncerrados
              ? "Nenhum contrato foi encerrado. Desligue o filtro para ver os que estão valendo."
              : 'Use "Novo plano" para cadastrar o contrato do primeiro aluno — valor, dia de vencimento e vigência.'}
          </p>
        </div>
      ) : (
        <>
          <div className="rounded-lg border border-border bg-paper overflow-hidden">
            <Table>
              <TableHeader>
                <TableRow>
                  {/* Headers em eyebrow mono — padrão do DESIGN.md §7.1.
                      Em mobile ficam só Aluno + Efetivo + ⋯: efetivo é o
                      que a escola cobra de fato; mensalidade cheia e
                      desconto são a conta que leva até ele. Vencimento e
                      vigência só em lg — com os dois em md as sete
                      colunas estouravam os ~462px que sobram da sidebar
                      (medido). */}
                  <TableHead className="text-[11px] uppercase tracking-[0.15em] text-sepia font-normal">Aluno</TableHead>
                  <TableHead className="hidden sm:table-cell text-right text-[11px] uppercase tracking-[0.15em] text-sepia font-normal">
                    Mensalidade
                  </TableHead>
                  <TableHead className="hidden sm:table-cell text-right text-[11px] uppercase tracking-[0.15em] text-sepia font-normal">
                    Desconto
                  </TableHead>
                  <TableHead className="text-right text-[11px] uppercase tracking-[0.15em] text-sepia font-normal">Efetivo</TableHead>
                  <TableHead className="hidden lg:table-cell text-[11px] uppercase tracking-[0.15em] text-sepia font-normal">
                    Vencimento
                  </TableHead>
                  <TableHead className="hidden lg:table-cell text-[11px] uppercase tracking-[0.15em] text-sepia font-normal">
                    Vigência
                  </TableHead>
                  <TableHead className="w-10" />
                </TableRow>
              </TableHeader>
              <TableBody>
                {planos.map((plano) => (
                  <TableRow
                    key={plano.id}
                    className="cursor-pointer"
                    onClick={() => abrirForm(plano)}
                  >
                    <TableCell className="whitespace-normal">
                      {plano.aluno_nome}
                      {!plano.ativo && (
                        <span className="ml-2 text-[11px] uppercase tracking-[0.14em] text-sepia">
                          [ encerrado ]
                        </span>
                      )}
                    </TableCell>
                    <TableCell className="hidden sm:table-cell text-right">
                      {formatarBRL(plano.valor_mensalidade)}
                    </TableCell>
                    <TableCell className="hidden sm:table-cell text-right">
                      {descricaoDesconto(plano)}
                    </TableCell>
                    <TableCell className="text-right font-heading">
                      {formatarBRL(plano.valor_efetivo)}
                    </TableCell>
                    <TableCell className="hidden lg:table-cell">
                      dia {plano.dia_vencimento}
                    </TableCell>
                    <TableCell className="hidden lg:table-cell text-sepia">
                      {descricaoVigencia(plano)}
                    </TableCell>
                    <TableCell onClick={(e) => e.stopPropagation()}>
                      <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                          <Button
                            variant="ghost"
                            size="icon-sm"
                            aria-label="Ações do plano"
                          >
                            ⋯
                          </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end">
                          <DropdownMenuItem onClick={() => abrirForm(plano)}>
                            Editar
                          </DropdownMenuItem>
                          {plano.ativo ? (
                            <DropdownMenuItem
                              onClick={() =>
                                desativar.mutate(plano.id, {
                                  onSuccess: voltarSeEsvaziou,
                                })
                              }
                            >
                              Encerrar
                            </DropdownMenuItem>
                          ) : (
                            <DropdownMenuItem
                              onClick={() =>
                                reativar.mutate(plano.id, {
                                  onSuccess: voltarSeEsvaziou,
                                })
                              }
                            >
                              Reativar
                            </DropdownMenuItem>
                          )}
                        </DropdownMenuContent>
                      </DropdownMenu>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
          <Pagination
            page={page}
            totalPages={totalPages}
            onPageChange={setPage}
            totalLabel={`${totalCount} plano(s)`}
          />
        </>
      )}
    </div>
  );
}
