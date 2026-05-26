import { useMemo } from "react";
import { Link } from "react-router-dom";

import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useAlunos } from "@/features/alunos/hooks";
import { useOcorrencias } from "@/features/ocorrencias/hooks";
import type { OcorrenciaStatus } from "@/types/api";

interface UltimasOcorrenciasCardProps {
  turmaFiltrada?: number | null;
}

// Mapeia status → classes Tailwind do badge. Mantém a mesma paleta usada
// nas listagens (verde/azul/cinza) pra consistência visual.
const STATUS_BADGE: Record<OcorrenciaStatus, string> = {
  aberta:
    "text-red-700 bg-red-50 dark:bg-red-950 dark:text-red-300",
  em_andamento:
    "text-amber-700 bg-amber-50 dark:bg-amber-950 dark:text-amber-300",
  resolvida:
    "text-green-700 bg-green-50 dark:bg-green-950 dark:text-green-300",
  arquivada:
    "text-muted-foreground bg-muted",
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
    <Card className="h-full">
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-medium text-muted-foreground">
          Últimas ocorrências
        </CardTitle>
      </CardHeader>
      <CardContent>
        {carregando ? (
          <div className="space-y-2">
            <Skeleton className="h-5 w-full" />
            <Skeleton className="h-5 w-full" />
            <Skeleton className="h-5 w-3/4" />
          </div>
        ) : recentes.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            Nenhuma ocorrência registrada.
          </p>
        ) : (
          <ul className="space-y-1.5 text-sm">
            {recentes.map((o) => (
              <li
                key={o.id}
                className="flex items-center justify-between gap-3"
              >
                <Link
                  to={`/ocorrencias/${o.id}`}
                  className="truncate hover:underline flex-1 min-w-0"
                  title={alunosPorId.get(o.aluno) ?? `Aluno #${o.aluno}`}
                >
                  <span className="text-muted-foreground tabular-nums mr-2">
                    {formatarDataBR(o.data_ocorrencia)}
                  </span>
                  <span>
                    {alunosPorId.get(o.aluno) ?? `Aluno #${o.aluno}`}
                  </span>
                </Link>
                <span
                  className={`text-xs px-2 py-0.5 rounded shrink-0 ${STATUS_BADGE[o.status]}`}
                >
                  {o.status_display}
                </span>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
