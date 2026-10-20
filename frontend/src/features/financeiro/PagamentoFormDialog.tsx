import { useState } from "react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { hojeISO } from "@/lib/datas";
import type { Fatura, PagamentoMetodo } from "@/types/api";

import {
  METODOS_PAGAMENTO,
  formatarBRL,
  formatarCompetencia,
} from "./constants";
import { mensagemDeErro } from "./erros";
import { useRegistrarPagamento } from "./hooks";

interface PagamentoFormDialogProps {
  // null = fechado. A página controla qual fatura está em jogo.
  fatura: Fatura | null;
  onOpenChange: (open: boolean) => void;
}

const LABEL_CLASS = "text-[11px] uppercase tracking-[0.18em] text-sepia";

export function PagamentoFormDialog({
  fatura,
  onOpenChange,
}: PagamentoFormDialogProps) {
  const registrar = useRegistrarPagamento();
  // Default = valor atualizado (saldo + multa e juros de hoje), que é o
  // que a escola efetivamente cobra. Vem calculado do backend.
  const [valor, setValor] = useState(fatura?.valor_atualizado ?? "");
  const [data, setData] = useState(hojeISO());
  const [metodo, setMetodo] = useState<PagamentoMetodo>("pix");
  const [referencia, setReferencia] = useState("");
  const [erro, setErro] = useState<string | null>(null);

  async function salvar() {
    setErro(null);
    if (!fatura) return;
    if (!valor.trim()) {
      setErro("Informe o valor recebido.");
      return;
    }
    try {
      await registrar.mutateAsync({
        fatura: fatura.id,
        valor: valor.trim(),
        data,
        metodo,
        ...(referencia.trim() && { referencia_externa: referencia.trim() }),
      });
      onOpenChange(false);
    } catch (err) {
      setErro(mensagemDeErro(err, "Não foi possível registrar o pagamento."));
    }
  }

  const temEncargos = fatura != null && Number(fatura.encargos) > 0;

  return (
    <Dialog open={fatura != null} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle className="font-heading tracking-tight">
            Registrar pagamento
          </DialogTitle>
          <DialogDescription>
            {fatura
              ? `${fatura.aluno_nome} — competência ${formatarCompetencia(fatura.competencia)}`
              : ""}
          </DialogDescription>
        </DialogHeader>

        {fatura && (
          <div className="space-y-4">
            <dl className="grid grid-cols-2 gap-x-4 gap-y-2 rounded-md bg-paper p-3 text-sm">
              <dt className={LABEL_CLASS}>Saldo</dt>
              <dd className="text-right">{formatarBRL(fatura.saldo)}</dd>
              {temEncargos && (
                <>
                  <dt className={LABEL_CLASS}>
                    Multa e juros ({fatura.dias_atraso} dias)
                  </dt>
                  <dd className="text-right">
                    {formatarBRL(fatura.encargos)}
                  </dd>
                </>
              )}
              <dt className={LABEL_CLASS}>A cobrar hoje</dt>
              <dd className="text-right font-heading">
                {formatarBRL(fatura.valor_atualizado)}
              </dd>
            </dl>

            <div className="space-y-2">
              <Label htmlFor="pagamento-valor" className={LABEL_CLASS}>
                Valor recebido (R$)
              </Label>
              <Input
                id="pagamento-valor"
                inputMode="decimal"
                value={valor}
                onChange={(e) => setValor(e.target.value)}
              />
              <p className="text-xs text-sepia">
                Pagamento parcial é aceito: a fatura continua em aberto com o
                saldo restante.
              </p>
            </div>

            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="pagamento-data" className={LABEL_CLASS}>
                  Data
                </Label>
                <Input
                  id="pagamento-data"
                  type="date"
                  max={hojeISO()}
                  value={data}
                  onChange={(e) => setData(e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <Label className={LABEL_CLASS}>Método</Label>
                <Select
                  value={metodo}
                  onValueChange={(v) => setMetodo(v as PagamentoMetodo)}
                >
                  <SelectTrigger className="w-full">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {METODOS_PAGAMENTO.map((m) => (
                      <SelectItem key={m.value} value={m.value}>
                        {m.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="pagamento-ref" className={LABEL_CLASS}>
                Referência (opcional)
              </Label>
              <Input
                id="pagamento-ref"
                maxLength={64}
                value={referencia}
                onChange={(e) => setReferencia(e.target.value)}
                placeholder="Id do comprovante ou da transação"
              />
            </div>
          </div>
        )}

        {erro && (
          <Alert variant="destructive">
            <AlertDescription>{erro}</AlertDescription>
          </Alert>
        )}

        <DialogFooter>
          <Button
            type="button"
            variant="ghost"
            onClick={() => onOpenChange(false)}
            disabled={registrar.isPending}
          >
            Cancelar
          </Button>
          <Button type="button" onClick={salvar} disabled={registrar.isPending}>
            {registrar.isPending ? "Registrando..." : "Registrar"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
