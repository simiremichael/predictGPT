import type { Metadata } from "next";

const contactEmail = "sales@xeltontechnologies.com.ng";

export const metadata: Metadata = {
  title: "Contact",
  description: "Contact the Football AI team by email.",
};

export default function ContactPage() {
  return (
    <article className="mx-auto max-w-3xl space-y-8 py-8">
      <header className="space-y-3">
        <p className="text-sm font-semibold uppercase tracking-widest text-primary">
          Get in touch
        </p>
        <h1 className="text-4xl font-black tracking-tight">Contact us</h1>
        <p className="text-lg leading-8 text-muted-foreground">
          Have a question about Football AI, your account, or a subscription?
          Send our team an email and we’ll be glad to help.
        </p>
      </header>

      <section className="rounded-2xl border border-border bg-card p-6">
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
