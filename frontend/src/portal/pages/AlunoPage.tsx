import { useState } from "react";
import { Link, useParams } from "react-router-dom";

import { Skeleton } from "@/components/ui/skeleton";
// `financeiro/constants` é modulo folha (so importa tipo, que some no
// build), entao reusar daqui nao arrasta a arvore do staff pro chunk do
// portal — e o formato de dinheiro e as cores de status ficam iguais aos
// da tela da secretaria, em vez de uma segunda copia que diverge.
import {
  STATUS_FATURA,
  formatarBRL,
  formatarCompetencia,
} from "@/features/financeiro/constants";
import {
  useFaturasFilho,
  useFilho,
  useMateriaisFilho,
  useOcorrenciasFilho,
} from "@/features/portal/hooks";
import type { PortalFatura, PortalMaterial } from "@/features/portal/types";

import { formatarDataPura, formatarDiaDaDataHora } from "@/lib/datas";
import { BoletimFilho } from "../components/BoletimFilho";

type Aba = "boletim" | "ocorrencias" | "mural" | "mensalidades";

const ABAS: { id: Aba; label: string }[] = [
  { id: "boletim", label: "Boletim" },
  { id: "ocorrencias", label: "Ocorrências" },
  { id: "mural", label: "Mural" },
  { id: "mensalidades", label: "Mensalidades" },
];

export function AlunoPage() {
  const params = useParams<{ id: string }>();
  const id = params.id ? parseInt(params.id, 10) : undefined;
  const [aba, setAba] = useState<Aba>("boletim");
  const [periodoId, setPeriodoId] = useState<number | null>(null);

  const filhoQuery = useFilho(id);

  if (filhoQuery.isLoading) {
    return (
      <div className="space-y-3">
        <Skeleton className="h-8 w-56" />
        <Skeleton className="h-32 w-full" />
      </div>
    );
  }
  // 404 é o que o backend devolve pra id que não é filho deste
  // responsável — a mensagem não distingue "não existe" de "não é seu",
  // justamente pra não confirmar a existência de aluno alheio.
  if (filhoQuery.isError || !filhoQuery.data || id == null) {
    return (
      <div className="space-y-3">
        <p className="text-sm text-destructive">Aluno não encontrado.</p>
        <Link to="/portal" className="text-sm underline">
          Voltar
        </Link>
      </div>
    );
  }

  const filho = filhoQuery.data;

  return (
    <div className="space-y-5">
      <Link
        to="/portal"
        className="text-[11px] uppercase tracking-[0.18em] text-sepia hover:underline"
      >
        ← Início
      </Link>

      <div className="space-y-2">
        <h1 className="font-heading text-[24px] md:text-[28px] tracking-tight text-tinta leading-[1.2]">
          {filho.nome_completo}
        </h1>
        <div className="h-px w-10 bg-ferrugem" />
        <p className="text-sm text-muted-foreground">
          {filho.turma ?? "Sem turma"}
          {filho.ano_letivo ? ` · ${filho.ano_letivo}` : ""}
          {!filho.ativo ? " · [ inativo ]" : ""}
        </p>
      </div>

      <div
        role="tablist"
        aria-label="Seções do aluno"
        className="flex gap-1 border-b border-border overflow-x-auto"
      >
        {ABAS.map((item) => (
          <button
            key={item.id}
            type="button"
            role="tab"
            aria-selected={aba === item.id}
            onClick={() => setAba(item.id)}
            className={[
              "px-3 py-2 text-sm border-b-2 -mb-px whitespace-nowrap transition",
              aba === item.id
                ? "border-ferrugem text-tinta"
                : "border-transparent text-muted-foreground hover:text-tinta",
            ].join(" ")}
          >
            {item.label}
          </button>
        ))}
      </div>

      {aba === "boletim" && (
        <BoletimFilho
          alunoId={id}
          periodoId={periodoId}
          onPeriodoChange={setPeriodoId}
        />
      )}
      {aba === "ocorrencias" && <Ocorrencias alunoId={id} />}
      {aba === "mural" && <Mural alunoId={id} ativo={filho.ativo} />}
      {aba === "mensalidades" && <Mensalidades alunoId={id} />}
    </div>
  );
}

function Ocorrencias({ alunoId }: { alunoId: number }) {
  const query = useOcorrenciasFilho(alunoId);

  if (query.isLoading) return <Skeleton className="h-24 w-full" />;
  if (query.isError) {
    return (
      <p className="text-sm text-destructive">
        Não foi possível carregar as ocorrências.
      </p>
    );
  }
  if ((query.data?.length ?? 0) === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        Nenhuma ocorrência registrada.
      </p>
    );
  }

  return (
    <ul className="space-y-2">
      {query.data?.map((o) => (
        <li
          key={o.id}
          className="rounded-lg bg-paper border border-border p-4 space-y-2"
        >
          <div className="flex items-baseline justify-between gap-3">
            <span className="text-sm text-muted-foreground">
              {formatarDataPura(o.data_ocorrencia)}
            </span>
            <span className="text-xs text-sepia shrink-0">
              {o.status_display}
            </span>
          </div>
          {/* Texto puro: a descrição é escrita pelo professor. */}
          <p className="text-sm whitespace-pre-wrap leading-relaxed">
            {o.descricao}
          </p>
          {o.professor && (
            <p className="text-xs text-muted-foreground">
              Registrada por {o.professor}
            </p>
          )}
        </li>
      ))}
    </ul>
  );
}

function Mural({ alunoId, ativo }: { alunoId: number; ativo: boolean }) {
  const query = useMateriaisFilho(alunoId);

  if (!ativo) {
    return (
      <p className="text-sm text-muted-foreground">
        O mural mostra o conteúdo atual da turma, e este aluno não está mais
        matriculado. O boletim e as ocorrências continuam disponíveis.
      </p>
    );
  }
  if (query.isLoading) return <Skeleton className="h-24 w-full" />;
  if (query.isError) {
    return (
      <p className="text-sm text-destructive">
        Não foi possível carregar o mural.
      </p>
    );
  }
  if ((query.data?.length ?? 0) === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        Nenhum material publicado pela turma ainda.
      </p>
    );
  }

  return (
    <ul className="space-y-2">
      {query.data?.map((m) => (
        <li
          key={m.id}
          className="rounded-lg bg-paper border border-border p-4 space-y-2"
        >
          <div className="flex items-baseline justify-between gap-3">
            <span className="font-medium min-w-0">{m.titulo}</span>
            <span className="text-xs text-sepia shrink-0">{m.disciplina}</span>
          </div>
          {m.descricao && (
            <p className="text-sm whitespace-pre-wrap leading-relaxed">
              {m.descricao}
            </p>
          )}
          <LinkMaterial material={m} />
          <p className="text-xs text-muted-foreground">
            {m.professor ? `${m.professor} · ` : ""}
            {formatarDiaDaDataHora(m.publicado_em)}
          </p>
        </li>
      ))}
    </ul>
  );
}

function Mensalidades({ alunoId }: { alunoId: number }) {
  const query = useFaturasFilho(alunoId);

  if (query.isLoading) return <Skeleton className="h-24 w-full" />;
  if (query.isError) {
    return (
      <p className="text-sm text-destructive">
        Não foi possível carregar as mensalidades.
      </p>
    );
  }
  if ((query.data?.length ?? 0) === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        Nenhuma mensalidade registrada.
      </p>
    );
  }

  return (
    <ul className="space-y-2">
      {query.data?.map((f) => (
        <li
          key={f.id}
          className="rounded-lg bg-paper border border-border p-4 space-y-2"
        >
          <div className="flex items-baseline justify-between gap-3">
            <span className="font-medium">{formatarCompetencia(f.competencia)}</span>
            <span
              className={[
                "text-xs px-2 py-0.5 rounded shrink-0",
                STATUS_FATURA[f.status as keyof typeof STATUS_FATURA]?.className ?? "",
              ].join(" ")}
            >
              {STATUS_FATURA[f.status as keyof typeof STATUS_FATURA]?.label ?? f.status}
            </span>
          </div>
          <p className="text-sm text-muted-foreground">
            Vence em {formatarDataPura(f.vencimento)} · {formatarBRL(f.valor)}
          </p>
          {/* So aparece quando multa ou juros ja correram: repetir o mesmo
              numero em duas linhas faria o pai procurar a diferenca. */}
          {f.valor_atualizado !== f.valor && (
            <p className="text-sm">
              Com encargos até hoje:{" "}
              <strong>{formatarBRL(f.valor_atualizado)}</strong>
            </p>
          )}
          <LinkPagamento fatura={f} />
        </li>
      ))}
    </ul>
  );
}

/**
 * Botão de pagamento, só se o link for http(s).
 *
 * Mesma razão do `LinkMaterial`: o backend valida o esquema, mas é aqui
 * que o valor vira `href` no navegador do pai, e o link vem de fora (o
 * gateway escreve esse campo). `noopener noreferrer` impede o destino de
 * alcançar `window.opener`.
 *
 * Sem link, nada é renderizado: a escola ainda não emitiu a cobrança, e
 * um botão morto só geraria ligação pra secretaria.
 */
function LinkPagamento({ fatura }: { fatura: PortalFatura }) {
  const url = fatura.link_pagamento?.trim() ?? "";
  if (!/^https?:\/\//i.test(url)) return null;
  return (
    <a
      href={url}
      target="_blank"
      rel="noopener noreferrer"
      className="inline-block text-sm underline text-olive"
    >
      Pagar
    </a>
  );
}

/**
 * Link do material, só se for http(s).
 *
 * O backend já valida o esquema, mas a checagem repete aqui porque este é
 * o ponto em que o valor vira `href` no navegador do pai: um `javascript:`
 * que escapasse da validação executaria no clique. `noopener noreferrer`
 * impede a página de destino de alcançar `window.opener`.
 */
function LinkMaterial({ material }: { material: PortalMaterial }) {
  const url = material.link?.trim() ?? "";
  if (!/^https?:\/\//i.test(url)) return null;
  return (
    <a
      href={url}
      target="_blank"
      rel="noopener noreferrer"
      className="text-sm underline text-olive break-all"
    >
      Abrir material
    </a>
  );
}
