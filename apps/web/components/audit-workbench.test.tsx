import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AuditWorkbench } from "./audit-workbench";

afterEach(() => vi.unstubAllGlobals());

describe("AuditWorkbench", () => {
  it("keeps uncertainty, evidence state, and policy trace together", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);
        if (url.endsWith("/audit-runs/run-1")) {
          return Response.json({
            id: "run-1",
            organization_id: "org-northstar",
            ai_system_id: "sys-1",
            model_version_id: "model-1",
            dataset_id: "dataset-1",
            config_version: 1,
            policy_pack_version: "eu-core+de@2026.09",
            config_snapshot: { random_seed: 42 },
            data_fingerprint: "f".repeat(64),
            status: "succeeded",
            job_id: "job-1",
            error_code: null,
            error_detail: null,
            submitted_by: "maya",
            submitted_at: "2026-09-03T00:00:00Z",
            started_at: "2026-09-03T00:00:01Z",
            completed_at: "2026-09-03T00:00:03Z",
          });
        }
        if (url.endsWith("/jobs/job-1")) {
          return Response.json({
            id: "job-1",
            organization_id: "org-northstar",
            task_name: "audit.analyze",
            resource_type: "audit_run",
            resource_id: "run-1",
            status: "succeeded",
            attempt: 1,
            max_attempts: 3,
            progress: 100,
            error_code: null,
            error_detail: null,
            cancellation_requested: false,
            submitted_at: "2026-09-03T00:00:00Z",
            updated_at: "2026-09-03T00:00:03Z",
          });
        }
        return Response.json({
          audit_run_id: "run-1",
          calculation_version: "fairhire-binary-audit@1.0.0",
          status_counts: { review_required: 1 },
          evidence_gaps: [],
          items: [
            {
              id: "metric-1",
              audit_run_id: "run-1",
              category: "fairness",
              metric_key: "demographic_parity_ratio",
              protected_attribute: "gender",
              reference_group: "women",
              comparison_group: "men",
              value: 0.78,
              lower_bound: 0.69,
              upper_bound: 0.88,
              status: "review_required",
              threshold: 0.8,
              threshold_operator: ">=",
              threshold_source: { source_id: "strategy-eu-binary-v1" },
              raw_counts: { comparison: { n: 250, selected: 98 } },
              method: "stratified_bootstrap_percentile",
              calculation_version: "fairhire-binary-audit@1.0.0",
              details: { random_seed: 42 },
              created_at: "2026-09-03T00:00:03Z",
            },
          ],
        });
      }),
    );

    render(<AuditWorkbench runId="run-1" view="fairness" />);
    expect(
      await screen.findByText("Demographic parity ratio"),
    ).toBeInTheDocument();
    expect(screen.getByText("0.69–0.88")).toBeInTheDocument();
    expect(screen.getByText("review required")).toBeInTheDocument();
    expect(screen.getByText("Counts & policy")).toBeInTheDocument();
  });

  it("shows both proxy evidence paths in one finding", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);
        if (url.endsWith("/audit-runs/run-proxy")) {
          return Response.json({
            id: "run-proxy",
            organization_id: "org-northstar",
            ai_system_id: "sys-1",
            model_version_id: "model-2",
            dataset_id: "dataset-2",
            baseline_run_id: null,
            config_version: 1,
            policy_pack_version: "eu-core+de@2026.09",
            config_snapshot: { random_seed: 1729 },
            data_fingerprint: "a".repeat(64),
            status: "succeeded",
            job_id: "job-proxy",
            error_code: null,
            error_detail: null,
            submitted_by: "maya",
            submitted_at: "2026-09-03T00:00:00Z",
            started_at: "2026-09-03T00:00:01Z",
            completed_at: "2026-09-03T00:00:03Z",
          });
        }
        if (url.endsWith("/jobs/job-proxy")) {
          return Response.json({
            id: "job-proxy",
            organization_id: "org-northstar",
            task_name: "audit.analyze",
            resource_type: "audit_run",
            resource_id: "run-proxy",
            status: "succeeded",
            attempt: 1,
            max_attempts: 3,
            progress: 100,
            error_code: null,
            error_detail: null,
            cancellation_requested: false,
            submitted_at: "2026-09-03T00:00:00Z",
            updated_at: "2026-09-03T00:00:03Z",
          });
        }
        return Response.json({
          audit_run_id: "run-proxy",
          calculation_version: "fairhire-binary-audit@2.0.0",
          status_counts: { review_required: 1 },
          evidence_gaps: [],
          items: [
            {
              id: "proxy-1",
              audit_run_id: "run-proxy",
              category: "proxy",
              metric_key: "proxy_risk",
              protected_attribute: "gender",
              reference_group: null,
              comparison_group: "postal_code",
              value: 0.42,
              lower_bound: null,
              upper_bound: null,
              status: "review_required",
              threshold: 0.1,
              threshold_operator: "dual_evidence",
              threshold_source: { source_id: "strategy-1" },
              raw_counts: { usable_rows: 500 },
              method: "dual_evidence_proxy_screen",
              calculation_version: "fairhire-binary-audit@2.0.0",
              details: {
                confidence: "high",
                association_evidence: {
                  normalized_mutual_information: 0.5,
                  predictability_lift_over_majority: 0.4,
                },
                output_impact_evidence: {
                  value: 0.35,
                  method: "controlled_ablation",
                },
                limitation: "Association is not proof of causation.",
              },
              created_at: "2026-09-03T00:00:03Z",
            },
          ],
        });
      }),
    );

    render(<AuditWorkbench runId="run-proxy" view="proxy" />);
    expect(await screen.findByText("postal_code")).toBeInTheDocument();
    expect(screen.getByText("01 · Group association")).toBeInTheDocument();
    expect(screen.getByText("02 · Output impact")).toBeInTheDocument();
    expect(screen.getByText("controlled ablation")).toBeInTheDocument();
  });

  it("makes the SHAP boundary, background dataset, and seed visible", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);
        if (url.endsWith("/audit-runs/run-shap")) {
          return Response.json({
            id: "run-shap",
            organization_id: "org-northstar",
            ai_system_id: "sys-1",
            model_version_id: "model-shap",
            dataset_id: "dataset-shap",
            baseline_run_id: null,
            config_version: 1,
            policy_pack_version: "eu-core+de@2026.09",
            config_snapshot: { random_seed: 73 },
            data_fingerprint: "c".repeat(64),
            status: "succeeded",
            job_id: "job-shap",
            error_code: null,
            error_detail: null,
            submitted_by: "maya",
            submitted_at: "2026-09-03T00:00:00Z",
            started_at: "2026-09-03T00:00:01Z",
            completed_at: "2026-09-03T00:00:03Z",
          });
        }
        if (url.endsWith("/jobs/job-shap")) {
          return Response.json({
            id: "job-shap",
            organization_id: "org-northstar",
            task_name: "audit.analyze",
            resource_type: "audit_run",
            resource_id: "run-shap",
            status: "succeeded",
            attempt: 1,
            max_attempts: 3,
            progress: 100,
            error_code: null,
            error_detail: null,
            cancellation_requested: false,
            submitted_at: "2026-09-03T00:00:00Z",
            updated_at: "2026-09-03T00:00:03Z",
          });
        }
        return Response.json({
          audit_run_id: "run-shap",
          calculation_version: "fairhire-binary-audit@2.0.0",
          status_counts: { pass: 1 },
          evidence_gaps: [],
          items: [
            {
              id: "explanation-1",
              audit_run_id: "run-shap",
              category: "explainability",
              metric_key: "global_feature_importance",
              protected_attribute: null,
              reference_group: null,
              comparison_group: "experience",
              value: 0.41,
              lower_bound: null,
              upper_bound: null,
              status: "pass",
              threshold: null,
              threshold_operator: null,
              threshold_source: {},
              raw_counts: { rows: 500 },
              method: "precomputed_global_shap",
              calculation_version: "fairhire-binary-audit@2.0.0",
              details: {
                rank: 1,
                background_dataset: "data-background@sha256:abc",
                random_seed: 73,
                method_boundary:
                  "Aggregated SHAP values supplied by the controlled model adapter.",
              },
              created_at: "2026-09-03T00:00:03Z",
            },
          ],
        });
      }),
    );

    render(<AuditWorkbench runId="run-shap" view="explainability" />);
    expect(
      await screen.findByText("Global SHAP attribution"),
    ).toBeInTheDocument();
    expect(screen.getByText("data-background@sha256:abc")).toBeInTheDocument();
    expect(screen.getByText("73")).toBeInTheDocument();
  });
});
