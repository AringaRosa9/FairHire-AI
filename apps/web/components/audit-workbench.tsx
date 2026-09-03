"use client";

import type {
  AuditMetricSummary,
  AuditRun,
  BackgroundJob,
  MetricResult,
} from "@fairhire/api-client";
import { StatusBadge } from "@fairhire/ui";
import type { Route } from "next";
import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { createBrowserApi } from "@/lib/browser-api";

type View = "summary" | "fairness" | "data-quality";

const runTones = {
  queued: "review",
  running: "review",
  succeeded: "approved",
  failed: "blocked",
  cancelling: "review",
  cancelled: "draft",
} as const;

const metricTones = {
  pass: "approved",
  review_required: "review",
  insufficient_evidence: "insufficient",
} as const;

const metricLabels: Record<string, string> = {
  missing_values: "Missing values",
  duplicate_identifiers: "Duplicate identifiers",
  sample_size: "Sample size",
  outliers: "Outlier scan",
  group_coverage: "Group coverage",
  time_coverage: "Time coverage",
  label_leakage: "Label leakage",
  train_test_overlap: "Train / test overlap",
  selection_rate: "Selection rate",
  demographic_parity_difference: "Demographic parity difference",
  demographic_parity_ratio: "Demographic parity ratio",
  true_positive_rate: "True positive rate",
  false_positive_rate: "False positive rate",
  equal_opportunity_difference: "Equal opportunity difference",
  equalized_odds_difference: "Equalized odds difference",
  precision: "Precision",
  calibration: "Calibration gap",
  error_rate: "Error rate",
};

function formatMetric(metric: MetricResult) {
  if (metric.value === null) return "Not available";
  if (metric.metric_key === "sample_size")
    return Math.round(metric.value).toLocaleString();
  if (metric.metric_key === "time_coverage")
    return `${metric.value.toFixed(1)} days`;
  if (metric.metric_key.includes("ratio")) return metric.value.toFixed(2);
  return `${(metric.value * 100).toFixed(1)}%`;
}

function formatInterval(metric: MetricResult) {
  if (metric.lower_bound === null || metric.upper_bound === null)
    return "No interval available";
  const ratio = metric.metric_key.includes("ratio");
  return ratio
    ? `${metric.lower_bound.toFixed(2)}–${metric.upper_bound.toFixed(2)}`
    : `${(metric.lower_bound * 100).toFixed(1)}–${(metric.upper_bound * 100).toFixed(1)}%`;
}

function WorkbenchTabs({ runId, view }: { runId: string; view: View }) {
  const tabs = [
    ["summary", "Summary", `/audits/${runId}/summary`],
    ["fairness", "Group differences", `/audits/${runId}/fairness`],
    ["data-quality", "Data quality", `/audits/${runId}/data-quality`],
  ] as const;
  return (
    <nav className="workbench-tabs" aria-label="Audit results">
      {tabs.map(([key, label, href]) => (
        <Link
          key={key}
          href={href as Route}
          aria-current={view === key ? "page" : undefined}
        >
          {label}
        </Link>
      ))}
    </nav>
  );
}

function MetricTable({ metrics }: { metrics: MetricResult[] }) {
  if (!metrics.length) {
    return (
      <div className="audit-empty">
        <p className="eyebrow">Awaiting evidence</p>
        <h2>No metrics have been published yet.</h2>
        <p>
          The worker will publish a complete, versioned result set when
          calculation finishes.
        </p>
      </div>
    );
  }
  return (
    <div
      className="metric-ledger"
      role="region"
      aria-label="Audit metric ledger"
      tabIndex={0}
    >
      <table>
        <thead>
          <tr>
            <th scope="col">Measure</th>
            <th scope="col">Group</th>
            <th scope="col">Result</th>
            <th scope="col">95% interval</th>
            <th scope="col">Evidence state</th>
            <th scope="col">Trace</th>
          </tr>
        </thead>
        <tbody>
          {metrics.map((metric) => (
            <tr key={metric.id}>
              <th scope="row">
                <strong>
                  {metricLabels[metric.metric_key] ??
                    metric.metric_key.replaceAll("_", " ")}
                </strong>
                <small>{metric.method.replaceAll("_", " ")}</small>
              </th>
              <td>
                {metric.comparison_group ?? "Dataset"}
                {metric.reference_group &&
                metric.comparison_group !== metric.reference_group ? (
                  <small>vs {metric.reference_group}</small>
                ) : null}
              </td>
              <td className="metric-number">{formatMetric(metric)}</td>
              <td className="metric-number muted">{formatInterval(metric)}</td>
              <td>
                <StatusBadge tone={metricTones[metric.status]}>
                  {metric.status.replaceAll("_", " ")}
                </StatusBadge>
              </td>
              <td>
                <details className="metric-trace">
                  <summary>Counts &amp; policy</summary>
                  <span>
                    {Object.keys(metric.raw_counts).length
                      ? JSON.stringify(metric.raw_counts)
                      : "Counts suppressed below the privacy floor or unavailable."}
                  </span>
                  <small>
                    {String(
                      metric.threshold_source.source_id ??
                        "No decision threshold",
                    )}
                    {metric.threshold !== null
                      ? ` · ${metric.threshold_operator} ${metric.threshold}`
                      : ""}
                  </small>
                </details>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function AuditWorkbench({ runId, view }: { runId: string; view: View }) {
  const api = useMemo(() => createBrowserApi(), []);
  const [run, setRun] = useState<AuditRun | null>(null);
  const [job, setJob] = useState<BackgroundJob | null>(null);
  const [results, setResults] = useState<AuditMetricSummary | null>(null);
  const [error, setError] = useState("");
  const refresh = useCallback(async () => {
    try {
      const nextRun = await api.getAuditRun(runId);
      const [nextJob, nextResults] = await Promise.all([
        api.getJob(nextRun.job_id),
        api.getAuditMetrics(runId),
      ]);
      setRun(nextRun);
      setJob(nextJob);
      setResults(nextResults);
      setError("");
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : "Audit evidence is unavailable.",
      );
    }
  }, [api, runId]);

  useEffect(() => {
    const initialTimer = window.setTimeout(() => void refresh(), 0);
    if (
      run?.status === "succeeded" ||
      run?.status === "failed" ||
      run?.status === "cancelled"
    ) {
      return () => window.clearTimeout(initialTimer);
    }
    const timer = window.setInterval(() => void refresh(), 3000);
    return () => {
      window.clearTimeout(initialTimer);
      window.clearInterval(timer);
    };
  }, [refresh, run?.status]);

  const metrics = results?.items ?? [];
  const visibleMetrics =
    view === "fairness"
      ? metrics.filter((metric) => metric.category === "fairness")
      : view === "data-quality"
        ? metrics.filter((metric) => metric.category === "data_quality")
        : metrics.filter(
            (metric) =>
              metric.status !== "pass" ||
              [
                "sample_size",
                "demographic_parity_ratio",
                "selection_rate",
              ].includes(metric.metric_key),
          );
  const passCount = results?.status_counts.pass ?? 0;
  const reviewCount = results?.status_counts.review_required ?? 0;
  const gapCount = results?.status_counts.insufficient_evidence ?? 0;

  return (
    <div className="audit-workbench">
      <Link className="back-link" href="/portfolio">
        ← Back to portfolio
      </Link>
      <header className="detail-header audit-header">
        <div>
          <p className="eyebrow">Audit run · reproducible evidence</p>
          <h1>
            {run ? `Run ${run.id.slice(0, 18)}…` : "Loading audit evidence"}
          </h1>
          <p>
            Risk signals follow the approved test strategy. They are not legal
            determinations.
          </p>
        </div>
        {run ? (
          <StatusBadge tone={runTones[run.status]}>
            {run.status.replaceAll("_", " ")}
          </StatusBadge>
        ) : null}
      </header>
      <WorkbenchTabs runId={runId} view={view} />
      {error ? (
        <div className="form-error" role="alert">
          <strong>Evidence unavailable</strong>
          <p>{error}</p>
        </div>
      ) : null}

      {view === "summary" && run && job ? (
        <>
          <section
            className="audit-scoreline"
            aria-label="Audit evidence summary"
          >
            <div>
              <span>Review required</span>
              <strong>{reviewCount}</strong>
              <small>policy signals</small>
            </div>
            <div>
              <span>Insufficient evidence</span>
              <strong>{gapCount}</strong>
              <small>never treated as pass</small>
            </div>
            <div>
              <span>Passed checks</span>
              <strong>{passCount}</strong>
              <small>under this strategy</small>
            </div>
            <div>
              <span>Worker progress</span>
              <strong>{job.progress}%</strong>
              <small>
                attempt {job.attempt} of {job.max_attempts}
              </small>
            </div>
          </section>
          <section className="evidence-strip">
            <div>
              <span>Policy pack</span>
              <strong>{run.policy_pack_version}</strong>
            </div>
            <div>
              <span>Calculation</span>
              <strong>{results?.calculation_version ?? "Pending"}</strong>
            </div>
            <div>
              <span>Random seed</span>
              <strong>
                {String(run.config_snapshot.random_seed ?? "Pending")}
              </strong>
            </div>
            <div>
              <span>Data fingerprint</span>
              <strong className="hash-value">{run.data_fingerprint}</strong>
            </div>
          </section>
        </>
      ) : null}

      <section className="audit-section">
        <div className="section-heading">
          <div>
            <p className="eyebrow">
              {view === "summary" ? "Decision queue" : "Evidence ledger"}
            </p>
            <h2>
              {view === "fairness"
                ? "Group differences"
                : view === "data-quality"
                  ? "Data quality checks"
                  : "Results needing attention"}
            </h2>
          </div>
          <p>
            {view === "fairness"
              ? "Every comparison keeps its reference group, raw counts, uncertainty and threshold provenance."
              : "Unknown, missing or undersized evidence remains visible instead of being folded into a passing state."}
          </p>
        </div>
        <MetricTable metrics={visibleMetrics} />
      </section>

      {results?.evidence_gaps.length ? (
        <aside className="evidence-gaps" aria-labelledby="evidence-gap-title">
          <div>
            <p className="eyebrow">Evidence gaps</p>
            <h2 id="evidence-gap-title">Conclusions we cannot support yet</h2>
          </div>
          <ul>
            {results.evidence_gaps.slice(0, 8).map((gap) => (
              <li key={gap}>{gap}</li>
            ))}
          </ul>
        </aside>
      ) : null}
    </div>
  );
}
