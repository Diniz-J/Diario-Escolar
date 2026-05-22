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
import type { Turma } from "@/types/api";

import { useDeleteTurma } from "./hooks";

interface TurmaDeleteDialogProps {
  turma: Turma | null;
  onOpenChange: (open: boolean) => void;
}

export function TurmaDeleteDialog({
  turma,
  onOpenChange,
}: TurmaDeleteDialogProps) {
  const deleteMutation = useDeleteTurma();

  async function handleConfirm() {
    if (!turma) return;
    try {
      await deleteMutation.mutateAsync(turma.id);
      onOpenChange(false);
    } catch (err) {
      console.error(err);
    }
  }

  return (
    <AlertDialog open={turma != null} onOpenChange={onOpenChange}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Excluir turma?</AlertDialogTitle>
          <AlertDialogDescription>
            Esta ação removerá <strong>{turma?.nome}</strong>{" "}
            permanentemente. Turmas com alunos vinculados não podem ser
            excluídas.
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
