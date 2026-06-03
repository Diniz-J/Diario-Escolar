import axios from "axios";
import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";

import { useRequestPasswordReset } from "@/features/auth/passwordHooks";

// Página /esqueci-senha — pública.
// Usuário digita username; backend resolve o email cadastrado e envia
// link. A resposta é sempre 200 (anti-enumeração), então mostramos
// sempre a mesma mensagem de sucesso — sem revelar se o user existe.
export function EsqueciSenhaPage() {
  const requestMutation = useRequestPasswordReset();
  const [username, setUsername] = useState("");
  const [enviado, setEnviado] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setErro(null);
    try {
      await requestMutation.mutateAsync(username.trim());
      setEnviado(true);
    } catch (err) {
      // O backend só retorna não-200 em erro de validação (campo vazio)
      // ou se a throttle bater. Mostramos genérico.
      if (axios.isAxiosError(err) && err.response?.status === 429) {
        setErro(
          "Muitas tentativas. Aguarde alguns minutos antes de tentar novamente.",
        );
      } else {
        setErro("Não foi possível processar a solicitação.");
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
          Esqueceu sua senha?
        </h1>

        <p className="text-sm mb-7 text-sepia">
          Informe seu usuário. Enviaremos um link para o email cadastrado
          no seu perfil.
        </p>

        <div className="h-px w-12 mb-10 bg-ferrugem" />

        {enviado ? (
          <div className="space-y-6">
            <p className="text-sm px-3 py-3 rounded-md bg-olive/10 text-olive border border-olive/20">
              Se o usuário existir e tiver email cadastrado, um link de
              redefinição foi enviado. Verifique sua caixa de entrada (e o
              spam). O link expira em 1 hora.
            </p>
            <Link
              to="/login"
              className="block text-sm text-ferrugem hover:underline"
            >
              ← Voltar para o login
            </Link>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-6">
            <div className="space-y-2">
              <label
                htmlFor="username"
                className="block text-[11px] uppercase tracking-[0.18em] text-sepia"
              >
                Usuário
              </label>
              <input
                id="username"
                type="text"
                autoComplete="username"
                required
                value={username}
                onChange={(e) => setUsername(e.target.value)}
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
              disabled={requestMutation.isPending}
              className="w-full py-3 text-base font-medium rounded-md bg-olive text-creme hover:bg-olive-dark transition disabled:opacity-60 disabled:cursor-not-allowed"
            >
              {requestMutation.isPending ? "Enviando..." : "Enviar link →"}
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
