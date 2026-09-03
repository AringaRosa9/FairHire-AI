import { createApiClient } from "@fairhire/api-client";

export function createBrowserApi() {
  return createApiClient({
    baseUrl: process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/v1",
    organizationId: "org-northstar",
    devUser: "maya.chen@fairhire.test",
  });
}
