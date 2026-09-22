"use client";

import {
  QueryClient,
  QueryClientProvider,
  HydrationBoundary,
  type HydrationBoundaryProps,
} from "@tanstack/react-query";
import { useState } from "react";

const defaultQueryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30 * 1000,
      gcTime: 5 * 60 * 1000,
      retry: (failureCount, error: unknown) => {
        if (error && typeof error === "object" && "status" in error) {
          const status = (error as { status?: number }).status;
          if (status && status >= 400 && status < 500) return false;
        }
        return failureCount < 3;
      },
      refetchOnWindowFocus: false,
    },
  },
});

export function QueryProvider({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(() => defaultQueryClient);
  return (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
}

export function QueryBoundary({
  state,
  children,
}: {
  state: unknown;
  children: React.ReactNode;
}) {
  return (
    <HydrationBoundary state={state as HydrationBoundaryProps["state"]}>
      {children}
    </HydrationBoundary>
  );
}
