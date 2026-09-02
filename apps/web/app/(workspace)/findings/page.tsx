import { PageIntro } from "@/components/page-intro";
import { SeverityBadge, StatusBadge } from "@fairhire/ui";

const findings = [
  {
    severity: "high" as const,
    title: "Career gaps may make women less likely to be selected",
    meta: "TalentRank EU · F-104 · 4 supporting tests",
    owner: "Maya Chen",
    due: "03 Sep",
    tone: "review" as const,
    state: "Being fixed",
  },
  {
    severity: "high" as const,
    title: "Emotion analysis may be a prohibited use",
    meta: "InterviewSense EU · F-097 · legal classification",
    owner: "Ana Silva",
    due: "Today",
    tone: "blocked" as const,
    state: "Not resolved",
  },
  {
    severity: "medium" as const,
    title: "Later outcomes remain incomplete",
    meta: "TalentRank EU · F-105 · data quality",
    owner: "Elias Roth",
    due: "18 Sep",
    tone: "draft" as const,
    state: "Scheduled",
  },
];

export default function FindingsPage() {
  return (
    <>
      <PageIntro
        eyebrow="8 open · 2 due this week"
        title="Problems that need someone to act"
        lead="Each problem shows what happened, who owns it, what must happen next, and when it is due."
      />
      <section className="finding-list" aria-label="Open findings">
        {findings.map((finding) => (
          <article className="finding-row" key={finding.title}>
            <SeverityBadge level={finding.severity} />
            <div>
              <h2>{finding.title}</h2>
              <p>{finding.meta}</p>
            </div>
            <div>
              <strong>{finding.owner}</strong>
              <span>Accountable owner</span>
            </div>
            <div>
              <strong>{finding.due}</strong>
              <span>Due date</span>
            </div>
            <StatusBadge tone={finding.tone}>{finding.state}</StatusBadge>
          </article>
        ))}
      </section>
    </>
  );
}
