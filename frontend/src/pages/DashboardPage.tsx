import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { useAuth } from "@/features/auth/useAuth";

const PERFIL_LABEL: Record<string, string> = {
  admin: "Administrador",
  diretor: "Diretor",
  professor: "Professor",
  secretaria: "Secretaria",
  inspetor: "Inspetor",
};

// Dashboard — destino padrão após o login.
//
// Agora renderizado dentro do AppLayout, que cuida de sidebar e botão
// Sair. Foco aqui é só o conteúdo da área principal.
export function DashboardPage() {
  const { user } = useAuth();

  const perfilLabel = user?.perfil
    ? PERFIL_LABEL[user.perfil] ?? user.perfil
    : "—";

  return (
    <div className="p-8 space-y-6">
      <h1 className="text-3xl font-semibold">Dashboard</h1>

      <Card>
        <CardHeader>
          <CardTitle>Bem-vindo</CardTitle>
        </CardHeader>
        <CardContent>
          <dl className="grid grid-cols-[max-content_1fr] gap-x-6 gap-y-2 text-sm">
            <dt className="text-muted-foreground">Perfil</dt>
            <dd>{perfilLabel}</dd>

            <dt className="text-muted-foreground">Sessão expira em</dt>
            <dd>
              {user
                ? new Date(user.exp * 1000).toLocaleString("pt-BR")
                : "—"}
            </dd>
          </dl>
        </CardContent>
      </Card>

      <p className="text-sm text-muted-foreground">
        Use a navegação à esquerda pra acessar as outras áreas.
      </p>
    </div>
  );
}
