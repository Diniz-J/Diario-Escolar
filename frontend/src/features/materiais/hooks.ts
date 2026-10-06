import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { api } from "@/lib/api";
import { normalizarPaginado } from "@/lib/pagination";
import type { Material, MaterialInput, Paginated } from "@/types/api";

const MATERIAIS_KEY = ["materiais"] as const;

interface MateriaisFilter {
  turma?: number;
  professor?: number;
  ativo?: boolean;
}

// Paginado sempre: a lista da direção (escola inteira) cresce ao longo do
// ano. O backend só pagina com `?page=` (paginação opt-in do projeto).
export function useMateriaisPaginated(
  filter: MateriaisFilter,
  pagination: { page: number; page_size?: number },
) {
  return useQuery({
    queryKey: [...MATERIAIS_KEY, "paginated", filter, pagination],
    queryFn: async (): Promise<Paginated<Material>> => {
      const { data } = await api.get<Paginated<Material> | Material[]>(
        "/materiais/",
        { params: { ...filter, ...pagination } },
      );
      return normalizarPaginado(data);
    },
    placeholderData: (previous) => previous,
  });
}

function invalidateAll(qc: ReturnType<typeof useQueryClient>) {
  qc.invalidateQueries({ queryKey: MATERIAIS_KEY });
}

export function useCreateMaterial() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (input: MaterialInput): Promise<Material> => {
      const { data } = await api.post<Material>("/materiais/", input);
      return data;
    },
    onSuccess: () => {
      invalidateAll(qc);
      toast.success("Material publicado.");
    },
    // Sem toast de erro: o dialog mostra a mensagem do backend no lugar.
  });
}

export function useUpdateMaterial() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({
      id,
      patch,
    }: {
      id: number;
      patch: Partial<MaterialInput>;
    }): Promise<Material> => {
      const { data } = await api.patch<Material>(`/materiais/${id}/`, patch);
      return data;
    },
    onSuccess: () => {
      invalidateAll(qc);
      toast.success("Material atualizado.");
    },
  });
}

// DELETE no backend é soft delete (`ativo=false`): some do portal dos pais.
export function useDespublicarMaterial() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: number): Promise<void> => {
      await api.delete(`/materiais/${id}/`);
    },
    onSuccess: () => {
      invalidateAll(qc);
      toast.success("Material despublicado.");
    },
    onError: () => toast.error("Não foi possível despublicar o material."),
  });
}

export function useReativarMaterial() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: number): Promise<Material> => {
      const { data } = await api.patch<Material>(`/materiais/${id}/`, {
        ativo: true,
      });
      return data;
    },
    onSuccess: () => {
      invalidateAll(qc);
      toast.success("Material publicado de novo.");
    },
    // Lecionamento encerrado faz o backend recusar (400): o professor não
    // leciona mais a turma, então não republica.
    onError: () =>
      toast.error(
        "Não foi possível publicar de novo. Verifique se o professor ainda leciona a turma.",
      ),
  });
}
