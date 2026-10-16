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
import type { Fatura } from "@/types/api";

import { formatarBRL, formatarCompetencia } from "./constants";
import { mensagemDeErro } from "./erros";
import { useCancelarFatura } from "./hooks";

interface FaturaCancelDialogProps {
  fatura: Fatura | null;
  onOpenChange: (open: boolean) => void;
  // Avisa a página pra voltar uma página se a listagem esvaziou.
  onCancelada?: () => void;
}

// Cancelar não apaga: fatura é documento financeiro, e o `DELETE` do
// backend move o status pra `cancelado`. Com pagamento registrado o
// backend recusa (400) — o caminho é estornar o pagamento primeiro, e a
// mensagem dele é mostrada aqui.
export function FaturaCancelDialog({
  fatura,
  onOpenChange,
  onCancelada,
}: FaturaCancelDialogProps) {
  const cancelar = useCancelarFatura();
  const [erro, setErro] = useState<string | null>(null);

  async function confirmar() {
    setErro(null);
    if (!fatura) return;
    try {
      await cancelar.mutateAsync(fatura.id);
      onCancelada?.();
      onOpenChange(false);
    } catch (err) {
      setErro(mensagemDeErro(err, "Não foi possível cancelar a fatura."));
    }
  }

  return (
    <Dialog open={fatura != null} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle className="font-heading tracking-tight">
            Cancelar fatura
          </DialogTitle>
          <DialogDescription>
            {fatura
              ? `${fatura.aluno_nome} — ${formatarCompetencia(fatura.competencia)}, ${formatarBRL(fatura.valor)}`
              : ""}
          </DialogDescription>
        </DialogHeader>

        <p className="text-sm text-muted-foreground">
          A fatura passa a constar como cancelada e para de ser cobrada. O
          registro continua no histórico — nada é apagado.
        </p>

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
            disabled={cancelar.isPending}
          >
            Voltar
          </Button>
          <Button
            type="button"
            variant="destructive"
            onClick={confirmar}
            disabled={cancelar.isPending}
          >
            {cancelar.isPending ? "Cancelando..." : "Cancelar fatura"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
