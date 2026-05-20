import { Link } from "react-router-dom";

import { Button } from "@/components/ui/button";

// Fallback para URLs não mapeadas no router.
export function NotFoundPage() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-background">
      <div className="text-center space-y-4">
        <h1 className="text-5xl font-semibold">404</h1>
        <p className="text-muted-foreground">Página não encontrada.</p>
        <Button asChild variant="outline">
          <Link to="/">Voltar ao início</Link>
        </Button>
      </div>
    </div>
  );
}
