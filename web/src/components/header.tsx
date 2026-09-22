"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Menu, Search, Sparkles } from "lucide-react";
import { useState, useEffect } from "react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { MobileNav } from "@/components/mobile-nav";
import { SearchDialog } from "@/components/search-dialog";

const navItems = [
  { href: "/", label: "Home" },
  { href: "/matches", label: "Matches" },
  { href: "/predictions", label: "Predictions" },
  { href: "/leagues", label: "Leagues" },
  { href: "/teams", label: "Teams" },
  { href: "/performance", label: "Performance" },
];

export function Header() {
  const pathname = usePathname();
  const [showSearch, setShowSearch] = useState(false);
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const handleScroll = () => {
      setScrolled(window.scrollY > 10);
    };
    window.addEventListener("scroll", handleScroll);
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  return (
    <>
      <header
        className={cn(
          "sticky top-0 z-40 border-b border-border/70 bg-background/70 backdrop-blur-xl transition-all duration-300",
          scrolled ? "shadow-[0_18px_40px_rgba(15,23,42,0.08)]" : "",
        )}
      >
        <div className="page-shell mx-auto flex h-[4.75rem] items-center justify-between">
          <Link href="/" className="group flex items-center gap-2.5">
            <span className="flex h-10 w-10 items-center justify-center rounded-2xl bg-gradient-to-br from-primary via-emerald-500 to-cyan-500 text-primary-foreground shadow-[0_14px_30px_rgba(13,128,87,0.35)] transition-transform duration-300 group-hover:rotate-6 group-hover:scale-105">
              <Sparkles className="h-4 w-4" />
            </span>
            <span className="text-lg font-extrabold tracking-[-0.06em] text-foreground">
              Football<span className="text-primary">AI</span>
            </span>
          </Link>

          <nav className="hidden items-center gap-1 rounded-full border border-border/80 bg-card/75 p-1.5 shadow-[0_10px_28px_rgba(15,23,42,0.08)] backdrop-blur md:flex">
            {navItems.map((item) => (
              <Link key={item.href} href={item.href}>
                <Button
                  variant={pathname === item.href ? "default" : "ghost"}
                  size="sm"
                  className={cn(
                    "px-3.5 text-sm font-semibold transition-all",
                    pathname === item.href &&
                      "shadow-[0_12px_22px_rgba(13,128,87,0.22)] ring-1 ring-primary/15",
                  )}
                >
                  {item.label}
                </Button>
              </Link>
            ))}
          </nav>

          <div className="flex items-center gap-2">
            <Button
              variant="ghost"
              size="icon"
              onClick={() => setShowSearch(true)}
              aria-label="Search"
              className="rounded-full border border-border/70 bg-card/60 shadow-sm hover:bg-accent hover:text-foreground"
            >
              <Search className="h-4 w-4" />
            </Button>
            <Button
              variant="ghost"
              size="icon"
              className="rounded-full border border-border/70 bg-card/60 shadow-sm md:hidden hover:bg-accent hover:text-foreground"
            >
              <Menu className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </header>

      <MobileNav items={navItems} currentPath={pathname} />

      <SearchDialog open={showSearch} onOpenChange={setShowSearch} />
    </>
  );
}
