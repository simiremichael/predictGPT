import Link from "next/link";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";

interface NavItem {
  href: string;
  label: string;
}

interface MobileNavProps {
  items: NavItem[];
  currentPath: string;
  open: boolean;
  onNavigate: () => void;
}

export function MobileNav({ items, currentPath, open, onNavigate }: MobileNavProps) {
  if (!open) return null;

  return (
    <nav aria-label="Mobile navigation" className="border-b border-border/80 bg-background/95 backdrop-blur-xl md:hidden">
      <div className="page-shell mx-auto grid grid-cols-2 gap-2 py-3 sm:grid-cols-3">
        {items.map((item) => (
          <Link
            key={item.href}
            href={item.href}
            onClick={onNavigate}
            aria-current={currentPath === item.href ? "page" : undefined}
          >
            <Button
              variant={currentPath === item.href ? "default" : "ghost"}
              size="sm"
              className={cn(
                "w-full whitespace-nowrap text-sm font-semibold shadow-sm",
                currentPath === item.href
                  ? "ring-1 ring-primary/15 shadow-[0_10px_20px_rgba(13,128,87,0.18)]"
                  : "hover:bg-accent/80",
              )}
            >
              {item.label}
            </Button>
          </Link>
        ))}
      </div>
    </nav>
  );
}
