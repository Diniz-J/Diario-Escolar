import axios from "axios";
import { useState, type FormEvent } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";

import { useConfirmPasswordReset } from "@/features/auth/passwordHooks";

// Página /redefinir-senha?token=XYZ — pública.
// Recebe o token via query string (link do email). Pede nova senha e
// confirmação; envia pro backend pra trocar. Sucesso redireciona pra
// /login. Token inválido/expirado mostra mensagem clara.
export function RedefinirSenhaPage() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const token = params.get("token") ?? "";
  const confirmMutation = useConfirmPasswordReset();

  const [novaSenha, setNovaSenha] = useState("");
  const [confirmar, setConfirmar] = useState("");
  const [erro, setErro] = useState<string | null>(null);
  const [sucesso, setSucesso] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setErro(null);

    if (!token) {
      setErro("Link inválido. Solicite um novo email de redefinição.");
      return;
    }
    if (novaSenha !== confirmar) {
      setErro("A confirmação não confere.");
      return;
    }

    try {
      await confirmMutation.mutateAsync({ token, new_password: novaSenha });
      setSucesso(true);
      // Pequena pausa pro usuário ler a confirmação, depois manda pra
      // /login. 1,5s é o suficiente sem virar espera frustrante.
      setTimeout(() => navigate("/login"), 1500);
    } catch (err) {
      if (axios.isAxiosError(err) && err.response?.data) {
        const data = err.response.data as Record<string, unknown>;
        // Prefere mensagem dedicada do campo `detail` (token inválido)
        // ou primeira mensagem dos validators de senha.
        const detail =
          typeof data.detail === "string" ? data.detail : undefined;
        const senhaErrors = Array.isArray(data.new_password)
          ? (data.new_password as unknown[]).find(
              (v): v is string => typeof v === "string",
            )
          : undefined;
        setErro(detail ?? senhaErrors ?? "Não foi possível redefinir.");
      } else {
        setErro("Erro inesperado.");
        console.error(err);
      }
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center p-4 bg-linho text-tinta">
      <div className="w-full max-w-lg">
        <p className="text-[11px] uppercase tracking-[0.25em] mb-10 text-olive">
          · diário diniz
        </p>

        <h1
          className="font-heading mb-2 leading-[1.2] text-[26px] md:text-[30px] tracking-tight"
          style={{ fontWeight: 500 }}
        >
          Defina uma nova senha
        </h1>

        <p className="text-sm mb-7 text-sepia">
          Escolha uma senha forte e fácil de lembrar.
        </p>

        <div className="h-px w-12 mb-10 bg-ferrugem" />

        {sucesso ? (
          <div className="space-y-6">
            <p className="text-sm px-3 py-3 rounded-md bg-olive/10 text-olive border border-olive/20">
              Senha redefinida. Redirecionando para o login...
            </p>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-6">
            <div className="space-y-2">
              <label
                htmlFor="nova-senha"
                className="block text-[11px] uppercase tracking-[0.18em] text-sepia"
              >
                Nova senha
              </label>
              <input
                id="nova-senha"
                type="password"
                autoComplete="new-password"
                required
                minLength={8}
                value={novaSenha}
                onChange={(e) => setNovaSenha(e.target.value)}
                className="w-full px-3 py-2.5 text-base rounded-md bg-paper border border-border text-tinta focus:outline-none focus:border-ferrugem focus:ring-2 focus:ring-ferrugem/20 transition"
              />
            </div>

            <div className="space-y-2">
              <label
                htmlFor="confirmar"
                className="block text-[11px] uppercase tracking-[0.18em] text-sepia"
              >
                Confirme a nova senha
              </label>
              <input
                id="confirmar"
                type="password"
                autoComplete="new-password"
                required
                minLength={8}
                value={confirmar}
                onChange={(e) => setConfirmar(e.target.value)}
                className="w-full px-3 py-2.5 text-base rounded-md bg-paper border border-border text-tinta focus:outline-none focus:border-ferrugem focus:ring-2 focus:ring-ferrugem/20 transition"
              />
            </div>

            {erro && (
              <p className="text-sm px-3 py-2 rounded-md bg-destructive/15 text-destructive border border-destructive/30">
                {erro}
              </p>
            )}

            <button
              type="submit"
              disabled={confirmMutation.isPending}
              className="w-full py-3 text-base font-medium rounded-md bg-olive text-creme hover:bg-olive-dark transition disabled:opacity-60 disabled:cursor-not-allowed"
            >
              {confirmMutation.isPending ? "Salvando..." : "Salvar →"}
            </button>

            <Link
              to="/login"
              className="block text-sm text-ferrugem hover:underline text-center"
            >
              ← Voltar para o login
            </Link>
          </form>
        )}
      </div>
    </div>
  );
}
