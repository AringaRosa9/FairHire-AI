import type { Finding } from "@fairhire/api-client";
import { SeverityBadge, StatusBadge } from "@fairhire/ui";
import Link from "next/link";
import { PageIntro } from "@/components/page-intro";
import { getFindings, getSystems } from "@/lib/api";

export const dynamic = "force-dynamic";

const stateMeta: Record<
  Finding["status"],
  { label: string; tone: "draft" | "review" | "approved" | "insufficient" }
> = {
  open: { label: "Open", tone: "draft" },
  triaged: { label: "Triaged", tone: "review" },
  mitigating: { label: "Mitigating", tone: "review" },
  ready_for_retest: { label: "Ready for retest", tone: "review" },
  resolved: { label: "Resolved", tone: "approved" },
  accepted: { label: "Accepted exception", tone: "insufficient" },
};

function dateLabel(value: string) {
  const date = new Date(value);
  const today = new Date("2026-09-03T00:00:00Z");
  if (date.toDateString() === today.toDateString()) return "Today";
  return date.toLocaleDateString("en-GB", { day: "2-digit", month: "short" });
}

export default async function FindingsPage({
  searchParams,
}: {
  searchParams: Promise<{ state?: string }>;
}) {
  const [{ items, source }, systemsResult] = await Promise.all([
    getFindings(),
    getSystems(),
  ]);
  const { state } = await searchParams;
  const filtered = state
    ? items.filter((item) => item.status === state)
    : items;
  const systemNames = new Map(
    systemsResult.items.map((system) => [system.id, system.name]),
  );
  const activeCount = items.filter(
    (item) => !["resolved", "accepted"].includes(item.status),
  ).length;
  const criticalCount = items.filter(
    (item) => item.severity === "critical" && item.status !== "resolved",
  ).length;

  return (
    <>
      <PageIntro
        eyebrow={`${activeCount} active · ${criticalCount} critical release blocker${criticalCount === 1 ? "" : "s"}`}
        title="Problems that need someone to act"
        lead="Every finding keeps the source test, evidence, mapped controls, accountable owner and decision history together—from triage through retest or a time-limited exception."
        action={
          <Link
            className="fh-button"
            data-variant="secondary"
            href="/approvals"
          >
            Open approval center
          </Link>
        }
      />
      <nav className="finding-filters" aria-label="Filter findings by state">
        <Link aria-current={!state ? "page" : undefined} href="/findings">
          All <span>{items.length}</span>
        </Link>
        {(["open", "mitigating", "ready_for_retest", "accepted"] as const).map(
          (filter) => (
            <Link
              aria-current={state === filter ? "page" : undefined}
              href={`/findings?state=${filter}`}
              key={filter}
            >
              {stateMeta[filter].label}{" "}
              <span>
                {items.filter((item) => item.status === filter).length}
              </span>
            </Link>
          ),
        )}
        <small>
          {source === "api" ? "Live register" : "Review fixture · API offline"}
        </small>
      </nav>
      <section className="finding-list" aria-label="Governance findings">
        {filtered.length ? (
          filtered.map((finding) => (
            <article className="finding-row" key={finding.id}>
              <SeverityBadge level={finding.severity} />
              <div>
                <h2>
                  <Link href={`/findings/${finding.id}`}>{finding.title}</Link>
                </h2>
                <p>
                  {systemNames.get(finding.ai_system_id) ??
                    finding.ai_system_id}{" "}
                  · {finding.id} · {finding.evidence_refs.length} evidence refs
                </p>
              </div>
              <div>
                <strong>{finding.owner_name}</strong>
                <span>Accountable owner</span>
              </div>
              <div>
                <strong>{dateLabel(finding.due_at)}</strong>
                <span>Due date</span>
              </div>
              <StatusBadge tone={stateMeta[finding.status].tone}>
                {stateMeta[finding.status].label}
              </StatusBadge>
            </article>
          ))
        ) : (
          <div className="empty-state">
            <h3>No findings in this state</h3>
            <p>
              Try the full register or move an item forward from its detail
              page.
            </p>
          </div>
        )}
      </section>
    </>
  );
}
