import { Link, useParams } from "react-router-dom";

import { Skeleton } from "@/components/ui/skeleton";
import { useComunicado } from "@/features/portal/hooks";

import { formatarDataHora } from "./InicioPage";

export function ComunicadoDetalhePage() {
  const params = useParams<{ id: string }>();
  const id = params.id ? parseInt(params.id, 10) : undefined;
  const query = useComunicado(id);

  if (query.isLoading) {
    return (
      <div className="space-y-3">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-32 w-full" />
      </div>
    );
  }
  if (query.isError || !query.data) {
    return (
      <div className="space-y-3">
        <p className="text-sm text-destructive">
          Comunicado não encontrado.
        </p>
        <Link to="/portal/comunicados" className="text-sm underline">
          Voltar
        </Link>
      </div>
    );
  }

  const c = query.data;

  return (
    <article className="space-y-4">
      <Link
        to="/portal/comunicados"
        className="text-[11px] uppercase tracking-[0.18em] text-sepia hover:underline"
      >
        ← Comunicados
      </Link>

      <div className="space-y-2">
        <h1 className="font-heading text-[24px] md:text-[28px] tracking-tight text-tinta leading-[1.2]">
          {c.titulo}
        </h1>
        <div className="h-px w-10 bg-ferrugem" />
        <p className="text-sm text-muted-foreground">
          {formatarDataHora(c.enviado_em)}
        </p>
      </div>

      <div className="rounded-lg bg-paper border border-border p-4">
        {/* Texto puro com `whitespace-pre-wrap`, nunca HTML. A mensagem é
            digitada pela escola e renderizá-la como HTML permitiria
            injeção de script na tela do pai (`PORTAL.md`, fatia 6).
            O React já escapa o conteúdo; o que não pode aparecer aqui é
            `dangerouslySetInnerHTML`. */}
        <p className="text-sm whitespace-pre-wrap leading-relaxed">
          {c.mensagem}
        </p>
      </div>

      {c.alunos.length > 0 && (
        <div className="space-y-1">
          <div className="text-[11px] uppercase tracking-[0.18em] text-sepia">
            Enviado sobre
          </div>
          <p className="text-sm">
            {c.alunos.map((a) => a.nome_completo).join(", ")}
          </p>
        </div>
      )}
    </article>
  );
}
