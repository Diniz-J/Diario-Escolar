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
import type { PlanoEnsino } from "@/types/api";

import { useDeletePlanoEnsino } from "./hooks";

interface PlanoEnsinoDeleteDialogProps {
  plano: PlanoEnsino | null;
  onOpenChange: (open: boolean) => void;
  onDeleted?: () => void;
}

export function PlanoEnsinoDeleteDialog({
  plano,
  onOpenChange,
  onDeleted,
}: PlanoEnsinoDeleteDialogProps) {
  const deleteMutation = useDeletePlanoEnsino();

  async function handleConfirm() {
    if (!plano) return;
    try {
      await deleteMutation.mutateAsync(plano.id);
      onOpenChange(false);
      onDeleted?.();
    } catch (err) {
      console.error(err);
    }
  }

  return (
    <AlertDialog open={plano != null} onOpenChange={onOpenChange}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Excluir plano de ensino?</AlertDialogTitle>
          <AlertDialogDescription>
            Esta ação removerá o plano permanentemente. Considere
            desativar (marcar como inativo) se quiser preservar o
            histórico.
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
