import { useMemo } from "react";
import { Link } from "react-router-dom";

import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useRegistros } from "@/features/presenca/hooks";
import { useTurmas } from "@/features/turmas/hooks";
import { cn } from "@/lib/utils";

interface UltimasChamadasCardProps {
  // Se preenchido, mostra só essa turma; senão, lista as 5 mais recentes.
  turmaFiltrada?: number | null;
}

interface LinhaUltimaChamada {
  turmaId: number;
  turmaNome: string;
  ultimaData: string | null; // ISO "YYYY-MM-DD" ou null se nunca houve chamada
  diasAtras: number | null;
}

const HOJE_ISO = () => new Date().toISOString().slice(0, 10);

function diasDesde(isoData: string): number {
  // Comparação só de data (sem hora) — evita off-by-one por fuso.
  const hoje = new Date(HOJE_ISO() + "T00:00:00");
  const passado = new Date(isoData + "T00:00:00");
  const diffMs = hoje.getTime() - passado.getTime();
  return Math.floor(diffMs / (1000 * 60 * 60 * 24));
}

function formatarDataBR(iso: string): string {
  const [ano, mes, dia] = iso.split("-");
  return `${dia}/${mes}/${ano}`;
}

// Mostra a data da chamada mais recente por turma. Quando nenhuma turma
// está filtrada, exibe até 5 turmas ativas (priorizando as que estão a
// mais tempo sem chamada — sinaliza turma "esquecida").
export function UltimasChamadasCard({
  turmaFiltrada,
}: UltimasChamadasCardProps) {
  const turmasQuery = useTurmas();
  const registrosQuery = useRegistros(
    turmaFiltrada ? { turma: turmaFiltrada } : {},
  );

  const carregando = turmasQuery.isLoading || registrosQuery.isLoading;

  const linhas: LinhaUltimaChamada[] = useMemo(() => {
    if (!turmasQuery.data || !registrosQuery.data) return [];

    // Mapeia turma → maior data de registro (ISO ordena lexicograficamente).
    const ultimaPorTurma = new Map<number, string>();
    for (const r of registrosQuery.data) {
      const atual = ultimaPorTurma.get(r.turma);
      if (!atual || r.data > atual) ultimaPorTurma.set(r.turma, r.data);
    }

    const turmasAtivas = turmasQuery.data.filter((t) => t.ativa);
    const turmasAlvo = turmaFiltrada
      ? turmasAtivas.filter((t) => t.id === turmaFiltrada)
      : turmasAtivas;

    const todas: LinhaUltimaChamada[] = turmasAlvo.map((t) => {
      const data = ultimaPorTurma.get(t.id) ?? null;
      return {
        turmaId: t.id,
        turmaNome: t.nome,
        ultimaData: data,
        diasAtras: data ? diasDesde(data) : null,
      };
    });

    // Ordena: turmas sem chamada primeiro (mais urgente), depois as com
    // mais dias sem chamada. Cap em 5 quando não há filtro.
    todas.sort((a, b) => {
      if (a.diasAtras == null && b.diasAtras == null) return 0;
      if (a.diasAtras == null) return -1;
      if (b.diasAtras == null) return 1;
      return b.diasAtras - a.diasAtras;
    });

    return turmaFiltrada ? todas : todas.slice(0, 5);
  }, [turmasQuery.data, registrosQuery.data, turmaFiltrada]);

  return (
    <Card className="h-full">
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-medium text-muted-foreground">
          Última chamada por turma
        </CardTitle>
      </CardHeader>
      <CardContent>
        {carregando ? (
          <div className="space-y-2">
            <Skeleton className="h-5 w-full" />
            <Skeleton className="h-5 w-full" />
            <Skeleton className="h-5 w-3/4" />
          </div>
        ) : linhas.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            Nenhuma turma ativa.
          </p>
        ) : (
          <ul className="space-y-1.5 text-sm">
            {linhas.map((l) => {
              const alerta = l.diasAtras == null || l.diasAtras > 3;
              return (
                <li key={l.turmaId} className="flex items-center justify-between gap-3">
                  <Link
                    to={`/turmas/${l.turmaId}`}
                    className="truncate hover:underline"
                  >
                    {l.turmaNome}
                  </Link>
                  <span
                    className={cn(
                      "text-xs tabular-nums shrink-0",
                      alerta ? "text-amber-700 dark:text-amber-400" : "text-muted-foreground",
                    )}
                  >
                    {l.ultimaData
                      ? `${formatarDataBR(l.ultimaData)} · ${l.diasAtras}d`
                      : "sem chamada"}
                  </span>
                </li>
              );
            })}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
