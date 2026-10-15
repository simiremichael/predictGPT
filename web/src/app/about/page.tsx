import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "About",
  description: "Learn about Football AI and how its football predictions work.",
};

export default function AboutPage() {
  return (
    <article className="mx-auto max-w-3xl space-y-8 py-8">
      <header className="space-y-3">
        <p className="text-sm font-semibold uppercase tracking-widest text-primary">About us</p>
        <h1 className="text-4xl font-black tracking-tight">Football insight, made clearer.</h1>
        <p className="text-lg leading-8 text-muted-foreground">
          Football AI helps fans explore match data and understand the range of
          possible outcomes before a game.
        </p>
      </header>

      <section className="space-y-3">
        <h2 className="text-2xl font-bold">How it works</h2>
        <p className="leading-7 text-muted-foreground">
          We combine available team and fixture statistics with probability
          models, including Poisson-based score estimates. Where available,
          additional research signals may add context. The result is a set of
          estimates such as likely scorelines and match outcomes, not a promise
          of what will happen.
        </p>
      </section>

      <section className="space-y-3">
        <h2 className="text-2xl font-bold">Our approach</h2>
        <p className="leading-7 text-muted-foreground">
          Football is uncertain. We aim to present predictions as probabilities
          and make the supporting match information easier to explore. Data may
          be delayed, incomplete, or corrected by its source, and model estimates
          can be wrong.
        </p>
      </section>

      <section className="rounded-2xl border border-border bg-card p-5">
        <h2 className="text-xl font-bold">Use predictions responsibly</h2>
        <p className="mt-2 leading-7 text-muted-foreground">
          Football AI is for informational and entertainment purposes. It is
          not financial advice, betting advice, or a guarantee of an outcome.
          Please make your own decisions and follow the laws and age limits that
          apply where you live.
        </p>
      </section>
    </article>
  );
}
