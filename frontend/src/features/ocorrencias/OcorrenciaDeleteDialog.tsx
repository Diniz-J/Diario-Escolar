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
import type { Ocorrencia } from "@/types/api";

import { useDeleteOcorrencia } from "./hooks";

interface OcorrenciaDeleteDialogProps {
  ocorrencia: Ocorrencia | null;
  onOpenChange: (open: boolean) => void;
  // Disparado apenas quando a exclusão é confirmada com sucesso.
  // Útil pra páginas de detalhe redirecionarem após excluir.
  onDeleted?: () => void;
}

export function OcorrenciaDeleteDialog({
  ocorrencia,
  onOpenChange,
  onDeleted,
}: OcorrenciaDeleteDialogProps) {
  const deleteMutation = useDeleteOcorrencia();

  async function handleConfirm() {
    if (!ocorrencia) return;
    try {
      await deleteMutation.mutateAsync(ocorrencia.id);
      onOpenChange(false);
      onDeleted?.();
    } catch (err) {
      console.error(err);
    }
  }

  return (
    <AlertDialog
      open={ocorrencia != null}
      onOpenChange={onOpenChange}
    >
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Excluir ocorrência?</AlertDialogTitle>
          <AlertDialogDescription>
            Esta ação removerá a ocorrência permanentemente. Se quiser
            preservar o histórico, considere arquivar em vez de excluir.
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
