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

// Confirmação de "exclusão" — na prática soft delete. O endpoint
// DELETE do AlunoViewSet marca `ativo=False` em vez de remover a
// linha, preservando o histórico (ocorrências, presença, avaliações).
// AlertDialog do shadcn cuida de foco e acessibilidade (ESC fecha,
// click fora fecha, Enter confirma).
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
          <AlertDialogTitle>Inativar aluno?</AlertDialogTitle>
          <AlertDialogDescription>
            <strong>{aluno?.nome_completo}</strong> será marcado como
            inativo e deixará de aparecer nas listagens e seleções do
            dia a dia. O histórico (ocorrências, presença, avaliações)
            permanece preservado. Você pode reativá-lo a qualquer
            momento ligando o filtro "Mostrar inativos" na página de
            Alunos.
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
            {deleteMutation.isPending ? "Inativando..." : "Inativar"}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
