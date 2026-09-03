import {
  createApiClient,
  type AISystem,
  type PortfolioSummary,
  type Assessment,
  type ModelVersion,
} from "@fairhire/api-client";
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

export async function getSystemDetail(systemId: string): Promise<{
  system: AISystem | undefined;
  assessments: Assessment[];
  modelVersions: ModelVersion[];
  source: "api" | "fixture";
}> {
  try {
    const [system, assessments, modelVersions] = await Promise.all([
      api.getSystem(systemId),
      api.listAssessments(systemId),
      api.listModelVersions(systemId),
    ]);
    return { system, assessments, modelVersions, source: "api" };
  } catch {
    return {
      system: fixtureSystems.find((item) => item.id === systemId),
      assessments: [],
      modelVersions: [],
      source: "fixture",
    };
  }
}

export async function getPortfolioSummary(): Promise<{
  summary: PortfolioSummary;
  source: "api" | "fixture";
}> {
  try {
    return { summary: await api.portfolio(), source: "api" };
  } catch {
    const releaseCounts = fixtureSystems.reduce<Record<string, number>>(
      (counts, system) => ({
        ...counts,
        [system.release_status]: (counts[system.release_status] ?? 0) + 1,
      }),
      {},
    );
    return {
      summary: {
        total_systems: fixtureSystems.length,
        release_counts: releaseCounts,
        ready_datasets: 0,
        active_audit_runs: 0,
        failed_jobs: 0,
      },
      source: "fixture",
    };
  }
}
