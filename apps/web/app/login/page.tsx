import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = { title: "Sign in" };

export default function LoginPage() {
  return (
    <main className="login-page">
      <section className="login-brand" aria-labelledby="login-brand-title">
        <span className="brand-mark large" aria-hidden="true">
          Fh
        </span>
        <p className="eyebrow">Recruitment AI assurance</p>
        <h1 id="login-brand-title">Decisions deserve an evidence trail.</h1>
        <p>
          Inspect risk, assign accountability, and preserve a reproducible
          record without pretending uncertainty is certainty.
        </p>
      </section>
      <section className="login-panel" aria-labelledby="login-title">
        <p className="eyebrow">Northstar Hiring Group · EU</p>
        <h2 id="login-title">Sign in to your workspace</h2>
        <p>
          Use your organization&apos;s identity provider. Multi-factor
          authentication is managed by your administrator.
        </p>
        <Link className="fh-button" data-variant="primary" href="/portfolio">
          Continue with SSO <span aria-hidden="true">→</span>
        </Link>
        <small>
          Development mode uses a named local test identity. It is disabled in
          production.
        </small>
      </section>
    </main>
  );
}
