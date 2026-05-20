// Placeholder usado pra rotas autenticadas que ainda não foram
// implementadas. Mostra um título e um aviso. Será substituído conforme
// cada feature (Turmas, Ocorrências, Presença) ganhar implementação.
interface PlaceholderPageProps {
  titulo: string;
}

export function PlaceholderPage({ titulo }: PlaceholderPageProps) {
  return (
    <div className="p-8 space-y-2">
      <h1 className="text-3xl font-semibold">{titulo}</h1>
      <p className="text-sm text-muted-foreground">
        Tela em construção. Em breve.
      </p>
    </div>
  );
}
