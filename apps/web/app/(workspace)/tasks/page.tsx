import { StatusBadge } from "@fairhire/ui";
import Link from "next/link";
import { RemediationTaskControl } from "@/components/governance-actions";
import { PageIntro } from "@/components/page-intro";
import { getFindings, getRemediationTasks } from "@/lib/api";
import { currentTimestamp } from "@/lib/time";

export const dynamic = "force-dynamic";

export default async function TasksPage() {
  const [{ items, source }, findings] = await Promise.all([
    getRemediationTasks(),
    getFindings(),
  ]);
  const findingTitles = new Map(
    findings.items.map((finding) => [finding.id, finding.title]),
  );
  const now = currentTimestamp();
  const overdue = items.filter(
    (task) =>
      new Date(task.due_at).getTime() < now &&
      ["open", "in_progress"].includes(task.status),
  ).length;

  return (
    <>
      <PageIntro
        eyebrow={`${overdue} overdue · ${items.length} tracked remediation tasks`}
        title="Work due before release"
        lead="This queue keeps implementation ownership, due dates and completion evidence close to the risk record. A task is not complete until its evidence references are attached."
        action={
          <Link className="fh-button" data-variant="secondary" href="/findings">
            Open risk register
          </Link>
        }
      />
      <section
        className="task-register"
        aria-label="Remediation task due dates"
      >
        {items.map((task) => {
          const isOverdue =
            new Date(task.due_at).getTime() < now &&
            ["open", "in_progress"].includes(task.status);
          return (
            <article key={task.id}>
              <div className="task-date" data-overdue={isOverdue}>
                <strong>
                  {new Date(task.due_at).toLocaleDateString("en-GB", {
                    day: "2-digit",
                  })}
                </strong>
                <span>
                  {new Date(task.due_at).toLocaleDateString("en-GB", {
                    month: "short",
                  })}
                </span>
              </div>
              <div className="task-main">
                <h2>{task.title}</h2>
                <p>
                  <Link href={`/findings/${task.finding_id}`}>
                    {findingTitles.get(task.finding_id) ?? task.finding_id}
                  </Link>
                </p>
              </div>
              <div className="task-owner">
                <strong>{task.owner_name}</strong>
                <span>Accountable owner</span>
              </div>
              <StatusBadge
                tone={task.status === "completed" ? "approved" : "review"}
              >
                {isOverdue ? "Overdue" : task.status.replaceAll("_", " ")}
              </StatusBadge>
              <RemediationTaskControl
                task={task}
                disabled={source === "fixture"}
              />
            </article>
          );
        })}
        {!items.length && (
          <div className="empty-state">
            <h3>No remediation work is waiting</h3>
            <p>New tasks appear here when they are assigned from a finding.</p>
          </div>
        )}
      </section>
      {source === "fixture" && (
        <p className="offline-note">
          Review fixture · connect the API to update task state and attach
          evidence.
        </p>
      )}
    </>
  );
}
