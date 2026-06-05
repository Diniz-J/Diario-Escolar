import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useAuth } from "@/features/auth/useAuth";
import { usePermissoes } from "@/features/auth/usePermissoes";
import {
  useExportar,
  type EntidadeImportExport,
} from "@/features/import-export/hooks";

interface ExportarMenuProps {
  entidade: EntidadeImportExport;
}

// Dropdown "Exportar" — CSV ou XLSX. Só aparece pra admin/diretor
// (`podeModificarCadastros`) porque planilha administrativa raramente
// faz sentido pra professor/inspetor. O backend ainda valida via
// `READ_PERMISSION` do ViewSet — esconder é UX, não segurança.
//
// `escolaId` vem do JWT do usuário logado. Admin global (sem escola no
// perfil) usa a tela /import pra escolher a escola alvo — esconder
// aqui evita confusão.
export function ExportarMenu({ entidade }: ExportarMenuProps) {
  const { user } = useAuth();
  const { podeModificarCadastros } = usePermissoes();
  const mutation = useExportar();

  if (!podeModificarCadastros) return null;
  if (!user?.escola_id) return null;

  const escolaId = user.escola_id;

  function exportar(formato: "csv" | "xlsx") {
    mutation.mutate(
      { entidade, formato, escolaId },
      {
        onSuccess: () =>
          toast.success(`Arquivo ${entidade}.${formato} gerado.`),
        onError: () => toast.error("Não foi possível exportar."),
      },
    );
  }

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="outline" disabled={mutation.isPending}>
          {mutation.isPending ? "Gerando..." : "Exportar"}
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <DropdownMenuItem onClick={() => exportar("csv")}>
          CSV
        </DropdownMenuItem>
        <DropdownMenuItem onClick={() => exportar("xlsx")}>
          Excel (.xlsx)
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
