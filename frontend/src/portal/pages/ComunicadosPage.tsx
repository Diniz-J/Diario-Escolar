import { Link } from "react-router-dom";

import { Skeleton } from "@/components/ui/skeleton";
import { useComunicados } from "@/features/portal/hooks";

import { formatarDataHora } from "./InicioPage";

export function ComunicadosPage() {
  const query = useComunicados();

  return (
    <section className="space-y-3">
      <div className="space-y-2">
        <h1 className="font-heading text-[26px] md:text-[30px] tracking-tight text-tinta leading-[1.15]">
          Comunicados
        </h1>
        <div className="h-px w-10 bg-ferrugem" />
      </div>

      {query.isLoading ? (
        <div className="space-y-2">
          <Skeleton className="h-16 w-full" />
          <Skeleton className="h-16 w-full" />
        </div>
      ) : query.isError ? (
        <p className="text-sm text-destructive">
          Não foi possível carregar os comunicados.
        </p>
      ) : (query.data?.length ?? 0) === 0 ? (
        <p className="text-sm text-muted-foreground">
          Nenhum comunicado recebido ainda.
        </p>
      ) : (
        <ul className="space-y-2">
          {query.data?.map((c) => (
            <li key={c.id}>
              <Link
                to={`/portal/comunicados/${c.id}`}
                className="block rounded-lg bg-paper border border-border p-4 hover:border-ferrugem transition space-y-1"
              >
                <span className="font-medium block">{c.titulo}</span>
                <span className="text-sm text-muted-foreground block">
                  {formatarDataHora(c.enviado_em)}
                </span>
                {c.alunos.length > 0 && (
                  <span className="text-xs text-sepia block">
                    {c.alunos.map((a) => a.nome_completo).join(", ")}
                  </span>
                )}
              </Link>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
