import Link from "next/link";
import { Code, X } from "lucide-react";

const footerLinks = [
  { href: "/about", label: "About" },
  { href: "/docs", label: "Documentation" },
  { href: "/privacy", label: "Privacy" },
  { href: "/terms", label: "Terms" },
];

export function Footer() {
  const year = new Date().getFullYear();

  return (
    <footer className="mt-14 border-t border-border/80 bg-card/70 backdrop-blur-sm">
      <div className="page-shell mx-auto px-1 py-10">
        <div className="grid grid-cols-1 gap-8 md:grid-cols-[1.4fr_1fr_1fr_1fr]">
          <div className="space-y-4">
            <div className="flex items-center gap-3">
              <span className="flex h-9 w-9 items-center justify-center rounded-2xl bg-gradient-to-br from-primary to-emerald-500 text-sm font-bold text-primary-foreground shadow-[0_12px_24px_rgba(13,128,87,0.3)]">
                FA
              </span>
              <span className="text-xl font-black tracking-[-0.06em] text-foreground">
                Football<span className="text-primary">AI</span>
              </span>
            </div>
            <p className="max-w-xs text-sm leading-6 text-muted-foreground">
              AI-powered football match predictions using transparent Poisson
              models, research signals, and live market intelligence.
            </p>
          </div>

          <div className="space-y-3">
            <h3 className="text-sm font-semibold uppercase tracking-[0.12em] text-muted-foreground">
              Pages
            </h3>
            <ul className="space-y-2">
              {footerLinks.map((link) => (
                <li key={link.href}>
                  <Link
                    href={link.href}
                    className="text-sm text-muted-foreground transition-colors hover:text-foreground"
                  >
                    {link.label}
                  </Link>
                </li>
              ))}
            </ul>
          </div>

          <div className="space-y-3">
            <h3 className="text-sm font-semibold uppercase tracking-[0.12em] text-muted-foreground">
              Legal
            </h3>
            <ul className="space-y-2">
              <li>
                <Link
                  href="/terms"
                  className="text-sm text-muted-foreground transition-colors hover:text-foreground"
                >
                  Terms of Service
                </Link>
              </li>
              <li>
                <Link
                  href="/privacy"
                  className="text-sm text-muted-foreground transition-colors hover:text-foreground"
                >
                  Privacy Policy
                </Link>
              </li>
            </ul>
          </div>

          <div className="space-y-3">
            <h3 className="text-sm font-semibold uppercase tracking-[0.12em] text-muted-foreground">
              Follow
            </h3>
            <div className="flex gap-2">
              <a
                href="#"
                className="flex h-9 w-9 items-center justify-center rounded-full border border-border bg-card text-muted-foreground transition-colors hover:border-primary/30 hover:bg-primary/5 hover:text-primary"
                aria-label="X"
              >
                <X className="h-4 w-4" />
              </a>
              <a
                href="#"
                className="flex h-9 w-9 items-center justify-center rounded-full border border-border bg-card text-muted-foreground transition-colors hover:border-primary/30 hover:bg-primary/5 hover:text-primary"
                aria-label="GitHub"
              >
                <Code className="h-4 w-4" />
              </a>
            </div>
          </div>
        </div>

        <div className="mt-8 border-t border-border/80 pt-5 text-center text-sm text-muted-foreground">
          <p>
            &copy; {year} Football AI. Predictions are probabilistic and should
            not be used for gambling.
          </p>
        </div>
      </div>
    </footer>
  );
}
