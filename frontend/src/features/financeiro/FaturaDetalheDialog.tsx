import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Skeleton } from "@/components/ui/skeleton";
import { formatarDataPura } from "@/lib/datas";
import type { Fatura } from "@/types/api";

import {
  METODO_LABEL,
  STATUS_FATURA,
  formatarBRL,
  formatarCompetencia,
  podeEmitirCobranca,
} from "./constants";
import {
  useEstornarPagamento,
  useFaturaItens,
  usePagamentosDaFatura,
} from "./hooks";

interface FaturaDetalheDialogProps {
  fatura: Fatura | null;
  onOpenChange: (open: boolean) => void;
  // A página é quem abre o dialog de pagamento: dialog dentro de dialog
  // briga por foco e trava o scroll.
  onRegistrarPagamento: (fatura: Fatura) => void;
  // Mesma razão: a confirmação de emissão é outro dialog, e quem o abre é
  // a página.
  onEmitirCobranca: (fatura: Fatura) => void;
}

const LABEL_CLASS = "text-[11px] uppercase tracking-[0.18em] text-sepia";

export function FaturaDetalheDialog({
  fatura,
  onOpenChange,
  onRegistrarPagamento,
  onEmitirCobranca,
}: FaturaDetalheDialogProps) {
  const itensQuery = useFaturaItens(fatura?.id ?? null);
  const pagamentosQuery = usePagamentosDaFatura(fatura?.id ?? null);
  const estornar = useEstornarPagamento();

  const status = fatura ? STATUS_FATURA[fatura.status] : null;
  const emAberto =
    fatura != null &&
    fatura.status !== "cancelado" &&
    Number(fatura.saldo) > 0;

  return (
    <Dialog open={fatura != null} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="font-heading tracking-tight">
            {fatura ? fatura.aluno_nome : ""}
          </DialogTitle>
          <DialogDescription>
            {fatura
              ? `Competência ${formatarCompetencia(fatura.competencia)} · vence em ${formatarDataPura(fatura.vencimento)}`
              : ""}
          </DialogDescription>
        </DialogHeader>

        {fatura && status && (
          <div className="space-y-5">
            <div className="flex items-center gap-3">
              <span
                className={`inline-flex rounded px-2 py-0.5 text-[11px] uppercase tracking-[0.14em] ${status.className}`}
              >
                {status.label}
              </span>
              {fatura.dias_atraso > 0 && fatura.status !== "cancelado" && (
                <span className="text-xs text-sepia">
                  {fatura.dias_atraso} dia(s) de atraso
                </span>
              )}
            </div>

            <dl className="grid grid-cols-2 gap-x-4 gap-y-2 rounded-md bg-paper p-3 text-sm">
              <dt className={LABEL_CLASS}>Valor</dt>
              <dd className="text-right">{formatarBRL(fatura.valor)}</dd>
              <dt className={LABEL_CLASS}>Pago</dt>
              <dd className="text-right">{formatarBRL(fatura.valor_pago)}</dd>
              <dt className={LABEL_CLASS}>Saldo</dt>
              <dd className="text-right">{formatarBRL(fatura.saldo)}</dd>
              {Number(fatura.encargos) > 0 && (
                <>
                  <dt className={LABEL_CLASS}>Multa e juros de hoje</dt>
                  <dd className="text-right">
                    {formatarBRL(fatura.encargos)}
                  </dd>
                  <dt className={LABEL_CLASS}>A cobrar hoje</dt>
                  <dd className="text-right font-heading">
                    {formatarBRL(fatura.valor_atualizado)}
                  </dd>
                </>
              )}
              {fatura.data_pagamento && (
                <>
                  <dt className={LABEL_CLASS}>Quitada em</dt>
                  <dd className="text-right">
                    {formatarDataPura(fatura.data_pagamento)}
                  </dd>
                </>
              )}
            </dl>

            <section className="space-y-2">
              <h3 className={LABEL_CLASS}>Composição</h3>
              {itensQuery.isLoading ? (
                <Skeleton className="h-10 w-full" />
              ) : (itensQuery.data ?? []).length === 0 ? (
                <p className="text-sm text-muted-foreground">
                  Sem detalhamento lançado.
                </p>
              ) : (
                <ul className="divide-y divide-border text-sm">
                  {(itensQuery.data ?? []).map((item) => (
                    <li
                      key={item.id}
                      className="flex justify-between gap-3 py-1.5"
                    >
                      <span>{item.descricao}</span>
                      <span className="text-sepia">
                        {formatarBRL(item.valor)}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </section>

            <section className="space-y-2">
              <h3 className={LABEL_CLASS}>Pagamentos</h3>
              {pagamentosQuery.isLoading ? (
                <Skeleton className="h-10 w-full" />
              ) : (pagamentosQuery.data ?? []).length === 0 ? (
                <p className="text-sm text-muted-foreground">
                  Nenhum pagamento registrado.
                </p>
              ) : (
                <ul className="divide-y divide-border text-sm">
                  {(pagamentosQuery.data ?? []).map((pagamento) => (
                    <li
                      key={pagamento.id}
                      className="flex items-center justify-between gap-3 py-1.5"
                    >
                      <span>
                        {formatarDataPura(pagamento.data)} ·{" "}
                        {METODO_LABEL[pagamento.metodo]}
                        {pagamento.referencia_externa && (
                          <span className="text-sepia">
                            {" "}
                            · {pagamento.referencia_externa}
                          </span>
                        )}
                      </span>
                      <span className="flex items-center gap-3">
                        <span>{formatarBRL(pagamento.valor)}</span>
                        <Button
                          type="button"
                          variant="ghost"
                          size="sm"
                          disabled={estornar.isPending}
                          onClick={() => estornar.mutate(pagamento.id)}
                        >
                          Estornar
                        </Button>
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </section>
          </div>
        )}

        {/* O link é o resultado visível da emissão: é ele que a secretaria
            manda pra família. Sem isto, emitir não mostraria nada na tela.
            `noreferrer` junto do `_blank` porque a página é de terceiro. */}
        {fatura?.link_pagamento && (
          <section className="space-y-1">
            <h3 className={LABEL_CLASS}>Link de pagamento</h3>
            <a
              href={fatura.link_pagamento}
              target="_blank"
              rel="noopener noreferrer"
              className="text-sm text-olive underline break-all"
            >
              {fatura.link_pagamento}
            </a>
          </section>
        )}

        <DialogFooter>
          <Button
            type="button"
            variant="ghost"
            onClick={() => onOpenChange(false)}
          >
            Fechar
          </Button>
          {fatura && podeEmitirCobranca(fatura) && (
            <Button
              type="button"
              variant="outline"
              onClick={() => onEmitirCobranca(fatura)}
            >
              Emitir cobrança
            </Button>
          )}
          {fatura && emAberto && (
            <Button type="button" onClick={() => onRegistrarPagamento(fatura)}>
              Registrar pagamento
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
