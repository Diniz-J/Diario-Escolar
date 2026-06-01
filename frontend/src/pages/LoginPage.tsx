import axios from "axios";
import { useState, type FormEvent } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";

import { useAuth } from "@/features/auth/useAuth";

// Login — paleta olive/linho (Diário Diniz).
//
// As cores vêm dos tokens globais definidos em `index.css` (utility
// classes `bg-linho`, `text-tinta`, `border-ferrugem` etc.). Quando
// quisermos ajustar tom, é uma alteração de variável CSS, não vários
// arquivos.

export function LoginPage() {
  const { login, isAuthenticated } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [erro, setErro] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);

  if (isAuthenticated) {
    return <Navigate to="/dashboard" replace />;
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setErro(null);
    setEnviando(true);
    try {
      await login({ username, password });
      const from =
        (location.state as { from?: { pathname: string } } | null)?.from
          ?.pathname ?? "/dashboard";
      navigate(from, { replace: true });
    } catch (err) {
      if (axios.isAxiosError(err) && err.response?.status === 401) {
        setErro("Usuário ou senha inválidos.");
      } else {
        setErro("Não foi possível entrar. Tente novamente.");
        console.error(err);
      }
    } finally {
      setEnviando(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center p-4 bg-linho text-tinta">
      <div className="w-full max-w-lg">
        {/* Microtípico no topo — eyebrow em olive. */}
        <p className="text-[11px] uppercase tracking-[0.25em] mb-10 text-olive">
          · diário diniz
        </p>

        {/* Título serif regular — Fraunces via font-heading. Tracking
            apertado pra Fraunces não estourar a largura do container. */}
        <h1
          className="font-heading mb-2 leading-[1.2] text-[26px] md:text-[30px] tracking-tight"
          style={{ fontWeight: 500 }}
        >
          Que bom te ver de volta.
        </h1>

        <p className="text-sm mb-7 text-sepia">
          Continue de onde parou.
        </p>

        {/* Filete ferrugem — detalhe memorável ("encadernação"). */}
        <div className="h-px w-12 mb-10 bg-ferrugem" />

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

          <div className="space-y-2">
            <div className="flex items-baseline justify-between">
              <label
                htmlFor="password"
                className="block text-[11px] uppercase tracking-[0.18em] text-sepia"
              >
                Senha
              </label>
              <button
                type="button"
                className="text-xs text-ferrugem hover:underline"
                onClick={() => {
                  /* Reset por email entra depois (FASE 4); por ora vira no-op. */
                }}
              >
                Esqueci a senha
              </button>
            </div>
            <input
              id="password"
              type="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
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
            disabled={enviando}
            className="w-full py-3 text-base font-medium rounded-md bg-olive text-creme hover:bg-olive-dark transition disabled:opacity-60 disabled:cursor-not-allowed"
          >
            {enviando ? "Acessando..." : "Acessar →"}
          </button>
        </form>

        {/* Rodapé sutil — paleta visível em 2 dots + versão. */}
        <div className="mt-12 flex items-center gap-2 text-[11px] text-sepia">
          <span className="inline-block w-2 h-2 rounded-full bg-olive" />
          <span className="inline-block w-2 h-2 rounded-full bg-ferrugem" />
          <span>v1.0 · Diário Diniz</span>
        </div>
      </div>
    </div>
  );
}
