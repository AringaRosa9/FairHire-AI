import { describe, expect, it, vi } from "vitest";
import { createApiClient } from "./index";

describe("createApiClient", () => {
  it("forwards explicit development identity and organization context", async () => {
    const fetcher = vi.fn(
      async (_input: RequestInfo | URL, init?: RequestInit) => {
        const headers = new Headers(init?.headers);
        expect(headers.get("X-Organization-ID")).toBe("org-demo");
        expect(headers.get("X-Dev-User")).toBe("auditor@fairhire.test");
        return new Response(
          JSON.stringify({ status: "ok", version: "0.1.0" }),
          { status: 200 },
        );
      },
    );
    await createApiClient({
      baseUrl: "http://api.test/v1",
      organizationId: "org-demo",
      devUser: "auditor@fairhire.test",
      fetcher: fetcher as typeof fetch,
    }).health();
    expect(fetcher).toHaveBeenCalledOnce();
  });

  it("requests a category-filtered metric ledger", async () => {
    const fetcher = vi.fn(async (input: RequestInfo | URL) => {
      expect(String(input)).toBe(
        "http://api.test/v1/audit-runs/run-1/metrics?category=fairness",
      );
      return new Response(
        JSON.stringify({
          audit_run_id: "run-1",
          calculation_version: null,
          status_counts: {},
          evidence_gaps: [],
          items: [],
        }),
        { status: 200 },
      );
    });
    await createApiClient({
      baseUrl: "http://api.test/v1",
      fetcher: fetcher as typeof fetch,
    }).getAuditMetrics("run-1", "fairness");
  });
});
