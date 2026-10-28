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
import { useEmitirCobranca } from "./hooks";

interface FaturaEmitirDialogProps {
  fatura: Fatura | null;
  onOpenChange: (open: boolean) => void;
}

// Confirmação antes de emitir, no molde do `FaturaCancelDialog`, porque a
// ação **sai do sistema**: cria uma cobrança de verdade no provedor e é
// ele quem avisa o pagador (as notificações dele ficam ligadas de
// propósito — lembrete de vencimento é coisa que o Diário não faz). Não
// há desfazer prático: cancelar a fatura cancela a cobrança lá, mas o
// email que o provedor já mandou não volta.
//
// A mensagem de erro aparece aqui dentro, e não num toast, porque é ela
// que diz o que falta preencher — "o responsável está sem CPF", "este
// plano não tem pagador definido", "cobrança online não está
// configurada". Toast some; o `Alert` fica na tela junto do botão que
// falhou.
export function FaturaEmitirDialog({
  fatura,
  onOpenChange,
}: FaturaEmitirDialogProps) {
  const emitir = useEmitirCobranca();
  const [erro, setErro] = useState<string | null>(null);

  async function confirmar() {
    setErro(null);
    if (!fatura) return;
    try {
      await emitir.mutateAsync(fatura.id);
      onOpenChange(false);
    } catch (err) {
      setErro(mensagemDeErro(err, "Não foi possível emitir a cobrança."));
    }
  }

  return (
    <Dialog open={fatura != null} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle className="font-heading tracking-tight">
            Emitir cobrança
          </DialogTitle>
          <DialogDescription>
            {fatura
              ? `${fatura.aluno_nome} — ${formatarCompetencia(fatura.competencia)}, ${formatarBRL(fatura.valor)}`
              : ""}
          </DialogDescription>
        </DialogHeader>

        <p className="text-sm text-muted-foreground">
          A cobrança é criada no provedor de pagamento, que gera o link
          (Pix ou boleto, à escolha da família) e avisa o responsável. O
          link fica disponível no detalhe da fatura.
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
            disabled={emitir.isPending}
          >
            Voltar
          </Button>
          <Button type="button" onClick={confirmar} disabled={emitir.isPending}>
            {emitir.isPending ? "Emitindo..." : "Emitir cobrança"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
