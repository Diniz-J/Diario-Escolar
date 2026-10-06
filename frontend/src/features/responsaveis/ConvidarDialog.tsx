import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import type { ResponsavelStaff } from "@/types/api";

import { useConvidarResponsavel } from "./hooks";

interface ConvidarDialogProps {
  responsavel: ResponsavelStaff | null;
  onOpenChange: (open: boolean) => void;
}

/**
 * Confirmação do convite.
 *
 * Confirma porque manda email de verdade, e porque reenviar **invalida o
 * link pendente anterior** (`ConviteResponsavel.gerar` expira os
 * pendentes). Sem avisar, a secretaria reenviaria "pra garantir" e
 * derrubaria o link que o pai estava a ponto de usar.
 */
export function ConvidarDialog({
  responsavel,
  onOpenChange,
}: ConvidarDialogProps) {
  const convidar = useConvidarResponsavel();
  const jaConvidado = responsavel?.situacao === "convidado";

  async function handleConfirm() {
    if (!responsavel) return;
    try {
      await convidar.mutateAsync(responsavel.id);
      onOpenChange(false);
    } catch (err) {
      // O toast de erro (incluindo 400 de conta já ativa e 502 de email que
      // não saiu) vem do hook.
      console.error(err);
    }
  }

  return (
    <AlertDialog open={responsavel != null} onOpenChange={onOpenChange}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>
            {jaConvidado ? "Reenviar convite?" : "Enviar convite?"}
          </AlertDialogTitle>
          <AlertDialogDescription asChild>
            <div className="space-y-2">
              <p>
                O link de acesso ao portal será enviado para{" "}
                <strong className="text-foreground">
                  {responsavel?.email}
                </strong>
                . O link vale 7 dias.
              </p>
              {jaConvidado && (
                <p className="text-destructive">
                  Existe um convite pendente para este responsável. Reenviar
                  invalida o link anterior — se ele estiver a ponto de usar o
                  que recebeu, vai precisar do novo.
                </p>
              )}
            </div>
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel disabled={convidar.isPending}>
            Cancelar
          </AlertDialogCancel>
          <AlertDialogAction
            onClick={handleConfirm}
            disabled={convidar.isPending}
          >
            {convidar.isPending
              ? "Enviando..."
              : jaConvidado
                ? "Reenviar"
                : "Enviar convite"}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
