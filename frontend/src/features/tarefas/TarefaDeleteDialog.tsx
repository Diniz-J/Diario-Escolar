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
import type { Tarefa } from "@/types/api";

import { useDeleteTarefa } from "./hooks";

interface TarefaDeleteDialogProps {
  tarefa: Tarefa | null;
  onOpenChange: (open: boolean) => void;
  onDeleted?: () => void;
}

export function TarefaDeleteDialog({
  tarefa,
  onOpenChange,
  onDeleted,
}: TarefaDeleteDialogProps) {
  const deleteMutation = useDeleteTarefa();

  async function handleConfirm() {
    if (!tarefa) return;
    try {
      await deleteMutation.mutateAsync(tarefa.id);
      onOpenChange(false);
      onDeleted?.();
    } catch (err) {
      console.error(err);
    }
  }

  return (
    <AlertDialog open={tarefa != null} onOpenChange={onOpenChange}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Excluir tarefa?</AlertDialogTitle>
          <AlertDialogDescription>
            Esta ação removerá <strong>{tarefa?.titulo}</strong> e todas as
            entregas associadas dos alunos.
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
