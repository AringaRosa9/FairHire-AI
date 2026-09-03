import { SeverityBadge, StatusBadge } from "@fairhire/ui";
import Link from "next/link";
import { notFound } from "next/navigation";
import {
  FindingWorkflowActions,
  RemediationTaskControl,
} from "@/components/governance-actions";
import { getFindingDetail, getSystemDetail } from "@/lib/api";

export const dynamic = "force-dynamic";

const statusTone = {
  open: "draft",
  triaged: "review",
  mitigating: "review",
  ready_for_retest: "review",
  resolved: "approved",
  accepted: "insufficient",
} as const;

export default async function FindingDetailPage({
  params,
}: {
  params: Promise<{ findingId: string }>;
}) {
  const { findingId } = await params;
  const { finding, source } = await getFindingDetail(findingId);
  if (!finding) notFound();
  const { system } = await getSystemDetail(finding.ai_system_id);

  return (
    <>
      <Link className="back-link" href="/findings">
        ← Back to findings
      </Link>
      <header className="finding-detail-header">
        <div className="finding-title-mark">
          <SeverityBadge level={finding.severity} />
          <div>
            <p className="eyebrow">
              {finding.id} · {system?.name ?? finding.ai_system_id}
            </p>
            <h1>{finding.title}</h1>
            <p>{finding.description}</p>
          </div>
        </div>
        <StatusBadge tone={statusTone[finding.status]}>
          {finding.status.replaceAll("_", " ")}
        </StatusBadge>
      </header>
      <section
        className="finding-accountability"
        aria-label="Finding accountability"
      >
        <div>
          <span>Owner</span>
          <strong>{finding.owner_name}</strong>
        </div>
        <div>
          <span>Due</span>
          <strong>
            {new Date(finding.due_at).toLocaleDateString("en-GB", {
              dateStyle: "medium",
            })}
          </strong>
        </div>
        <div>
          <span>Confidence</span>
          <strong>{finding.confidence}</strong>
        </div>
        <div>
          <span>Affected</span>
          <strong>
            {finding.affected_groups.join(", ") || "Not specified"}
          </strong>
        </div>
      </section>
      <div className="finding-evidence-grid">
        <section>
          <p className="eyebrow">Traceability</p>
          <h2>Evidence references</h2>
          <ul>
            {finding.evidence_refs.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </section>
        <section>
          <p className="eyebrow">Control mapping</p>
          <h2>Required control</h2>
          <p>
            {finding.recommended_control ??
              "Control decision is pending triage."}
          </p>
          <ul>
            {finding.control_refs.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </section>
      </div>
      {finding.status === "accepted" && (
        <section className="risk-exception">
          <p className="eyebrow">Time-limited risk acceptance</p>
          <h2>Residual risk remains visible</h2>
          <p>{finding.residual_risk}</p>
          <dl>
            <div>
              <dt>Approved by</dt>
              <dd>{finding.accepted_by}</dd>
            </div>
            <div>
              <dt>Valid until</dt>
              <dd>
                {finding.accepted_until
                  ? new Date(finding.accepted_until).toLocaleString("en-GB")
                  : "Missing expiry"}
              </dd>
            </div>
          </dl>
        </section>
      )}
      <div className="governance-history">
        <section>
          <p className="eyebrow">Remediation</p>
          <h2>Owned tasks</h2>
          {finding.tasks.length ? (
            finding.tasks.map((task) => (
              <article key={task.id}>
                <div>
                  <strong>{task.title}</strong>
                  <span>
                    {task.owner_name} · due{" "}
                    {new Date(task.due_at).toLocaleDateString("en-GB")}
                  </span>
                </div>
                <StatusBadge
                  tone={task.status === "completed" ? "approved" : "review"}
                >
                  {task.status.replaceAll("_", " ")}
                </StatusBadge>
                <RemediationTaskControl
                  task={task}
                  disabled={source === "fixture"}
                />
              </article>
            ))
          ) : (
            <p className="quiet-empty">
              No remediation task has been assigned yet.
            </p>
          )}
        </section>
        <section>
          <p className="eyebrow">Verification</p>
          <h2>Retest record</h2>
          {finding.retests.length ? (
            finding.retests.map((retest) => (
              <article key={retest.id}>
                <div>
                  <strong>{retest.outcome}</strong>
                  <span>
                    {retest.audit_run_id} ·{" "}
                    {new Date(retest.performed_at).toLocaleDateString("en-GB")}
                  </span>
                </div>
                <p>{retest.notes}</p>
              </article>
            ))
          ) : (
            <p className="quiet-empty">
              No reproducible retest has been linked.
            </p>
          )}
        </section>
      </div>
      <FindingWorkflowActions
        finding={finding}
        disabled={source === "fixture"}
      />
    </>
  );
}
