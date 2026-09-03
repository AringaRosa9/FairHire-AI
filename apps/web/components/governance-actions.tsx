"use client";

import type {
  Approval,
  FindingDetail,
  RemediationTask,
} from "@fairhire/api-client";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { createBrowserApi } from "@/lib/browser-api";

const nextState: Partial<
  Record<FindingDetail["status"], FindingDetail["status"]>
> = {
  open: "triaged",
  triaged: "mitigating",
  mitigating: "ready_for_retest",
  resolved: "open",
  accepted: "mitigating",
};

const nextLabel: Partial<Record<FindingDetail["status"], string>> = {
  open: "Confirm triage",
  triaged: "Start mitigation",
  mitigating: "Send to retest",
  resolved: "Reopen finding",
  accepted: "Start mitigation",
};

function commandKey(prefix: string) {
  return `${prefix}-${crypto.randomUUID()}`;
}

export function FindingWorkflowActions({
  finding,
  disabled,
}: {
  finding: FindingDetail;
  disabled: boolean;
}) {
  const router = useRouter();
  const api = createBrowserApi();
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [reason, setReason] = useState(
    "Evidence reviewed by the accountable owner",
  );

  async function run(action: () => Promise<unknown>, success: string) {
    setBusy(true);
    setMessage("");
    try {
      await action();
      setMessage(success);
      router.refresh();
    } catch (error) {
      setMessage(
        error instanceof Error
          ? error.message
          : "The update could not be saved.",
      );
    } finally {
      setBusy(false);
    }
  }

  const target = nextState[finding.status];
  return (
    <section className="governance-command" aria-labelledby="workflow-actions">
      <div>
        <p className="eyebrow">Accountable action</p>
        <h2 id="workflow-actions">Move the record forward</h2>
        <p>
          Every command requires a reason and becomes a named event in the
          immutable audit log.
        </p>
      </div>
      {disabled ? (
        <p className="command-notice">
          Connect the API to make changes. This is an offline review fixture.
        </p>
      ) : (
        <div className="command-forms">
          {target && (
            <form
              onSubmit={(event) => {
                event.preventDefault();
                void run(
                  () =>
                    api.transitionFinding(
                      finding.id,
                      { status: target, reason },
                      commandKey("finding-transition"),
                    ),
                  `Finding moved to ${target.replaceAll("_", " ")}.`,
                );
              }}
            >
              <label>
                Decision reason
                <textarea
                  value={reason}
                  onChange={(event) => setReason(event.target.value)}
                />
              </label>
              <button
                className="fh-button"
                data-variant="primary"
                disabled={busy}
              >
                {nextLabel[finding.status]}
              </button>
            </form>
          )}
          {finding.status !== "resolved" && (
            <form
              onSubmit={(event) => {
                event.preventDefault();
                const form = new FormData(event.currentTarget);
                void run(
                  () =>
                    api.createRemediationTask(
                      finding.id,
                      {
                        title: String(form.get("taskTitle")),
                        description: String(form.get("taskDescription")),
                        owner_id: String(form.get("taskOwnerId")),
                        owner_name: String(form.get("taskOwnerName")),
                        due_at: new Date(
                          String(form.get("taskDueAt")),
                        ).toISOString(),
                      },
                      commandKey("remediation-task"),
                    ),
                  "Remediation task assigned.",
                );
              }}
            >
              <h3>Assign remediation</h3>
              <label>
                Task
                <input name="taskTitle" minLength={3} required />
              </label>
              <label>
                Implementation note
                <textarea name="taskDescription" />
              </label>
              <div className="command-field-pair">
                <label>
                  Owner name
                  <input name="taskOwnerName" minLength={2} required />
                </label>
                <label>
                  Owner identity
                  <input name="taskOwnerId" minLength={2} required />
                </label>
              </div>
              <label>
                Due at
                <input name="taskDueAt" type="datetime-local" required />
              </label>
              <button
                className="fh-button"
                data-variant="secondary"
                disabled={busy}
              >
                Assign task
              </button>
            </form>
          )}
          {["triaged", "mitigating", "ready_for_retest"].includes(
            finding.status,
          ) && (
            <form
              onSubmit={(event) => {
                event.preventDefault();
                const form = new FormData(event.currentTarget);
                void run(
                  () =>
                    api.acceptFinding(
                      finding.id,
                      {
                        residual_risk: String(form.get("residualRisk")),
                        reason: String(form.get("acceptanceReason")),
                        expires_at: new Date(
                          String(form.get("expiresAt")),
                        ).toISOString(),
                      },
                      commandKey("risk-acceptance"),
                    ),
                  "Time-limited risk acceptance recorded.",
                );
              }}
            >
              <h3>Time-limited exception</h3>
              <label>
                Residual risk
                <textarea name="residualRisk" minLength={10} required />
              </label>
              <label>
                Acceptance reason
                <textarea name="acceptanceReason" minLength={10} required />
              </label>
              <label>
                Valid until
                <input name="expiresAt" type="datetime-local" required />
              </label>
              <button
                className="fh-button"
                data-variant="secondary"
                disabled={busy}
              >
                Record exception
              </button>
            </form>
          )}
          {finding.status === "ready_for_retest" && (
            <form
              onSubmit={(event) => {
                event.preventDefault();
                const form = new FormData(event.currentTarget);
                void run(
                  () =>
                    api.recordFindingRetest(
                      finding.id,
                      {
                        audit_run_id: String(form.get("auditRunId")),
                        outcome: form.get("outcome") as
                          | "resolved"
                          | "improved"
                          | "persisted"
                          | "regressed",
                        notes: String(form.get("notes")),
                      },
                      commandKey("finding-retest"),
                    ),
                  "Retest evidence linked to the finding.",
                );
              }}
            >
              <h3>Record retest</h3>
              <label>
                Successful audit run ID
                <input name="auditRunId" required />
              </label>
              <label>
                Outcome
                <select name="outcome" defaultValue="resolved">
                  <option value="resolved">Resolved</option>
                  <option value="improved">
                    Improved, continue mitigation
                  </option>
                  <option value="persisted">Persisted</option>
                  <option value="regressed">Regressed</option>
                </select>
              </label>
              <label>
                Evidence note
                <textarea name="notes" minLength={10} required />
              </label>
              <button
                className="fh-button"
                data-variant="primary"
                disabled={busy}
              >
                Save retest
              </button>
            </form>
          )}
        </div>
      )}
      {message && (
        <p className="command-feedback" role="status">
          {message}
        </p>
      )}
    </section>
  );
}

export function RemediationTaskControl({
  task,
  disabled,
}: {
  task: RemediationTask;
  disabled: boolean;
}) {
  const router = useRouter();
  const api = createBrowserApi();
  const [message, setMessage] = useState("");
  const [evidence, setEvidence] = useState("");
  const [busy, setBusy] = useState(false);
  const target = task.status === "open" ? "in_progress" : "completed";

  if (!["open", "in_progress"].includes(task.status)) return null;
  async function update() {
    setBusy(true);
    setMessage("");
    try {
      await api.updateRemediationTask(
        task.id,
        {
          status: target,
          reason:
            target === "completed"
              ? "Implementation completed and evidence attached"
              : "Assigned owner started implementation",
          evidence_refs:
            target === "completed"
              ? evidence
                  .split(",")
                  .map((item) => item.trim())
                  .filter(Boolean)
              : [],
        },
        commandKey("remediation-status"),
      );
      setMessage(`Task moved to ${target.replaceAll("_", " ")}.`);
      router.refresh();
    } catch (error) {
      setMessage(
        error instanceof Error ? error.message : "Task could not be updated.",
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="task-command">
      {target === "completed" && (
        <label>
          Evidence references, comma separated
          <input
            value={evidence}
            onChange={(event) => setEvidence(event.target.value)}
            disabled={disabled}
          />
        </label>
      )}
      <button
        className="text-button"
        disabled={
          disabled || busy || (target === "completed" && !evidence.trim())
        }
        onClick={() => void update()}
      >
        {target === "completed" ? "Complete with evidence" : "Start task"}
      </button>
      {message && <p role="status">{message}</p>}
    </div>
  );
}

export function ApprovalDecisionForm({
  approval,
  disabled,
}: {
  approval: Approval;
  disabled: boolean;
}) {
  const router = useRouter();
  const api = createBrowserApi();
  const [reason, setReason] = useState(
    "Evidence and controls reviewed for this stage",
  );
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);

  async function decide(decision: "approved" | "rejected") {
    setBusy(true);
    setMessage("");
    try {
      await api.decideApproval(
        approval.id,
        { decision, reason },
        commandKey(`approval-${decision}`),
      );
      setMessage(`${approval.stage.replaceAll("_", " / ")} decision recorded.`);
      router.refresh();
    } catch (error) {
      setMessage(
        error instanceof Error
          ? error.message
          : "Decision could not be recorded.",
      );
    } finally {
      setBusy(false);
    }
  }

  if (approval.decision !== "pending") return null;
  return (
    <div className="approval-command">
      <label>
        Decision reason
        <input
          value={reason}
          onChange={(event) => setReason(event.target.value)}
          disabled={disabled}
        />
      </label>
      <div>
        <button
          className="fh-button"
          data-variant="primary"
          disabled={disabled || busy}
          onClick={() => void decide("approved")}
        >
          Approve stage
        </button>
        <button
          className="fh-button"
          data-variant="secondary"
          disabled={disabled || busy}
          onClick={() => void decide("rejected")}
        >
          Reject
        </button>
      </div>
      {message && <p role="status">{message}</p>}
    </div>
  );
}

export function ApprovalChainControl({
  systemId,
  disabled,
}: {
  systemId: string;
  disabled: boolean;
}) {
  const router = useRouter();
  const api = createBrowserApi();
  const [reason, setReason] = useState(
    "Audit evidence is ready for sequential release review",
  );
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);

  async function start() {
    setBusy(true);
    setMessage("");
    try {
      await api.startApprovalChain(
        systemId,
        reason,
        commandKey("approval-chain"),
      );
      setMessage("A new three-stage approval chain is ready.");
      router.refresh();
    } catch (error) {
      setMessage(
        error instanceof Error
          ? error.message
          : "The approval chain could not start.",
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="approval-chain-control">
      <label>
        Submission reason
        <input
          value={reason}
          onChange={(event) => setReason(event.target.value)}
          disabled={disabled}
        />
      </label>
      <button
        className="fh-button"
        data-variant="primary"
        disabled={disabled || busy}
        onClick={() => void start()}
      >
        Start new approval chain
      </button>
      {message && <p role="status">{message}</p>}
    </div>
  );
}
