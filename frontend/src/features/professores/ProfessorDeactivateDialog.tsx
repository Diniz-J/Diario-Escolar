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
import type { Professor } from "@/types/api";

import { useDeactivateProfessor } from "./hooks";

interface ProfessorDeactivateDialogProps {
  professor: Professor | null;
  onOpenChange: (open: boolean) => void;
}

// "Excluir" professor é sempre soft delete via `ativo=False` — preserva
// o histórico de tarefas/ocorrências/planos vinculados ao professor.
// Pra reativar, basta editar e mexer no campo `ativo` por outro fluxo
// (hoje apenas via Django Admin; tela de "Reativar" entra no backlog).
export function ProfessorDeactivateDialog({
  professor,
  onOpenChange,
}: ProfessorDeactivateDialogProps) {
  const mutation = useDeactivateProfessor();

  async function handleConfirm() {
    if (!professor) return;
    try {
      await mutation.mutateAsync(professor.id);
      onOpenChange(false);
    } catch (err) {
      console.error(err);
    }
  }

  return (
    <AlertDialog open={professor != null} onOpenChange={onOpenChange}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Excluir professor?</AlertDialogTitle>
          <AlertDialogDescription>
            O professor será marcado como inativo. O histórico (tarefas,
            ocorrências, planos de ensino) é preservado. Você pode
            reativar depois pelo Django Admin.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel disabled={mutation.isPending}>
            Cancelar
          </AlertDialogCancel>
          <AlertDialogAction
            onClick={handleConfirm}
            disabled={mutation.isPending}
            className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
          >
            {mutation.isPending ? "Excluindo..." : "Excluir"}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
