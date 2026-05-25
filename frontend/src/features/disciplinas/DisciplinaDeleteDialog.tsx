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
import type { Disciplina } from "@/types/api";

import { useDeleteDisciplina } from "./hooks";

interface DisciplinaDeleteDialogProps {
  disciplina: Disciplina | null;
  onOpenChange: (open: boolean) => void;
}

export function DisciplinaDeleteDialog({
  disciplina,
  onOpenChange,
}: DisciplinaDeleteDialogProps) {
  const deleteMutation = useDeleteDisciplina();

  async function handleConfirm() {
    if (!disciplina) return;
    try {
      await deleteMutation.mutateAsync(disciplina.id);
      onOpenChange(false);
    } catch (err) {
      console.error(err);
    }
  }

  return (
    <AlertDialog open={disciplina != null} onOpenChange={onOpenChange}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Excluir disciplina?</AlertDialogTitle>
          <AlertDialogDescription>
            Esta ação removerá <strong>{disciplina?.nome}</strong>{" "}
            permanentemente. Disciplinas vinculadas a tarefas ou professores
            não podem ser excluídas.
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
