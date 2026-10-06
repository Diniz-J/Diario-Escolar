import { Skeleton } from "@/components/ui/skeleton";
import { useBoletimFilho, usePeriodos } from "@/features/portal/hooks";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

const ANUAL = "__anual__";

/**
 * Boletim do filho — componente PRÓPRIO do portal.
 *
 * Não reaproveita a `BoletimPage` do staff de propósito (`PORTAL.md`,
 * fatia 6): ela tem 469 linhas e arrasta exportação CSV/XLSX, geração de
 * PDF e layout de impressão — nada disso é do pai, e importar puxaria
 * tudo pro chunk do portal.
 */
export function BoletimFilho({
  alunoId,
  periodoId,
  onPeriodoChange,
}: {
  alunoId: number;
  periodoId: number | null;
  onPeriodoChange: (id: number | null) => void;
}) {
  const periodosQuery = usePeriodos();
  const boletimQuery = useBoletimFilho(alunoId, periodoId);

  if (boletimQuery.isLoading) {
    return (
      <div className="space-y-2">
        <Skeleton className="h-20 w-full" />
        <Skeleton className="h-32 w-full" />
      </div>
    );
  }
  if (boletimQuery.isError || !boletimQuery.data) {
    return (
      <p className="text-sm text-destructive">
        Não foi possível carregar o boletim.
      </p>
    );
  }

  const boletim = boletimQuery.data;
  const freq = boletim.frequencia;

  return (
    <div className="space-y-6">
      <div className="space-y-2">
        <div className="text-[11px] uppercase tracking-[0.18em] text-sepia">
          Período
        </div>
        <Select
          value={periodoId ? String(periodoId) : ANUAL}
          onValueChange={(v) =>
            onPeriodoChange(v === ANUAL ? null : parseInt(v, 10))
          }
        >
          <SelectTrigger className="w-full sm:w-64">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ANUAL}>Ano inteiro</SelectItem>
            {periodosQuery.data?.map((p) => (
              <SelectItem key={p.id} value={String(p.id)}>
                {p.nome} ({p.ano_letivo})
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <section className="rounded-lg bg-paper border border-border p-4 space-y-3">
        <h3 className="font-heading text-[18px] tracking-tight text-tinta">
          Frequência
        </h3>
        <div className="flex flex-wrap gap-x-8 gap-y-3">
          <div>
            <div className="text-[11px] uppercase tracking-[0.18em] text-sepia">
              Presença
            </div>
            <p className="font-heading text-[28px] text-olive leading-tight">
              {freq.percentual_presenca}%
            </p>
          </div>
          <div>
            <div className="text-[11px] uppercase tracking-[0.18em] text-sepia">
              Aulas
            </div>
            <p className="text-sm pt-2">{freq.total}</p>
          </div>
          <div>
            <div className="text-[11px] uppercase tracking-[0.18em] text-sepia">
              Faltas
            </div>
            <p className="text-sm pt-2">{freq.ausentes}</p>
          </div>
          <div>
            <div className="text-[11px] uppercase tracking-[0.18em] text-sepia">
              Justificadas
            </div>
            <p className="text-sm pt-2">{freq.justificados}</p>
          </div>
        </div>
      </section>

      <section className="space-y-3">
        <h3 className="font-heading text-[18px] tracking-tight text-tinta">
          Notas
        </h3>
        {boletim.notas_por_disciplina.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            Nenhuma nota lançada neste período.
          </p>
        ) : (
          <div className="space-y-3">
            {boletim.notas_por_disciplina.map((d) => (
              <div
                key={d.disciplina.id}
                className="rounded-lg bg-paper border border-border p-4 space-y-3"
              >
                <div className="flex items-baseline justify-between gap-3">
                  <h4 className="font-medium">{d.disciplina.nome}</h4>
                  {d.notas_finais_por_periodo.length > 0 && (
                    <div className="text-right shrink-0">
                      {d.notas_finais_por_periodo.map((nf) => (
                        <div key={nf.periodo_id} className="text-sm">
                          <span className="text-muted-foreground">
                            {nf.periodo_nome}:{" "}
                          </span>
                          <span className="font-medium">
                            {nf.nota_final || "—"}
                          </span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                {d.avaliacoes.length === 0 ? (
                  <p className="text-sm text-muted-foreground">
                    Sem avaliações no período.
                  </p>
                ) : (
                  <ul className="space-y-1">
                    {d.avaliacoes.map((av) => (
                      <li
                        key={av.avaliacao_id}
                        className="flex items-baseline justify-between gap-3 text-sm"
                      >
                        <span className="min-w-0 truncate">
                          {av.titulo}
                          {av.data ? (
                            <span className="text-muted-foreground">
                              {" "}
                              · {formatarData(av.data)}
                            </span>
                          ) : null}
                        </span>
                        <span className="shrink-0 font-medium">
                          {av.nota_obtida || "—"}
                          <span className="text-muted-foreground font-normal">
                            {av.nota_maxima ? ` / ${av.nota_maxima}` : ""}
                          </span>
                        </span>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}

function formatarData(iso: string): string {
  return new Date(`${iso}T00:00:00`).toLocaleDateString("pt-BR", {
    day: "2-digit",
    month: "2-digit",
  });
}
