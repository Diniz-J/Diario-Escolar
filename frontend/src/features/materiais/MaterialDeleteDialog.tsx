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
import type { Material } from "@/types/api";

import { useDespublicarMaterial } from "./hooks";

interface MaterialDeleteDialogProps {
  material: Material | null;
  onOpenChange: (open: boolean) => void;
  // Chamado depois de despublicar — a página usa pra não ficar numa página
  // que deixou de existir (o item saiu do filtro `ativo=true`).
  onDespublicado?: () => void;
}

// "Despublicar" — na prática soft delete: o DELETE do backend marca
// `ativo=false`. O material some do portal dos pais e fica no histórico.
export function MaterialDeleteDialog({
  material,
  onOpenChange,
  onDespublicado,
}: MaterialDeleteDialogProps) {
  const despublicarMutation = useDespublicarMaterial();

  async function handleConfirm() {
    if (!material) return;
    try {
      await despublicarMutation.mutateAsync(material.id);
      onDespublicado?.();
      onOpenChange(false);
    } catch (err) {
      console.error(err);
    }
  }

  return (
    <AlertDialog open={material != null} onOpenChange={onOpenChange}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Despublicar material?</AlertDialogTitle>
          <AlertDialogDescription>
            <strong>{material?.titulo}</strong> deixa de aparecer no portal
            para os responsáveis. O registro fica no histórico e pode ser
            publicado de novo ligando "Mostrar despublicados".
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel disabled={despublicarMutation.isPending}>
            Cancelar
          </AlertDialogCancel>
          <AlertDialogAction
            onClick={handleConfirm}
            disabled={despublicarMutation.isPending}
            className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
          >
            {despublicarMutation.isPending ? "Despublicando..." : "Despublicar"}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
