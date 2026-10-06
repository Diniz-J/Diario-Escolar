import { useQuery } from "@tanstack/react-query";

import type { Boletim } from "@/types/api";

import { portalApi } from "./api";
import type {
  Paginado,
  PortalComunicado,
  PortalFilho,
  PortalMaterial,
  PortalOcorrencia,
  PortalPeriodo,
} from "./types";

// Chave raiz própria: invalidar o cache do portal nunca mexe no do staff.
const PORTAL_KEY = ["portal"] as const;

/** Lista plana ou envelope paginado — o backend varia por endpoint. */
function resultados<T>(data: T[] | Paginado<T>): T[] {
  return Array.isArray(data) ? data : data.results;
}

export function useFilhos() {
  return useQuery({
    queryKey: [...PORTAL_KEY, "filhos"],
    queryFn: async (): Promise<PortalFilho[]> => {
      const { data } = await portalApi.get<PortalFilho[]>("/alunos/");
      return data;
    },
  });
}

export function useFilho(id: number | undefined) {
  return useQuery({
    queryKey: [...PORTAL_KEY, "filho", id],
    queryFn: async (): Promise<PortalFilho> => {
      const { data } = await portalApi.get<PortalFilho>(`/alunos/${id}/`);
      return data;
    },
    enabled: id != null && Number.isFinite(id),
  });
}

export function usePeriodos() {
  return useQuery({
    queryKey: [...PORTAL_KEY, "periodos"],
    queryFn: async (): Promise<PortalPeriodo[]> => {
      const { data } = await portalApi.get<PortalPeriodo[]>("/periodos/");
      return data;
    },
  });
}

/** `periodoId` nulo = boletim anual (sem janela). */
export function useBoletimFilho(
  alunoId: number | undefined,
  periodoId: number | null,
) {
  return useQuery({
    queryKey: [...PORTAL_KEY, "boletim", alunoId, periodoId],
    queryFn: async (): Promise<Boletim> => {
      const { data } = await portalApi.get<Boletim>(
        `/alunos/${alunoId}/boletim/`,
        { params: periodoId ? { periodo: periodoId } : {} },
      );
      return data;
    },
    enabled: alunoId != null && Number.isFinite(alunoId),
  });
}

export function useOcorrenciasFilho(alunoId: number | undefined) {
  return useQuery({
    queryKey: [...PORTAL_KEY, "ocorrencias", alunoId],
    queryFn: async (): Promise<PortalOcorrencia[]> => {
      const { data } = await portalApi.get<
        PortalOcorrencia[] | Paginado<PortalOcorrencia>
      >(`/alunos/${alunoId}/ocorrencias/`, { params: { page_size: "all" } });
      return resultados(data);
    },
    enabled: alunoId != null && Number.isFinite(alunoId),
  });
}

export function useMateriaisFilho(alunoId: number | undefined) {
  return useQuery({
    queryKey: [...PORTAL_KEY, "materiais", alunoId],
    queryFn: async (): Promise<PortalMaterial[]> => {
      const { data } = await portalApi.get<
        PortalMaterial[] | Paginado<PortalMaterial>
      >(`/alunos/${alunoId}/materiais/`, { params: { page_size: "all" } });
      return resultados(data);
    },
    enabled: alunoId != null && Number.isFinite(alunoId),
  });
}

export function useComunicados() {
  return useQuery({
    queryKey: [...PORTAL_KEY, "comunicados"],
    queryFn: async (): Promise<PortalComunicado[]> => {
      const { data } = await portalApi.get<
        PortalComunicado[] | Paginado<PortalComunicado>
      >("/comunicados/", { params: { page_size: "all" } });
      return resultados(data);
    },
  });
}

export function useComunicado(id: number | undefined) {
  return useQuery({
    queryKey: [...PORTAL_KEY, "comunicado", id],
    queryFn: async (): Promise<PortalComunicado> => {
      const { data } = await portalApi.get<PortalComunicado>(
        `/comunicados/${id}/`,
      );
      return data;
    },
    enabled: id != null && Number.isFinite(id),
  });
}
