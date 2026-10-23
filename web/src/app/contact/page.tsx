import type { Metadata } from "next";

const contactEmail = "sales@xeltontechnologies.com.ng";

export const metadata: Metadata = {
  title: "Contact",
  description: "Contact the Football AI team by email.",
};

export default function ContactPage() {
  return (
    <article className="mx-auto max-w-3xl space-y-8 py-5 sm:py-8">
      <header className="space-y-3">
        <p className="text-sm font-semibold uppercase tracking-widest text-primary">
          Get in touch
        </p>
        <h1 className="text-3xl font-black tracking-tight sm:text-4xl">Contact us</h1>
        <p className="text-base leading-7 text-muted-foreground sm:text-lg sm:leading-8">
          Have a question about Football AI, your account, or a subscription?
          Send our team an email and we’ll be glad to help.
        </p>
      </header>

      <section className="rounded-2xl border border-border bg-card p-4 sm:p-6">
        <h2 className="text-xl font-bold">Email</h2>
        <p className="mt-2 leading-7 text-muted-foreground">
          Contact us at{" "}
          <a
            className="font-semibold text-primary underline-offset-4 hover:underline"
            href={`mailto:${contactEmail}`}
          >
            {contactEmail}
          </a>
          .
        </p>
      </section>
    </article>
  );
}
