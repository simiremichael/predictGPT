import { Sparkles } from "lucide-react";
import { Badge } from "@/components/ui/badge";

export function AIGeneratedBadge() {
  return (
    <Badge
      variant="secondary"
      className="inline-flex items-center gap-1 border border-primary/20 bg-primary/10 text-[10px] font-semibold text-primary"
    >
      <Sparkles className="h-3 w-3" aria-hidden="true" />
      AI Generated
    </Badge>
  );
}
