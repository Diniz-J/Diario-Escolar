import { Button } from "@/components/ui/button";

// Paginação enxuta — botões anterior/próxima + indicador "X de Y" no meio.
// Sumir quando só há uma página (ou nenhuma) — sem precisar tomar decisão
// no callsite.
//
// Decisão consciente de NÃO renderizar a sequência 1/2/3.../N: tabelas
// administrativas do Diário ficam mais limpas com prev/next e o usuário
// raramente "salta" pra uma página específica — a busca/filtro server-side
// já atende esse caso. Se um dia virar requisito, dá pra ampliar aqui.
interface PaginationProps {
  page: number;
  totalPages: number;
  onPageChange: (page: number) => void;
  // Opcionais — mostrados como microtípico ao lado: "32 alunos no total".
  totalLabel?: string;
}

export function Pagination({
  page,
  totalPages,
  onPageChange,
  totalLabel,
}: PaginationProps) {
  if (totalPages <= 1) return null;

  return (
    <div className="flex items-center justify-between gap-3 py-2">
      {totalLabel ? (
        <p className="text-[11px] uppercase tracking-[0.18em] text-sepia">
          {totalLabel}
        </p>
      ) : (
        <span />
      )}
      <div className="flex items-center gap-3">
        <Button
          type="button"
          variant="ghost"
          size="sm"
          disabled={page <= 1}
          onClick={() => onPageChange(page - 1)}
        >
          ← Anterior
        </Button>
        <span className="text-[11px] uppercase tracking-[0.15em] text-sepia tabular-nums">
          {page} de {totalPages}
        </span>
        <Button
          type="button"
          variant="ghost"
          size="sm"
          disabled={page >= totalPages}
          onClick={() => onPageChange(page + 1)}
        >
          Próxima →
        </Button>
      </div>
    </div>
  );
}
