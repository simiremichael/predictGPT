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
}

export function MobileNav({ items, currentPath }: MobileNavProps) {
  return (
    <nav className="md:hidden border-t border-border/80 bg-background/95 backdrop-blur-xl">
      <div className="page-shell mx-auto flex items-center gap-1 overflow-x-auto py-2.5">
        {items.map((item) => (
          <Link key={item.href} href={item.href}>
            <Button
              variant={currentPath === item.href ? "default" : "ghost"}
              size="sm"
              className={cn(
                "whitespace-nowrap text-sm font-semibold shadow-sm",
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
