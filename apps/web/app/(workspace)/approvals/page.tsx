import type { Approval } from "@fairhire/api-client";
import { StatusBadge } from "@fairhire/ui";
import Link from "next/link";
import { ApprovalDecisionForm } from "@/components/governance-actions";
import { PageIntro } from "@/components/page-intro";
import { getApprovals, getSystems } from "@/lib/api";

export const dynamic = "force-dynamic";

const stageLabel: Record<Approval["stage"], string> = {
  responsible_ai: "Responsible AI",
  hr: "HR",
  legal_dpo: "Legal / DPO",
};

const decisionTone = {
  pending: "review",
  approved: "approved",
  rejected: "blocked",
  expired: "insufficient",
} as const;

export default async function ApprovalsPage() {
  const [{ items, source }, systems] = await Promise.all([
    getApprovals(),
    getSystems(),
  ]);
  const systemNames = new Map(
    systems.items.map((item) => [item.id, item.name]),
  );
  const pending = items.filter((item) => item.decision === "pending").length;
  const chains = new Map<string, Approval[]>();
  for (const approval of items) {
    const key = `${approval.ai_system_id}:${approval.chain_version}`;
    chains.set(key, [...(chains.get(key) ?? []), approval]);
  }

  return (
    <>
      <PageIntro
        eyebrow={`${pending} decisions waiting · three accountable roles`}
        title="Release approval center"
        lead="Release approval is sequential. Responsible AI confirms the evidence, HR confirms the operating context, and Legal or DPO closes the gate only when no Critical finding remains unresolved without a valid exception."
        action={
          <Link className="fh-button" data-variant="secondary" href="/findings">
            Review findings
          </Link>
        }
      />
      <section className="approval-register" aria-label="Approval chains">
        {[...chains.entries()].map(([key, approvals]) => {
          const ordered = approvals.sort((a, b) => a.sequence - b.sequence);
          const systemId = ordered[0].ai_system_id;
          return (
            <article className="approval-chain" key={key}>
              <header>
                <div>
                  <p className="eyebrow">
                    Release gate · chain v{ordered[0].chain_version}
                  </p>
                  <h2>{systemNames.get(systemId) ?? systemId}</h2>
                </div>
                <Link href={`/systems/${systemId}`}>System record →</Link>
              </header>
              <ol>
                {ordered.map((approval) => (
                  <li key={approval.id} data-decision={approval.decision}>
                    <span className="approval-sequence">
                      0{approval.sequence}
                    </span>
                    <div className="approval-stage">
                      <strong>{stageLabel[approval.stage]}</strong>
                      <span>
                        {approval.approver_name ?? "Named reviewer required"}
                      </span>
                      {approval.reason && <p>{approval.reason}</p>}
                    </div>
                    <StatusBadge tone={decisionTone[approval.decision]}>
                      {approval.decision}
                    </StatusBadge>
                    <ApprovalDecisionForm
                      approval={approval}
                      disabled={source === "fixture"}
                    />
                  </li>
                ))}
              </ol>
            </article>
          );
        })}
        {!items.length && (
          <div className="empty-state">
            <h3>No active approval chain</h3>
            <p>
              Start a release review from an AI system after its audit evidence
              is ready.
            </p>
          </div>
        )}
      </section>
      {source === "fixture" && (
        <p className="offline-note">
          Review fixture · connect the API to record decisions.
        </p>
      )}
    </>
  );
}
