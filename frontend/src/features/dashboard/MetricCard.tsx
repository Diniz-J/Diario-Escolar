import { Link } from "react-router-dom";

import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
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
}

// Card compacto pro Dashboard. Quando recebe `href`, vira um link e
// ganha hover state — usado pra navegar pra listagem filtrada.
export function MetricCard({
  titulo,
  valor,
  sublinha,
  href,
  carregando,
}: MetricCardProps) {
  const conteudo = (
    <Card
      className={cn(
        "h-full transition-colors",
        href && "hover:bg-muted/40 cursor-pointer",
      )}
    >
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-medium text-muted-foreground">
          {titulo}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-1">
        {carregando ? (
          <Skeleton className="h-8 w-20" />
        ) : (
          <p className="text-3xl font-semibold tabular-nums">{valor}</p>
        )}
        {sublinha && (
          <div className="text-xs text-muted-foreground">{sublinha}</div>
        )}
      </CardContent>
    </Card>
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
