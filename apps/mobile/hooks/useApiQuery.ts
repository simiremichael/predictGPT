import { useQuery, UseQueryOptions } from "@tanstack/react-query";
import type { PaginatedMeta } from "@/types";

export function useApiQuery<T>(
  queryKey: readonly unknown[],
  queryFn: () => Promise<T>,
  options?: Omit<UseQueryOptions<T>, "queryKey" | "queryFn">,
) {
  return useQuery<T>({
    queryKey,
    queryFn,
    staleTime: 1000 * 60 * 2,
    gcTime: 1000 * 60 * 5,
    retry: 2,
    retryDelay: (attemptIndex) => Math.min(1000 * 2 ** attemptIndex, 30000),
    ...options,
  });
}

export function usePaginatedQuery<T>(
  queryKey: readonly unknown[],
  queryFn: () => Promise<{ data: T[]; meta: PaginatedMeta }>,
  options?: Omit<UseQueryOptions<{ data: T[]; meta: PaginatedMeta }>, "queryKey" | "queryFn">,
) {
  return useQuery<{ data: T[]; meta: PaginatedMeta }>({
    queryKey,
    queryFn,
    staleTime: 1000 * 60 * 2,
    gcTime: 1000 * 60 * 5,
    retry: 2,
    retryDelay: (attemptIndex) => Math.min(1000 * 2 ** attemptIndex, 30000),
    ...options,
  });
}
