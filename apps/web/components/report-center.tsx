"use client";

import type { AISystem, Report } from "@fairhire/api-client";
import { StatusBadge } from "@fairhire/ui";
import Link from "next/link";
import { useState } from "react";
import { createBrowserApi } from "@/lib/browser-api";

const statusTone = {
  draft: "draft",
  approved: "approved",
  superseded: "insufficient",
} as const;

function key() {
  return crypto.randomUUID();
}

export function ReportCenter({
  initialReports,
  systems,
  offline,
}: {
  initialReports: Report[];
  systems: AISystem[];
  offline: boolean;
}) {
  const [reports, setReports] = useState(initialReports);
  const [systemId, setSystemId] = useState(systems[0]?.id ?? "");
  const [runId, setRunId] = useState("");
  const [title, setTitle] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const api = createBrowserApi();

  async function create(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setMessage("");
    try {
      const report = await api.createReport(
        {
          ai_system_id: systemId,
          audit_run_id: runId,
          title: title.trim() || null,
        },
        key(),
      );
      setReports((current) => [report, ...current]);
      setRunId("");
      setTitle("");
      setMessage(
        `Draft v${report.version} created with ${report.evidence_index.length} traceable references.`,
      );
    } catch (error) {
      setMessage(
        error instanceof Error ? error.message : "Could not create report.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function approve(report: Report) {
    setBusy(true);
    setMessage("");
    try {
      const updated = await api.approveReport(
        report.id,
        "Evidence package reviewed against the selected Audit Run",
        key(),
      );
      setReports((current) =>
        current.map((item) =>
          item.id === updated.id
            ? updated
            : item.ai_system_id === updated.ai_system_id &&
                item.status === "approved"
              ? { ...item, status: "superseded" }
              : item,
        ),
      );
      setMessage(
        `Report v${updated.version} approved. Its content hash is now frozen.`,
      );
    } catch (error) {
      setMessage(
        error instanceof Error ? error.message : "Could not approve report.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function download(report: Report, format: "pdf" | "json" | "csv") {
    setBusy(true);
    try {
      const blob = await api.downloadReport(report.id, format);
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `fairhire-${report.id}-v${report.version}.${format}`;
      anchor.click();
      URL.revokeObjectURL(url);
      setMessage(
        `${format.toUpperCase()} export recorded in the audit ledger.`,
      );
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Export failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <section
        className="evidence-package-maker"
        aria-labelledby="package-maker-title"
      >
        <div>
          <p className="eyebrow">Freeze a reproducible snapshot</p>
          <h2 id="package-maker-title">Create evidence package</h2>
          <p>
            A package binds seven report sections to one completed Audit Run.
            Later changes create a new version; they never rewrite the old one.
          </p>
        </div>
        <form onSubmit={create}>
          <label>
            AI system
            <select
              value={systemId}
              onChange={(event) => setSystemId(event.target.value)}
            >
              {systems.map((system) => (
                <option key={system.id} value={system.id}>
                  {system.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            Completed Audit Run ID
            <input
              value={runId}
              onChange={(event) => setRunId(event.target.value)}
              placeholder="run-…"
              required
            />
          </label>
          <label>
            Report title <span>optional</span>
            <input
              value={title}
              onChange={(event) => setTitle(event.target.value)}
            />
          </label>
          <button
            className="fh-button"
            disabled={busy || offline || !systems.length}
          >
            {busy ? "Building package…" : "Create draft"}
          </button>
        </form>
      </section>

      {message && (
        <p className="command-feedback" role="status">
          {message}
        </p>
      )}

      <section
        className="report-register"
        aria-label="Evidence package versions"
      >
        {reports.map((report) => (
          <article key={report.id}>
            <header>
              <div>
                <p className="eyebrow">Evidence package · v{report.version}</p>
                <h2>
                  <Link href={`/reports/${report.id}`}>{report.title}</Link>
                </h2>
                <span>
                  Audit {report.audit_run_id} · policy{" "}
                  {report.policy_pack_version}
                </span>
              </div>
              <StatusBadge tone={statusTone[report.status]}>
                {report.status}
              </StatusBadge>
            </header>
            <div className="report-proof-line">
              <div>
                <span>Traceable refs</span>
                <strong>{report.evidence_index.length}</strong>
              </div>
              <div>
                <span>Evidence gaps</span>
                <strong>{report.evidence_gaps.length}</strong>
              </div>
              <div>
                <span>Content hash</span>
                <code>{report.content_hash.slice(0, 12)}…</code>
              </div>
              <div>
                <span>Sections</span>
                <strong>{report.sections.length}/7</strong>
              </div>
            </div>
            <footer>
              <Link href={`/reports/${report.id}`}>Inspect evidence →</Link>
              {(["pdf", "json", "csv"] as const).map((format) => (
                <button
                  className="text-button"
                  disabled={busy}
                  key={format}
                  onClick={() => download(report, format)}
                >
                  {format.toUpperCase()}
                </button>
              ))}
              {report.status === "draft" && (
                <button
                  className="fh-button"
                  disabled={busy || report.evidence_gaps.length > 0}
                  onClick={() => approve(report)}
                >
                  Approve snapshot
                </button>
              )}
            </footer>
          </article>
        ))}
        {!reports.length && (
          <div className="empty-state evidence-empty">
            <p className="eyebrow">No frozen snapshots</p>
            <h3>Your first package starts with a completed Audit Run.</h3>
            <p>
              Enter its ID above. Unsupported conclusions will remain visible as
              Evidence Gaps.
            </p>
          </div>
        )}
      </section>
      {offline && (
        <p className="offline-note">
          API unavailable · report creation is disabled.
        </p>
      )}
    </>
  );
}
