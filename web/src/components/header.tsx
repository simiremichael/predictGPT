"use client";

import Link from "next/link";
import Image from "next/image";
import { usePathname } from "next/navigation";
import { Menu, Search, X } from "lucide-react";
import { useState, useEffect } from "react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { MobileNav } from "@/components/mobile-nav";
import { SearchDialog } from "@/components/search-dialog";
import { useAuth } from "@/contexts/auth";

const navItems = [
  { href: "/", label: "Home" },
  { href: "/matches", label: "Matches" },
  { href: "/predictions", label: "Predictions" },
  { href: "/leagues", label: "Leagues" },
  { href: "/teams", label: "Teams" },
  { href: "/results", label: "Results" },
  // { href: "/admin", label: "Admin" },
];

export function Header() {
  const pathname = usePathname();
  const [showSearch, setShowSearch] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);
  const { user, isSubscribed, logout } = useAuth();

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
          <Link
            href="/"
            className="group flex min-w-0 items-center gap-2 sm:gap-2.5"
          >
            <Image
              src="/logo.png"
              alt="Football AI logo"
              width={40}
              height={40}
              priority
              className="h-10 w-10 shrink-0 rounded-xl object-contain transition-transform duration-300 group-hover:scale-105"
            />
            <span className="truncate text-base font-extrabold tracking-[-0.06em] text-foreground sm:text-lg">
              Football<span className="text-primary">AI</span>
            </span>
          </Link>

          <nav className="hidden items-center gap-1 rounded-full border border-border/80 bg-card/75 p-1.5 shadow-[0_10px_28px_rgba(15,23,42,0.08)] backdrop-blur md:flex">
            {navItems.map((item) => (
              <Link key={item.href} href={item.href} className="cursor-pointer">
                <Button
                  variant={pathname === item.href ? "default" : "ghost"}
                  size="sm"
                  className={cn(
                    "px-3.5 text-sm font-semibold transition-all cursor-pointer",
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
            {user ? (
              <>
                {isSubscribed ? (
                  <span className="hidden items-center gap-1.5 rounded-full border border-border/80 bg-card/60 px-2.5 py-1 text-xs font-medium text-green-400 md:flex">
                    <span className="h-2 w-2 rounded-full bg-green-400" />
                    Premium
                  </span>
                ) : (
                  <Link href="/subscription">
                    <Button size="sm" variant="outline">
                      Upgrade
                    </Button>
                  </Link>
                )}
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={logout}
                  className="hidden md:inline-flex"
                >
                  Logout
                </Button>
              </>
            ) : (
              <Link href="/login">
                <Button size="sm" variant="ghost">
                  Login
                </Button>
              </Link>
            )}
            <Button
              variant="ghost"
              size="icon"
              onClick={() => setMobileMenuOpen((open) => !open)}
              aria-label={
                mobileMenuOpen
                  ? "Close navigation menu"
                  : "Open navigation menu"
              }
              aria-expanded={mobileMenuOpen}
              className="rounded-full border border-border/70 bg-card/60 shadow-sm md:hidden hover:bg-accent hover:text-foreground"
            >
              {mobileMenuOpen ? (
                <X className="h-4 w-4" />
              ) : (
                <Menu className="h-4 w-4" />
              )}
            </Button>
          </div>
        </div>
      </header>

      <MobileNav
        items={navItems}
        currentPath={pathname}
        open={mobileMenuOpen}
        onNavigate={() => setMobileMenuOpen(false)}
      />

      <SearchDialog open={showSearch} onOpenChange={setShowSearch} />
    </>
  );
}
