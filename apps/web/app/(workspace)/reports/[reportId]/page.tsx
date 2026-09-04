import { StatusBadge } from "@fairhire/ui";
import Link from "next/link";
import { notFound } from "next/navigation";
import { getReportDetail } from "@/lib/api";

export const dynamic = "force-dynamic";

const tone = {
  draft: "draft",
  approved: "approved",
  superseded: "insufficient",
} as const;

export default async function ReportDetailPage({
  params,
}: {
  params: Promise<{ reportId: string }>;
}) {
  const { reportId } = await params;
  const { report } = await getReportDetail(reportId);
  if (!report) notFound();

  return (
    <>
      <Link className="back-link" href="/reports">
        ← Evidence packages
      </Link>
      <header className="report-dossier-head">
        <div>
          <p className="eyebrow">
            Immutable evidence dossier · version {report.version}
          </p>
          <h1>{report.title}</h1>
          <p>
            Audit Run {report.audit_run_id} · {report.policy_pack_version}
          </p>
        </div>
        <StatusBadge tone={tone[report.status]}>{report.status}</StatusBadge>
      </header>
      <dl className="report-integrity">
        <div>
          <dt>Content SHA-256</dt>
          <dd>
            <code>{report.content_hash}</code>
          </dd>
        </div>
        <div>
          <dt>Created by</dt>
          <dd>{report.created_by}</dd>
        </div>
        <div>
          <dt>Approved by</dt>
          <dd>{report.approved_by ?? "Awaiting approval"}</dd>
        </div>
        <div>
          <dt>Traceable references</dt>
          <dd>{report.evidence_index.length}</dd>
        </div>
      </dl>

      <div className="dossier-layout">
        <nav aria-label="Report sections">
          <p className="eyebrow">Contents</p>
          <ol>
            {report.sections.map((section, index) => (
              <li key={section.key}>
                <a href={`#${section.key}`}>
                  0{index + 1} {section.title}
                </a>
              </li>
            ))}
          </ol>
        </nav>
        <div className="dossier-sections">
          {report.sections.map((section, index) => (
            <section id={section.key} key={section.key}>
              <span className="section-number">0{index + 1}</span>
              <div>
                <p className="eyebrow">{section.key.replaceAll("_", " ")}</p>
                <h2>{section.title}</h2>
                <p>{section.summary}</p>
                <span className="section-record-count">
                  {section.items.length} source record
                  {section.items.length === 1 ? "" : "s"}
                </span>
              </div>
            </section>
          ))}
        </div>
      </div>

      <section className="trace-ledger" aria-labelledby="trace-ledger-title">
        <header>
          <div>
            <p className="eyebrow">Metric provenance</p>
            <h2 id="trace-ledger-title">Every reported number has a source</h2>
          </div>
          <span>{report.evidence_index.length} references</span>
        </header>
        <div
          className="trace-table"
          role="table"
          aria-label="Evidence traceability"
        >
          {report.evidence_index.map((item) => (
            <div role="row" key={item.reference}>
              <div role="cell">
                <strong>{item.label}</strong>
                <span>{item.reference}</span>
              </div>
              <div role="cell">
                <span>Value</span>
                <strong>{item.value ?? "Snapshot"}</strong>
              </div>
              <div role="cell">
                <span>Method</span>
                <strong>{item.method ?? "—"}</strong>
              </div>
              <div role="cell">
                <span>Run</span>
                <code>{item.audit_run_id}</code>
              </div>
            </div>
          ))}
        </div>
      </section>
    </>
  );
}
