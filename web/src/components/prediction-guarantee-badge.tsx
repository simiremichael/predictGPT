import { Shield } from "lucide-react";

export function PredictionGuaranteeBadge() {
  return (
    <div className="inline-flex max-w-full items-start gap-2 rounded-2xl border-2 border-emerald-500/30 bg-emerald-500/15 px-3 py-2.5 shadow-[0_0_20px_rgba(16,185,129,0.2)] sm:items-center sm:rounded-full sm:px-4">
      <Shield className="mt-0.5 h-5 w-5 shrink-0 text-emerald-400 sm:mt-0" />
      <span className="text-sm font-black text-emerald-500 sm:text-base">
        90% probability at least one of the 3 predictions hits
      </span>
    </div>
  );
}
