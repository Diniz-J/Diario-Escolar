import { useState } from "react";
import { Link, useParams } from "react-router-dom";

import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { MetricCard } from "@/features/dashboard/MetricCard";
import { FaturaCancelDialog } from "@/features/financeiro/FaturaCancelDialog";
import { FaturaDetalheDialog } from "@/features/financeiro/FaturaDetalheDialog";
import { PagamentoFormDialog } from "@/features/financeiro/PagamentoFormDialog";
import { PlanoCobrancaFormDialog } from "@/features/financeiro/PlanoCobrancaFormDialog";
import {
  METODO_LABEL,
  STATUS_FATURA,
  formatarBRL,
  formatarCompetencia,
  formatarData,
} from "@/features/financeiro/constants";
import { useFichaFinanceira } from "@/features/financeiro/hooks";
import type { Fatura, PlanoCobranca } from "@/types/api";

const EYEBROW = "text-[11px] uppercase tracking-[0.18em] text-sepia";

function descricaoDesconto(plano: PlanoCobranca): string {
  if (plano.desconto_tipo === "percentual") {
    return `${Number(plano.desconto_valor).toLocaleString("pt-BR")}% de desconto`;
  }
  if (plano.desconto_tipo === "fixo") {
    return `${formatarBRL(plano.desconto_valor)} de desconto`;
  }
  return "sem desconto";
}

// Ficha financeira do aluno — o histórico consolidado: contratos, faturas
// e pagamentos num lugar só, com os totais que respondem "quanto este
// aluno deve".
//
// Os totais vêm somados do backend (`GET /financeiro/alunos/<id>/`), em
// Decimal: somar `saldo` de várias faturas em JavaScript perderia centavo
// em ponto flutuante, e o piso por fatura (pagamento a mais não abate
// dívida de outra) é regra de negócio, não de exibição. Ver
// FINANCEIRO.md §7.
export function FichaFinanceiraPage() {
  const { id } = useParams<{ id: string }>();
  const alunoId = id ? Number(id) : null;
  const fichaQuery = useFichaFinanceira(alunoId);

  const [detalhe, setDetalhe] = useState<Fatura | null>(null);
  const [pagando, setPagando] = useState<Fatura | null>(null);
  const [cancelando, setCancelando] = useState<Fatura | null>(null);
  const [planoEditando, setPlanoEditando] = useState<PlanoCobranca | null>(null);
  const [planoFormKey, setPlanoFormKey] = useState(0);

  function registrarPagamento(fatura: Fatura) {
    setDetalhe(null);
    setPagando(fatura);
  }

  function abrirPlano(plano: PlanoCobranca) {
    setPlanoEditando(plano);
    setPlanoFormKey((k) => k + 1);
  }

  if (fichaQuery.isLoading) {
    return (
      <div className="p-4 md:p-8 space-y-6">
        <Skeleton className="h-10 w-64" />
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <Skeleton className="h-32" />
          <Skeleton className="h-32" />
          <Skeleton className="h-32" />
          <Skeleton className="h-32" />
        </div>
      </div>
    );
  }

  if (fichaQuery.isError || !fichaQuery.data) {
    return (
      <div className="p-4 md:p-8 space-y-4">
        <p className="text-sm text-muted-foreground">
          Não foi possível carregar a ficha financeira deste aluno.
        </p>
        <Link to="/financeiro" className="text-sm text-ferrugem underline">
          Voltar para o financeiro
        </Link>
      </div>
    );
  }

  const { aluno, totais, planos, faturas, pagamentos } = fichaQuery.data;
  const temDivida = Number(totais.em_aberto) > 0;
  const temVencido = Number(totais.vencido) > 0;

  return (
    <div className="p-4 md:p-8 space-y-8">
      <header className="space-y-3">
        <Link to="/financeiro" className={`${EYEBROW} hover:text-tinta`}>
          ← Financeiro
        </Link>
        <h1 className="font-heading text-[28px] md:text-[34px] tracking-tight text-tinta leading-[1.15]">
          {aluno.nome_completo}
        </h1>
        <div className="h-px w-10 bg-ferrugem" />
        <p className="text-sm text-muted-foreground">
          Matrícula {aluno.matricula} · {aluno.turma}
          {!aluno.ativo && " · aluno inativo"}
        </p>
      </header>

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
      />
      <PlanoCobrancaFormDialog
        key={planoFormKey}
        open={planoEditando != null}
        onOpenChange={(aberto) => !aberto && setPlanoEditando(null)}
        plano={planoEditando}
      />

      <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <MetricCard
          titulo="Em aberto"
          valor={formatarBRL(totais.em_aberto)}
          sublinha={`${totais.faturas_abertas} fatura(s)`}
          tomDestaque={temDivida}
        />
        <MetricCard
          titulo="Vencido"
          valor={formatarBRL(totais.vencido)}
          tomDestaque={temVencido}
        />
        <MetricCard
          titulo="A cobrar hoje"
          valor={formatarBRL(totais.a_cobrar_hoje)}
          sublinha={
            Number(totais.encargos_hoje) > 0
              ? `inclui ${formatarBRL(totais.encargos_hoje)} de multa e juros`
              : "sem multa ou juros"
          }
        />
        <MetricCard
          titulo="Pago no ano"
          valor={formatarBRL(totais.pago_no_ano)}
        />
      </section>

      <section className="space-y-3">
        <h2 className="font-heading text-[20px] tracking-tight text-tinta">
          Contratos
        </h2>
        {planos.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            Nenhum plano de cobrança cadastrado para este aluno.
          </p>
        ) : (
          <ul className="space-y-2">
            {planos.map((plano) => (
              <li
                key={plano.id}
                className="flex flex-wrap items-baseline justify-between gap-3 rounded-md border border-border bg-paper p-4"
              >
                <div className="space-y-1">
                  <p className="font-heading text-[18px] text-tinta">
                    {formatarBRL(plano.valor_efetivo)}
                    <span className="ml-2 text-xs text-sepia">
                      / mês · vence dia {plano.dia_vencimento}
                    </span>
                  </p>
                  <p className="text-xs text-sepia">
                    {descricaoDesconto(plano)} ·{" "}
                    {plano.vigencia_fim
                      ? `${formatarData(plano.vigencia_inicio)} a ${formatarData(plano.vigencia_fim)}`
                      : `desde ${formatarData(plano.vigencia_inicio)}`}
                    {!plano.ativo && " · encerrado"}
                  </p>
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => abrirPlano(plano)}
                >
                  Editar
                </Button>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="space-y-3">
        <h2 className="font-heading text-[20px] tracking-tight text-tinta">
          Faturas
        </h2>
        {faturas.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            Nenhuma fatura emitida. A geração mensal cria a partir do
            contrato.
          </p>
        ) : (
          <div className="rounded-md border border-border bg-paper">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Competência</TableHead>
                  <TableHead className="hidden sm:table-cell">
                    Vencimento
                  </TableHead>
                  <TableHead className="text-right">Valor</TableHead>
                  <TableHead className="hidden md:table-cell text-right">
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
                        {formatarCompetencia(fatura.competencia)}
                      </TableCell>
                      <TableCell className="hidden sm:table-cell">
                        {formatarData(fatura.vencimento)}
                      </TableCell>
                      <TableCell className="text-right">
                        {formatarBRL(fatura.valor)}
                      </TableCell>
                      <TableCell className="hidden md:table-cell text-right">
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
        )}
      </section>

      <section className="space-y-3">
        <h2 className="font-heading text-[20px] tracking-tight text-tinta">
          Pagamentos
        </h2>
        {pagamentos.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            Nenhum pagamento registrado.
          </p>
        ) : (
          <ul className="divide-y divide-border rounded-md border border-border bg-paper px-4">
            {pagamentos.map((pagamento) => (
              <li
                key={pagamento.id}
                className="flex flex-wrap items-baseline justify-between gap-2 py-2.5 text-sm"
              >
                <span>
                  {formatarData(pagamento.data)} ·{" "}
                  {METODO_LABEL[pagamento.metodo]}
                  <span className="text-sepia">
                    {" "}
                    · competência {formatarCompetencia(pagamento.competencia)}
                  </span>
                  {pagamento.referencia_externa && (
                    <span className="text-sepia">
                      {" "}
                      · {pagamento.referencia_externa}
                    </span>
                  )}
                </span>
                <span className="font-heading">
                  {formatarBRL(pagamento.valor)}
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
