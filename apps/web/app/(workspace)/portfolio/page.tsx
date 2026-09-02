import type { Metadata } from "next";
import Link from "next/link";
import { StatusBadge, SeverityBadge } from "@fairhire/ui";
import { PageIntro } from "@/components/page-intro";
import { getSystems } from "@/lib/api";

export const metadata: Metadata = { title: "Portfolio" };
export const dynamic = "force-dynamic";

const status = {
  approved: { tone: "approved" as const, label: "Approved" },
  review_required: { tone: "review" as const, label: "Review required" },
  blocked: { tone: "blocked" as const, label: "Blocked" },
  draft: { tone: "draft" as const, label: "Draft" },
  insufficient_evidence: {
    tone: "insufficient" as const,
    label: "Insufficient evidence",
  },
};

export default async function PortfolioPage() {
  const { items, source } = await getSystems();
  const counts = items.reduce(
    (result, system) => ({
      ...result,
      [system.release_status]: (result[system.release_status] ?? 0) + 1,
    }),
    {} as Record<string, number>,
  );
  return (
    <>
      <PageIntro
        eyebrow="Monday, 1 September · Decision week"
        title="What needs a human decision?"
        lead="A current view of release posture, unresolved evidence and controls approaching expiry. Every status is tied to a named owner and a reproducible audit run."
        action={
          <Link className="fh-button" data-variant="primary" href="/onboarding">
            Start first audit
          </Link>
        }
      />
      <section className="release-ledger" aria-labelledby="release-heading">
        <div className="ledger-heading">
          <p className="eyebrow">Release posture</p>
          <h2 id="release-heading">4 systems in scope</h2>
          <span>
            {source === "api"
              ? "Live organization data"
              : "Review fixture · API offline"}
          </span>
        </div>
        <div className="ledger-values">
          <div>
            <strong>{counts.approved ?? 0}</strong>
            <span>Approved</span>
          </div>
          <div>
            <strong>{counts.review_required ?? 0}</strong>
            <span>Need review</span>
          </div>
          <div>
            <strong>{counts.blocked ?? 0}</strong>
            <span>Blocked</span>
          </div>
          <div>
            <strong>
              74<span className="unit">%</span>
            </strong>
            <span>Evidence complete</span>
          </div>
        </div>
      </section>
      <div className="portfolio-grid">
        <section className="systems-queue" aria-labelledby="queue-heading">
          <div className="section-heading">
            <div>
              <p className="eyebrow">Nearest decision first</p>
              <h2 id="queue-heading">Systems being checked</h2>
            </div>
            <Link href="/systems">Open registry →</Link>
          </div>
          <div className="system-list">
            {items.map((system, index) => (
              <article className="system-line" key={system.id}>
                <span className="system-index">0{index + 1}</span>
                <div>
                  <h3>{system.name}</h3>
                  <p>
                    {system.purpose} · {system.owner_name}
                  </p>
                </div>
                <div>
                  <span>{system.jurisdictions.join(" · ")}</span>
                  <small>Assessment v{system.assessment_version}</small>
                </div>
                <StatusBadge tone={status[system.release_status].tone}>
                  {status[system.release_status].label}
                </StatusBadge>
                <Link
                  href={`/systems/${system.id}`}
                  aria-label={`Open ${system.name}`}
                >
                  ›
                </Link>
              </article>
            ))}
          </div>
        </section>
        <aside className="decision-rail" aria-labelledby="decision-heading">
          <p className="eyebrow">Accountability</p>
          <h2 id="decision-heading">Due next</h2>
          <div className="rail-item">
            <SeverityBadge level="high" />
            <div>
              <strong>Pause emotion analysis trial</strong>
              <span>Ana Silva · due today</span>
            </div>
          </div>
          <div className="rail-item">
            <SeverityBadge level="high" />
            <div>
              <strong>Confirm career-gap control</strong>
              <span>Maya Chen · 2 days</span>
            </div>
          </div>
          <div className="rail-item">
            <SeverityBadge level="medium" />
            <div>
              <strong>Approve test strategy v3</strong>
              <span>Elias Roth · 5 days</span>
            </div>
          </div>
          <Link className="text-link" href="/findings">
            See all 8 action items →
          </Link>
        </aside>
      </div>
    </>
  );
}
