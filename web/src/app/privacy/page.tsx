import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Privacy Policy",
  description: "How Football AI handles account and service information.",
};

export default function PrivacyPolicyPage() {
  return (
    <article className="mx-auto max-w-3xl space-y-8 py-5 sm:py-8">
      <header className="space-y-3">
        <p className="text-sm font-semibold uppercase tracking-widest text-primary">Privacy</p>
        <h1 className="text-3xl font-black tracking-tight sm:text-4xl">Privacy Policy</h1>
        <p className="text-sm text-muted-foreground">Last updated: October 15, 2026</p>
        <p className="text-base leading-7 text-muted-foreground sm:text-lg sm:leading-8">
          This policy explains what information Football AI may handle when you
          use the website and how it is used to provide and protect the service.
        </p>
      </header>

      <section className="space-y-3">
        <h2 className="text-2xl font-bold">Information we handle</h2>
        <p className="leading-7 text-muted-foreground">
          If you create an account, we handle the account details you provide,
          such as your email address and authentication information. When you
          use the site, technical information such as requested pages, device
          and browser details, and basic diagnostic logs may be processed to
          operate, secure, and troubleshoot the service.
        </p>
        <p className="leading-7 text-muted-foreground">
          If you use paid features, payment details are handled by the payment
          provider used for that transaction. We receive information needed to
          check or manage subscription status; we do not intend to store your
          full payment card number.
        </p>
      </section>

      <section className="space-y-3">
        <h2 className="text-2xl font-bold">How information is used</h2>
        <ul className="list-disc space-y-2 pl-6 leading-7 text-muted-foreground">
          <li>To provide account access, predictions, and subscription features.</li>
          <li>To maintain service security, prevent abuse, and diagnose errors.</li>
          <li>To communicate important account or service updates.</li>
          <li>To improve the reliability and usefulness of the site.</li>
        </ul>
      </section>

      <section className="space-y-3">
        <h2 className="text-2xl font-bold">Storage and sharing</h2>
        <p className="leading-7 text-muted-foreground">
          We retain information for as long as needed to provide the service,
          meet operational needs, and comply with applicable obligations. We
          may use service providers for hosting, authentication, analytics,
          payment processing, and football data. They receive only information
          needed for their services. We do not sell personal information.
        </p>
      </section>

      <section className="space-y-3">
        <h2 className="text-2xl font-bold">Your choices and contact</h2>
        <p className="leading-7 text-muted-foreground">
          You can stop using the site at any time. You may request access to,
          correction of, or deletion of account information by contacting the
          service operator through the contact method provided with your
          account. We will respond in line with applicable law. This policy may
          be updated as the service changes; the date above identifies the
          latest revision.
        </p>
      </section>
    </article>
  );
}
