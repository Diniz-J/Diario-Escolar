import { Link } from "react-router-dom";

import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

interface MetricCardProps {
  titulo: string;
  // `valor` aceita string pra suportar formatos "12" ou "—" (sem dado).
  valor: string | number;
  // Linha secundária (ex.: breakdown "8 abertas · 4 em andamento").
  sublinha?: React.ReactNode;
  // Quando passado, o card vira clicável e leva pra rota indicada.
  href?: string;
  carregando?: boolean;
  // Quando true, marca o card com a tira ferrugem à esquerda — indica
  // que tem algo que pede atenção (pendente, atrasado, etc.). Usado
  // hoje no card de ocorrências em aberto quando há > 0.
  tomDestaque?: boolean;
}

// Card de métrica do Dashboard.
//
// Tipografia: título em mono uppercase pequeno (papel de "etiqueta") +
// valor em Fraunces grande (presença visual real). Inversão proposital
// vs. o resto da UI — o número É o conteúdo aqui, então merece o peso
// editorial.
//
// Interação: quando `href` está setado, o card inteiro vira link. Na
// hover, a borda esquerda passa de transparente pra ferrugem — efeito
// mais elegante que escurecer o fundo.
export function MetricCard({
  titulo,
  valor,
  sublinha,
  href,
  carregando,
  tomDestaque,
}: MetricCardProps) {
  const conteudo = (
    <div
      className={cn(
        "h-full bg-paper rounded-lg p-6 transition-all",
        "border border-border border-l-2",
        tomDestaque ? "border-l-ferrugem" : "border-l-border",
        href && "hover:border-l-ferrugem hover:shadow-sm cursor-pointer",
      )}
    >
      <p className="text-[11px] uppercase tracking-[0.18em] text-sepia">
        {titulo}
      </p>
      <div className="mt-3 space-y-2">
        {carregando ? (
          <Skeleton className="h-12 w-24" />
        ) : (
          <p className="font-heading text-[44px] md:text-[52px] leading-none text-tinta tabular-nums">
            {valor}
          </p>
        )}
        {sublinha && <div className="text-xs text-sepia">{sublinha}</div>}
      </div>
    </div>
  );

  if (href) {
    return (
      <Link to={href} className="block">
        {conteudo}
      </Link>
    );
  }
  return conteudo;
}
