import { createApiClient, type AISystem } from "@fairhire/api-client";
import { fixtureSystems } from "./fixtures";

const api = createApiClient({
  baseUrl:
    process.env.API_INTERNAL_URL ??
    process.env.NEXT_PUBLIC_API_URL ??
    "http://localhost:8000/v1",
  organizationId: "org-northstar",
  devUser: "maya.chen@fairhire.test",
});

export async function getSystems(): Promise<{
  items: AISystem[];
  source: "api" | "fixture";
}> {
  try {
    const result = await api.listSystems();
    return { items: result.items, source: "api" };
  } catch {
    return { items: fixtureSystems, source: "fixture" };
  }
}
