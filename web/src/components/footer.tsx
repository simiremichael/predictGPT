import Link from "next/link";
import Image from "next/image";
const footerLinks = [
  { href: "/about", label: "About" },
  { href: "/contact", label: "Contact" },
  { href: "/privacy", label: "Privacy Policy" },
  { href: "/terms", label: "Terms of Service" },
];

export function Footer() {
  const year = new Date().getFullYear();

  return (
    <footer className="mt-14 border-t border-border/80 bg-card/70 backdrop-blur-sm">
      <div className="page-shell mx-auto px-1 py-10">
        <div className="grid grid-cols-1 gap-8 md:grid-cols-[1.4fr_1fr_1fr]">
          <div className="space-y-4">
            <div className="flex items-center gap-3">
              <Image
                src="/logo.png"
                alt="Football AI logo"
                width={36}
                height={36}
                className="h-9 w-9 shrink-0 rounded-xl object-contain"
              />
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
