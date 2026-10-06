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
import type { Comunicado } from "@/types/api";

import { useDeleteComunicado } from "./hooks";

interface ComunicadoDeleteDialogProps {
  comunicado: Comunicado | null;
  onOpenChange: (open: boolean) => void;
  onDeleted?: () => void;
}

export function ComunicadoDeleteDialog({
  comunicado,
  onOpenChange,
  onDeleted,
}: ComunicadoDeleteDialogProps) {
  const deleteMutation = useDeleteComunicado();

  async function handleConfirm() {
    if (!comunicado) return;
    try {
      await deleteMutation.mutateAsync(comunicado.id);
      onOpenChange(false);
      onDeleted?.();
    } catch (err) {
      console.error(err);
    }
  }

  return (
    <AlertDialog open={comunicado != null} onOpenChange={onOpenChange}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Excluir rascunho?</AlertDialogTitle>
          <AlertDialogDescription>
            O rascunho será removido permanentemente. Comunicados já
            enviados não podem ser excluídos — eles são o registro do que
            chegou aos responsáveis.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel disabled={deleteMutation.isPending}>
            Cancelar
          </AlertDialogCancel>
          <AlertDialogAction
            onClick={handleConfirm}
            disabled={deleteMutation.isPending}
            className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
          >
            {deleteMutation.isPending ? "Excluindo..." : "Excluir"}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
