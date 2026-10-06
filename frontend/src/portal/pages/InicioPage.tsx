import { Link } from "react-router-dom";

import { Skeleton } from "@/components/ui/skeleton";
import { useComunicados, useFilhos } from "@/features/portal/hooks";

const MAX_RECENTES = 3;

export function InicioPage() {
  const filhosQuery = useFilhos();
  const comunicadosQuery = useComunicados();
  const recentes = (comunicadosQuery.data ?? []).slice(0, MAX_RECENTES);

  return (
    <>
      <section className="space-y-3">
        <div className="space-y-2">
          <h1 className="font-heading text-[26px] md:text-[30px] tracking-tight text-tinta leading-[1.15]">
            Seus filhos
          </h1>
          <div className="h-px w-10 bg-ferrugem" />
        </div>

        {filhosQuery.isLoading ? (
          <Skeleton className="h-20 w-full" />
        ) : filhosQuery.isError ? (
          <p className="text-sm text-destructive">
            Não foi possível carregar seus filhos.
          </p>
        ) : (filhosQuery.data?.length ?? 0) === 0 ? (
          <p className="text-sm text-muted-foreground">
            Nenhum aluno vinculado à sua conta. Procure a secretaria da escola.
          </p>
        ) : (
          <ul className="space-y-2">
            {filhosQuery.data?.map((filho) => (
              <li key={filho.id}>
                <Link
                  to={`/portal/alunos/${filho.id}`}
                  className="block rounded-lg bg-paper border border-border p-4 hover:border-ferrugem transition"
                >
                  <span className="font-medium block">
                    {filho.nome_completo}
                  </span>
                  <span className="text-sm text-muted-foreground">
                    {filho.turma ?? "Sem turma"}
                    {filho.ano_letivo ? ` · ${filho.ano_letivo}` : ""}
                    {!filho.ativo ? " · [ inativo ]" : ""}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="space-y-3">
        <div className="flex items-baseline justify-between gap-3">
          <h2 className="font-heading text-[20px] tracking-tight text-tinta">
            Comunicados recentes
          </h2>
          <Link to="/portal/comunicados" className="text-sm underline">
            Ver todos
          </Link>
        </div>

        {comunicadosQuery.isLoading ? (
          <Skeleton className="h-16 w-full" />
        ) : recentes.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            Nenhum comunicado recebido ainda.
          </p>
        ) : (
          <ul className="space-y-2">
            {recentes.map((c) => (
              <li key={c.id}>
                <Link
                  to={`/portal/comunicados/${c.id}`}
                  className="block rounded-lg bg-paper border border-border p-4 hover:border-ferrugem transition"
                >
                  <span className="font-medium block">{c.titulo}</span>
                  <span className="text-sm text-muted-foreground">
                    {formatarDataHora(c.enviado_em)}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </section>
    </>
  );
}

export function formatarDataHora(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("pt-BR", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}
