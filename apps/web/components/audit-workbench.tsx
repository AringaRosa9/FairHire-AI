"use client";

import type {
  AuditComparison,
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

export type AuditView =
  | "summary"
  | "fairness"
  | "data-quality"
  | "proxy"
  | "counterfactual"
  | "explainability"
  | "drift"
  | "comparison";

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
  warning: "review",
  critical: "blocked",
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
  proxy_risk: "Proxy risk",
  counterfactual_consistency: "Counterfactual consistency",
  global_feature_importance: "Global feature importance",
  explanation_available: "Explanation available",
  baseline_available: "Baseline available",
  data_distribution_drift: "Data distribution drift",
  performance_drift: "Performance drift",
  fairness_selection_drift: "Fairness drift · selection",
  fairness_error_drift: "Fairness drift · error",
  fairness_calibration_drift: "Fairness drift · calibration",
  explanation_rank_drift: "Explanation rank drift",
  explanation_contribution_drift: "Explanation contribution drift",
  age_output_trend: "Continuous age trend",
  age_threshold_discontinuity: "Age threshold discontinuity",
};

function record(value: unknown): Record<string, unknown> {
  return typeof value === "object" && value !== null
    ? (value as Record<string, unknown>)
    : {};
}

function numberValue(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function formatScalar(value: number | null, signed = false) {
  if (value === null) return "Not available";
  return `${signed && value > 0 ? "+" : ""}${(value * 100).toFixed(1)}%`;
}

function formatMetric(metric: MetricResult) {
  if (metric.value === null) return "Not available";
  if (metric.metric_key === "sample_size")
    return Math.round(metric.value).toLocaleString();
  if (metric.metric_key === "time_coverage")
    return `${metric.value.toFixed(1)} days`;
  if (metric.metric_key.includes("ratio")) return metric.value.toFixed(2);
  return formatScalar(metric.value, metric.category === "drift");
}

function formatInterval(metric: MetricResult) {
  if (metric.lower_bound === null || metric.upper_bound === null)
    return "No interval available";
  const ratio = metric.metric_key.includes("ratio");
  return ratio
    ? `${metric.lower_bound.toFixed(2)}–${metric.upper_bound.toFixed(2)}`
    : `${formatScalar(metric.lower_bound)}–${formatScalar(metric.upper_bound)}`;
}

function WorkbenchTabs({ runId, view }: { runId: string; view: AuditView }) {
  const tabs = [
    ["summary", "Summary"],
    ["fairness", "Group differences"],
    ["data-quality", "Data quality"],
    ["proxy", "Proxy"],
    ["counterfactual", "Counterfactual"],
    ["explainability", "Explainability"],
    ["drift", "Drift"],
    ["comparison", "Version compare"],
  ] as const;
  return (
    <nav className="workbench-tabs" aria-label="Audit results">
      {tabs.map(([key, label]) => (
        <Link
          key={key}
          href={`/audits/${runId}/${key}` as Route}
          aria-current={view === key ? "page" : undefined}
        >
          {label}
        </Link>
      ))}
    </nav>
  );
}

function MetricTable({ metrics }: { metrics: MetricResult[] }) {
  if (!metrics.length) return <AuditEmpty />;
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

function AuditEmpty({ children }: { children?: React.ReactNode }) {
  return (
    <div className="audit-empty">
      <p className="eyebrow">Awaiting evidence</p>
      <h2>No supported conclusion yet.</h2>
      <p>
        {children ??
          "The worker will publish a complete, versioned result set when the required evidence is available."}
      </p>
    </div>
  );
}

function ProxyLedger({ metrics }: { metrics: MetricResult[] }) {
  if (!metrics.length) return <AuditEmpty />;
  const proxyFindings = metrics.filter(
    (metric) => metric.metric_key === "proxy_risk",
  );
  const ageMetrics = metrics.filter(
    (metric) => metric.metric_key !== "proxy_risk",
  );
  return (
    <>
      <div className="proxy-ledger">
        {proxyFindings.map((metric) => {
          const details = record(metric.details);
          const association = record(details.association_evidence);
          const impact = record(details.output_impact_evidence);
          return (
            <article className="proxy-row" key={metric.id}>
              <div className="proxy-subject">
                <p className="eyebrow">
                  {metric.protected_attribute ?? "Protected attribute"}
                </p>
                <h3>{metric.comparison_group ?? "Unnamed feature"}</h3>
                <StatusBadge tone={metricTones[metric.status]}>
                  {metric.status.replaceAll("_", " ")}
                </StatusBadge>
                <small>
                  Confidence · {String(details.confidence ?? "low")}
                </small>
              </div>
              <div className="evidence-column">
                <span>01 · Group association</span>
                <strong>
                  {formatScalar(
                    numberValue(association.normalized_mutual_information),
                  )}
                </strong>
                <p>Normalized mutual information</p>
                <small>
                  Predictability lift{" "}
                  {formatScalar(
                    numberValue(association.predictability_lift_over_majority),
                  )}
                </small>
              </div>
              <div className="evidence-column">
                <span>02 · Output impact</span>
                <strong>{formatScalar(numberValue(impact.value))}</strong>
                <p>
                  {String(impact.method ?? "Unavailable").replaceAll("_", " ")}
                </p>
                <small>
                  {String(details.limitation ?? "No limitation recorded")}
                </small>
              </div>
            </article>
          );
        })}
      </div>
      {ageMetrics.length ? (
        <div className="age-evidence">
          <p className="eyebrow">Age-specific evidence</p>
          <MetricTable metrics={ageMetrics} />
        </div>
      ) : null}
    </>
  );
}

function CounterfactualLedger({ metrics }: { metrics: MetricResult[] }) {
  const metric = metrics[0];
  if (!metric) return <AuditEmpty />;
  const details = record(metric.details);
  const pairs = Array.isArray(details.pair_records)
    ? details.pair_records.map(record)
    : [];
  const invalid = Number(metric.raw_counts.invalid_pairs ?? 0);
  return (
    <div className="counterfactual-panel">
      <div className="counterfactual-verdict">
        <p className="eyebrow">Matched-pair consistency</p>
        <strong>{formatMetric(metric)}</strong>
        <StatusBadge tone={metricTones[metric.status]}>
          {metric.status.replaceAll("_", " ")}
        </StatusBadge>
        <p>
          {String(metric.raw_counts.valid_pairs ?? 0)} valid pairs · {invalid}{" "}
          rejected pair{invalid === 1 ? "" : "s"}
        </p>
      </div>
      {pairs.length ? (
        <div
          className="pair-ledger"
          role="region"
          aria-label="Counterfactual pair records"
          tabIndex={0}
        >
          <table>
            <thead>
              <tr>
                <th>Pair</th>
                <th>Only changed variable</th>
                <th>Original</th>
                <th>Counterfactual</th>
                <th>Output</th>
              </tr>
            </thead>
            <tbody>
              {pairs.map((pair, index) => (
                <tr key={String(pair.pair_id ?? index)}>
                  <th>{String(pair.pair_id ?? index + 1)}</th>
                  <td>{String(pair.changed_field ?? "Invalid")}</td>
                  <td>{String(pair.original_value ?? "—")}</td>
                  <td>{String(pair.counterfactual_value ?? "—")}</td>
                  <td>{pair.output_changed ? "Changed" : "Stable"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <AuditEmpty>
          Define matched pairs with exactly one permitted input change to make
          this experiment reproducible.
        </AuditEmpty>
      )}
    </div>
  );
}

function ExplainabilityLedger({
  metrics,
  run,
}: {
  metrics: MetricResult[];
  run: AuditRun;
}) {
  if (!metrics.length) return <AuditEmpty />;
  const firstDetails = record(metrics[0].details);
  const max = Math.max(...metrics.map((metric) => metric.value ?? 0), 0.000001);
  return (
    <>
      <aside className="method-boundary">
        <div>
          <p className="eyebrow">Method boundary</p>
          <h3>
            {metrics[0].method === "black_box_sensitivity"
              ? "SHAP unavailable — degraded safely"
              : "Global SHAP attribution"}
          </h3>
          <p>
            {String(
              firstDetails.method_boundary ?? "No method boundary recorded.",
            )}
          </p>
        </div>
        <dl>
          <div>
            <dt>Model version</dt>
            <dd>{run.model_version_id}</dd>
          </div>
          <div>
            <dt>Data fingerprint</dt>
            <dd>{run.data_fingerprint.slice(0, 16)}…</dd>
          </div>
          <div>
            <dt>Background</dt>
            <dd>{String(firstDetails.background_dataset ?? "Not used")}</dd>
          </div>
          <div>
            <dt>Random seed</dt>
            <dd>{String(firstDetails.random_seed ?? "Not recorded")}</dd>
          </div>
        </dl>
      </aside>
      <ol className="importance-ledger">
        {metrics.map((metric) => {
          const details = record(metric.details);
          const correlated = Array.isArray(details.correlated_features)
            ? details.correlated_features.join(", ")
            : "";
          return (
            <li key={metric.id}>
              <span className="importance-rank">
                {String(details.rank ?? "—").padStart(2, "0")}
              </span>
              <div>
                <strong>{metric.comparison_group ?? "Unknown feature"}</strong>
                <span className="importance-track" aria-hidden="true">
                  <i
                    style={{
                      transform: `scaleX(${(metric.value ?? 0) / max})`,
                    }}
                  />
                </span>
                <small>
                  {correlated
                    ? `Correlated with ${correlated}; attribution may be split.`
                    : String(details.attribution_warning ?? "")}
                </small>
              </div>
              <b>{formatScalar(metric.value)}</b>
            </li>
          );
        })}
      </ol>
    </>
  );
}

function DriftLedger({
  metrics,
  baselineRunId,
}: {
  metrics: MetricResult[];
  baselineRunId: string | null;
}) {
  if (!baselineRunId)
    return (
      <AuditEmpty>
        Select an explicit approved baseline Run when creating the audit.
        Current data never silently replaces historical alerts.
      </AuditEmpty>
    );
  if (!metrics.length) return <AuditEmpty />;
  return (
    <div className="drift-ledger">
      <p className="baseline-note">
        <span>Baseline</span>
        <strong>{baselineRunId}</strong>
      </p>
      {metrics.map((metric) => {
        const details = record(metric.details);
        return (
          <article key={metric.id}>
            <div>
              <p className="eyebrow">{String(details.drift_type ?? "drift")}</p>
              <h3>
                {metric.comparison_group ?? metricLabels[metric.metric_key]}
              </h3>
              <small>{metric.method.replaceAll("_", " ")}</small>
            </div>
            <div className="drift-values">
              <span>
                Baseline{" "}
                <strong>
                  {formatScalar(numberValue(details.baseline_value))}
                </strong>
              </span>
              <span>
                Current{" "}
                <strong>
                  {formatScalar(numberValue(details.current_value))}
                </strong>
              </span>
              <span>
                Change <strong>{formatMetric(metric)}</strong>
              </span>
            </div>
            <div>
              <StatusBadge tone={metricTones[metric.status]}>
                {metric.status.replaceAll("_", " ")}
              </StatusBadge>
              <p>
                {String(
                  details.change_kind ?? "distribution_change",
                ).replaceAll("_", " ")}
              </p>
            </div>
          </article>
        );
      })}
    </div>
  );
}

function ComparisonLedger({
  comparison,
}: {
  comparison: AuditComparison | null;
}) {
  if (!comparison)
    return (
      <AuditEmpty>
        An explicit same-system baseline is required before versions can be
        compared.
      </AuditEmpty>
    );
  return (
    <div className="comparison-ledger">
      <div className="comparison-head">
        <div>
          <span>Baseline</span>
          <strong>{comparison.baseline_model_version_id}</strong>
          <small>{comparison.baseline_run_id}</small>
        </div>
        <b aria-hidden="true">→</b>
        <div>
          <span>Current</span>
          <strong>{comparison.current_model_version_id}</strong>
          <small>{comparison.current_run_id}</small>
        </div>
      </div>
      <div className="comparison-governance">
        <div>
          <span>Baseline change reason</span>
          <p>{comparison.baseline_change_reason}</p>
        </div>
        <div>
          <span>Approval evidence</span>
          <strong>{comparison.baseline_approval_ref}</strong>
        </div>
      </div>
      <div
        className="metric-ledger"
        role="region"
        aria-label="Version comparison"
        tabIndex={0}
      >
        <table>
          <thead>
            <tr>
              <th>Measure</th>
              <th>Scope</th>
              <th>Baseline</th>
              <th>Current</th>
              <th>Delta</th>
              <th>State change</th>
            </tr>
          </thead>
          <tbody>
            {comparison.items.map((item) => (
              <tr
                key={`${item.category}:${item.metric_key}:${item.protected_attribute}:${item.comparison_group}`}
              >
                <th>
                  {metricLabels[item.metric_key] ??
                    item.metric_key.replaceAll("_", " ")}
                  <small>{item.category}</small>
                </th>
                <td>
                  {item.comparison_group ??
                    item.protected_attribute ??
                    "Dataset"}
                </td>
                <td className="metric-number">
                  {formatScalar(item.baseline_value)}
                </td>
                <td className="metric-number">
                  {formatScalar(item.current_value)}
                </td>
                <td className="metric-number">
                  {formatScalar(item.delta, true)}
                </td>
                <td>
                  {item.baseline_status.replaceAll("_", " ")} →{" "}
                  {item.current_status.replaceAll("_", " ")}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

const viewCopy: Record<
  AuditView,
  { eyebrow: string; title: string; description: string }
> = {
  summary: {
    eyebrow: "Decision queue",
    title: "Results needing attention",
    description:
      "Unknown, missing or undersized evidence remains visible instead of being folded into a passing state.",
  },
  fairness: {
    eyebrow: "Evidence ledger",
    title: "Group differences",
    description:
      "Every comparison keeps its reference group, raw counts, uncertainty and threshold provenance.",
  },
  "data-quality": {
    eyebrow: "Evidence ledger",
    title: "Data quality checks",
    description:
      "Input quality and coverage determine which downstream conclusions this audit can support.",
  },
  proxy: {
    eyebrow: "Dual evidence",
    title: "Proxy signal review",
    description:
      "A feature is escalated only when protected-group association and model-output impact can be traced together.",
  },
  counterfactual: {
    eyebrow: "Controlled experiment",
    title: "Matched-pair consistency",
    description:
      "Only pairs with one permitted input change are valid; rejected pairs remain in the experiment record.",
  },
  explainability: {
    eyebrow: "Model behavior",
    title: "Global explanation",
    description:
      "Attribution is descriptive, not causal. Unsupported models degrade to a named sensitivity method.",
  },
  drift: {
    eyebrow: "Continuous monitoring",
    title: "Baseline drift",
    description:
      "Distribution movement is separated from harmful performance decline, with warning and critical thresholds.",
  },
  comparison: {
    eyebrow: "Version history",
    title: "Evidence comparison",
    description:
      "Aligned measures preserve both model versions, data fingerprints and evidence-state changes.",
  },
};

export function AuditWorkbench({
  runId,
  view,
}: {
  runId: string;
  view: AuditView;
}) {
  const api = useMemo(() => createBrowserApi(), []);
  const [run, setRun] = useState<AuditRun | null>(null);
  const [job, setJob] = useState<BackgroundJob | null>(null);
  const [results, setResults] = useState<AuditMetricSummary | null>(null);
  const [comparison, setComparison] = useState<AuditComparison | null>(null);
  const [error, setError] = useState("");
  const refresh = useCallback(async () => {
    try {
      const nextRun = await api.getAuditRun(runId);
      const [nextJob, nextResults] = await Promise.all([
        api.getJob(nextRun.job_id),
        api.getAuditMetrics(runId),
      ]);
      let nextComparison: AuditComparison | null = null;
      if (view === "comparison" && nextRun.baseline_run_id) {
        nextComparison = await api.compareAuditRun(
          runId,
          nextRun.baseline_run_id,
        );
      }
      setRun(nextRun);
      setJob(nextJob);
      setResults(nextResults);
      setComparison(nextComparison);
      setError("");
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : "Audit evidence is unavailable.",
      );
    }
  }, [api, runId, view]);

  useEffect(() => {
    const initialTimer = window.setTimeout(() => void refresh(), 0);
    if (["succeeded", "failed", "cancelled"].includes(run?.status ?? ""))
      return () => window.clearTimeout(initialTimer);
    const timer = window.setInterval(() => void refresh(), 3000);
    return () => {
      window.clearTimeout(initialTimer);
      window.clearInterval(timer);
    };
  }, [refresh, run?.status]);

  const metrics = results?.items ?? [];
  const categories: Partial<Record<AuditView, MetricResult["category"]>> = {
    fairness: "fairness",
    "data-quality": "data_quality",
    proxy: "proxy",
    counterfactual: "counterfactual",
    explainability: "explainability",
    drift: "drift",
  };
  const visibleMetrics = categories[view]
    ? metrics.filter((metric) => metric.category === categories[view])
    : metrics.filter(
        (metric) =>
          metric.status !== "pass" ||
          [
            "sample_size",
            "demographic_parity_ratio",
            "selection_rate",
          ].includes(metric.metric_key),
      );
  const copy = viewCopy[view];

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
              <span>Critical</span>
              <strong>{results?.status_counts.critical ?? 0}</strong>
              <small>threshold breaches</small>
            </div>
            <div>
              <span>Review + warning</span>
              <strong>
                {(results?.status_counts.review_required ?? 0) +
                  (results?.status_counts.warning ?? 0)}
              </strong>
              <small>human decision queue</small>
            </div>
            <div>
              <span>Evidence gaps</span>
              <strong>
                {results?.status_counts.insufficient_evidence ?? 0}
              </strong>
              <small>never treated as pass</small>
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
            <p className="eyebrow">{copy.eyebrow}</p>
            <h2>{copy.title}</h2>
          </div>
          <p>{copy.description}</p>
        </div>
        {view === "proxy" ? (
          <ProxyLedger metrics={visibleMetrics} />
        ) : view === "counterfactual" ? (
          <CounterfactualLedger metrics={visibleMetrics} />
        ) : view === "explainability" && run ? (
          <ExplainabilityLedger metrics={visibleMetrics} run={run} />
        ) : view === "drift" ? (
          <DriftLedger
            metrics={visibleMetrics}
            baselineRunId={run?.baseline_run_id ?? null}
          />
        ) : view === "comparison" ? (
          <ComparisonLedger comparison={comparison} />
        ) : (
          <MetricTable metrics={visibleMetrics} />
        )}
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
