"use client";

import { useRouter } from "next/navigation";

export function RetryableError({ message }: { message: string }) {
  const router = useRouter();

  return (
    <div className="flex flex-col items-center justify-center py-12 text-center">
      <div className="max-w-md rounded-xl border border-destructive/50 bg-destructive/5 p-6">
        <h3 className="text-lg font-semibold text-destructive">
          Something went wrong
        </h3>
        <p className="mt-2 text-sm text-muted-foreground">{message}</p>
        <button
          type="button"
          onClick={() => router.refresh()}
          className="mt-4 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90"
        >
          Try again
        </button>
      </div>
    </div>
  );
}
