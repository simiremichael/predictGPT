import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Terms of Service",
  description: "Terms for using the Football AI website and predictions.",
};

export default function TermsPage() {
  return (
    <article className="mx-auto max-w-3xl space-y-8 py-8">
      <header className="space-y-3">
        <p className="text-sm font-semibold uppercase tracking-widest text-primary">Terms</p>
        <h1 className="text-4xl font-black tracking-tight">Terms of Service</h1>
        <p className="text-sm text-muted-foreground">Last updated: October 15, 2026</p>
        <p className="text-lg leading-8 text-muted-foreground">
          These terms apply when you access or use Football AI. By using the
          service, you agree to follow them. If you do not agree, do not use the
          service.
        </p>
      </header>

      <section className="space-y-3">
        <h2 className="text-2xl font-bold">The service</h2>
        <p className="leading-7 text-muted-foreground">
          Football AI provides football statistics, match information, and
          model-generated predictions for informational and entertainment
          purposes. Predictions are estimates based on available data and
          assumptions. Football matches are uncertain, results are not
          guaranteed, and information may be incomplete, delayed, or inaccurate.
        </p>
      </section>

      <section className="space-y-3">
        <h2 className="text-2xl font-bold">Acceptable use</h2>
        <p className="leading-7 text-muted-foreground">
          Use the service lawfully and do not disrupt its operation, attempt
          unauthorized access, misuse another person’s account, or copy and
          redistribute site content in ways that violate applicable rights or
          laws. You are responsible for activity carried out through your
          account and for keeping your sign-in details secure.
        </p>
      </section>

      <section className="space-y-3">
        <h2 className="text-2xl font-bold">Accounts and subscriptions</h2>
        <p className="leading-7 text-muted-foreground">
          Some features may require an account or paid subscription. You agree
          to provide accurate account information. Subscription pricing,
          billing periods, renewals, and cancellation options are shown during
          checkout or in your account. Payment processing is handled by the
          applicable payment provider, whose terms may also apply.
        </p>
      </section>

      <section className="space-y-3">
        <h2 className="text-2xl font-bold">No betting or financial advice</h2>
        <p className="leading-7 text-muted-foreground">
          Nothing on Football AI is betting, investment, or financial advice.
          Do not rely on a prediction as the sole basis for a decision. If you
          choose to gamble, you must meet the legal age requirement and obey
          local laws. Please gamble responsibly.
        </p>
      </section>

      <section className="space-y-3">
        <h2 className="text-2xl font-bold">Availability and liability</h2>
        <p className="leading-7 text-muted-foreground">
          We may update, suspend, or discontinue features as the service
          develops. To the extent permitted by law, the service is provided
          without a guarantee that it will always be available, error-free, or
          suitable for a particular purpose. Nothing in these terms excludes
          rights or liability that cannot legally be excluded.
        </p>
      </section>

      <section className="space-y-3">
        <h2 className="text-2xl font-bold">Changes to these terms</h2>
        <p className="leading-7 text-muted-foreground">
          We may revise these terms when the service or applicable requirements
          change. The updated version will be posted on this page with a revised
          date. Continued use after an update means you accept the revised
          terms.
        </p>
      </section>
    </article>
  );
}
