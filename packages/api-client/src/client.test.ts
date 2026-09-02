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
});
