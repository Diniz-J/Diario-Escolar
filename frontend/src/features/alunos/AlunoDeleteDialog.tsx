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
import type { Aluno } from "@/types/api";

import { useDeleteAluno } from "./hooks";

interface AlunoDeleteDialogProps {
  aluno: Aluno | null;
  onOpenChange: (open: boolean) => void;
}

// Confirmação de exclusão. AlertDialog do shadcn cuida de foco e
// acessibilidade (ESC fecha, click fora fecha, Enter confirma).
export function AlunoDeleteDialog({
  aluno,
  onOpenChange,
}: AlunoDeleteDialogProps) {
  const deleteMutation = useDeleteAluno();

  async function handleConfirm() {
    if (!aluno) return;
    try {
      await deleteMutation.mutateAsync(aluno.id);
      onOpenChange(false);
    } catch (err) {
      console.error(err);
    }
  }

  return (
    <AlertDialog open={aluno != null} onOpenChange={onOpenChange}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Excluir aluno?</AlertDialogTitle>
          <AlertDialogDescription>
            Esta ação removerá <strong>{aluno?.nome_completo}</strong>{" "}
            permanentemente. Alunos com ocorrências ou registros de
            presença não podem ser excluídos.
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
