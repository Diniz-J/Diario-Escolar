import { useMemo } from "react";
import { Link } from "react-router-dom";

import { Skeleton } from "@/components/ui/skeleton";
import { useAlunos } from "@/features/alunos/hooks";
import { useOcorrencias } from "@/features/ocorrencias/hooks";
import type { OcorrenciaStatus } from "@/types/api";

interface UltimasOcorrenciasCardProps {
  turmaFiltrada?: number | null;
}

// Mapeia status → cores na paleta da marca (em vez do red/amber/green
// genérico). Mantém a leitura "ferrugem = atenção, olive = resolvido"
// coerente com o resto do app. Cada entrada gera classes Tailwind via
// arbitrary values pra puxar diretamente das CSS variables.
const STATUS_STYLE: Record<OcorrenciaStatus, string> = {
  // ferrugem clarinho de fundo + ferrugem escuro de texto.
  aberta: "bg-[#F4DAD3] text-[#7C2D1A]",
  // mostarda quente — diferencia de "aberta" sem perder a sensação de pendente.
  em_andamento: "bg-[#FCE7BC] text-[#854D0E]",
  // olive — sensação de "consolidado, ok".
  resolvida: "bg-[#D7DCC1] text-[#3A4524]",
  // muted — paleta neutra da própria marca.
  arquivada: "bg-muted text-sepia",
};

function formatarDataBR(iso: string): string {
  const [ano, mes, dia] = iso.split("-");
  return `${dia}/${mes}/${ano}`;
}

// Lista as 5 ocorrências mais recentes da escola (ou da turma filtrada).
// O backend já devolve ordenado por data desc, então é só fatiar.
export function UltimasOcorrenciasCard({
  turmaFiltrada,
}: UltimasOcorrenciasCardProps) {
  const ocorrenciasQuery = useOcorrencias(
    turmaFiltrada ? { turma: turmaFiltrada } : {},
  );
  // Sem filtro de `ativo` — precisamos resolver nome mesmo de alunos
  // que foram desativados depois da ocorrência.
  const alunosQuery = useAlunos();

  const carregando = ocorrenciasQuery.isLoading || alunosQuery.isLoading;

  const alunosPorId = useMemo(() => {
    const m = new Map<number, string>();
    alunosQuery.data?.forEach((a) => m.set(a.id, a.nome_completo));
    return m;
  }, [alunosQuery.data]);

  const recentes = useMemo(
    () => ocorrenciasQuery.data?.slice(0, 5) ?? [],
    [ocorrenciasQuery.data],
  );

  return (
    <div className="h-full bg-paper rounded-lg p-6 border border-border">
      <p className="text-[11px] uppercase tracking-[0.18em] text-sepia mb-4">
        Últimas ocorrências
      </p>
      {carregando ? (
        <div className="space-y-2">
          <Skeleton className="h-5 w-full" />
          <Skeleton className="h-5 w-full" />
          <Skeleton className="h-5 w-3/4" />
        </div>
      ) : recentes.length === 0 ? (
        <p className="text-sm text-sepia">Nenhuma ocorrência registrada.</p>
      ) : (
        <ul className="space-y-2 text-sm">
          {recentes.map((o) => (
            <li
              key={o.id}
              className="flex items-center justify-between gap-3"
            >
              <Link
                to={`/ocorrencias/${o.id}`}
                className="truncate flex-1 min-w-0 text-tinta hover:text-ferrugem transition-colors"
                title={alunosPorId.get(o.aluno) ?? `Aluno #${o.aluno}`}
              >
                <span className="text-sepia tabular-nums mr-2 font-mono text-xs">
                  {formatarDataBR(o.data_ocorrencia)}
                </span>
                <span>
                  {alunosPorId.get(o.aluno) ?? `Aluno #${o.aluno}`}
                </span>
              </Link>
              <span
                className={`text-[10px] uppercase tracking-wider px-2 py-0.5 rounded shrink-0 ${STATUS_STYLE[o.status]}`}
              >
                {o.status_display}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
