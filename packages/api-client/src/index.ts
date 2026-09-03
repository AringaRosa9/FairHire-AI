import type { components } from "./schema";

export type Session = components["schemas"]["SessionResponse"];
export type AISystem = components["schemas"]["AISystemResponse"];
export type AISystemList = components["schemas"]["AISystemListResponse"];
export type AISystemCreate = components["schemas"]["AISystemCreate"];
export type Assessment = components["schemas"]["AssessmentResponse"];
export type AssessmentCreate = components["schemas"]["AssessmentCreate"];
export type ModelVersion = components["schemas"]["ModelVersionResponse"];
export type ModelVersionCreate = components["schemas"]["ModelVersionCreate"];
export type Draft = components["schemas"]["DraftResponse"];
export type DraftUpdate = components["schemas"]["DraftUpdate"];
export type UploadInitiate = components["schemas"]["UploadInitiate"];
export type UploadSession = components["schemas"]["UploadInitiateResponse"];
export type UploadComplete = components["schemas"]["UploadComplete"];
export type Dataset = components["schemas"]["DatasetResponse"];
export type FieldMappingsCreate = components["schemas"]["FieldMappingsCreate"];
export type AuditRunCreate = components["schemas"]["AuditRunCreate"];
export type AuditRun = components["schemas"]["AuditRunResponse"];
export type BackgroundJob = components["schemas"]["BackgroundJobResponse"];
export type PortfolioSummary = components["schemas"]["PortfolioSummary"];

export type ClientOptions = {
  baseUrl: string;
  fetcher?: typeof fetch;
  organizationId?: string;
  devUser?: string;
};

export function createApiClient({
  baseUrl,
  fetcher = fetch,
  organizationId,
  devUser,
}: ClientOptions) {
  async function request<T>(path: string, init?: RequestInit): Promise<T> {
    const headers = new Headers(init?.headers);
    headers.set("Accept", "application/json");
    if (organizationId) headers.set("X-Organization-ID", organizationId);
    if (devUser) headers.set("X-Dev-User", devUser);
    const response = await fetcher(`${baseUrl}${path}`, {
      ...init,
      headers,
      cache: "no-store",
    });
    if (!response.ok) {
      const problem = (await response.json().catch(() => null)) as {
        detail?: string;
      } | null;
      throw new Error(
        problem?.detail ?? `FairHire API request failed (${response.status})`,
      );
    }
    return response.json() as Promise<T>;
  }

  function write<T>(
    path: string,
    method: "POST" | "PUT",
    body: unknown,
    idempotencyKey: string,
  ): Promise<T> {
    return request<T>(path, {
      method,
      headers: {
        "Content-Type": "application/json",
        "Idempotency-Key": idempotencyKey,
      },
      body: JSON.stringify(body),
    });
  }

  return {
    health: () => request<{ status: string; version: string }>("/health"),
    session: () => request<Session>("/session"),
    portfolio: () => request<PortfolioSummary>("/portfolio"),
    listSystems: () => request<AISystemList>("/ai-systems"),
    getSystem: (systemId: string) =>
      request<AISystem>(`/ai-systems/${systemId}`),
    createSystem: (payload: AISystemCreate, idempotencyKey: string) =>
      write<AISystem>("/ai-systems", "POST", payload, idempotencyKey),
    createAssessment: (
      systemId: string,
      payload: AssessmentCreate,
      idempotencyKey: string,
    ) =>
      write<Assessment>(
        `/ai-systems/${systemId}/assessments`,
        "POST",
        payload,
        idempotencyKey,
      ),
    listAssessments: (systemId: string) =>
      request<Assessment[]>(`/ai-systems/${systemId}/assessments`),
    createModelVersion: (
      systemId: string,
      payload: ModelVersionCreate,
      idempotencyKey: string,
    ) =>
      write<ModelVersion>(
        `/ai-systems/${systemId}/model-versions`,
        "POST",
        payload,
        idempotencyKey,
      ),
    listModelVersions: (systemId: string) =>
      request<ModelVersion[]>(`/ai-systems/${systemId}/model-versions`),
    getDraft: () => request<Draft | null>("/onboarding-draft"),
    saveDraft: (payload: DraftUpdate, idempotencyKey: string) =>
      write<Draft>("/onboarding-draft", "PUT", payload, idempotencyKey),
    initiateUpload: (payload: UploadInitiate, idempotencyKey: string) =>
      write<UploadSession>(
        "/datasets/initiate-upload",
        "POST",
        payload,
        idempotencyKey,
      ),
    completeUpload: (
      datasetId: string,
      payload: UploadComplete,
      idempotencyKey: string,
    ) =>
      write<Dataset>(
        `/datasets/${datasetId}/complete-upload`,
        "POST",
        payload,
        idempotencyKey,
      ),
    saveFieldMappings: (
      datasetId: string,
      payload: FieldMappingsCreate,
      idempotencyKey: string,
    ) =>
      write<Dataset>(
        `/datasets/${datasetId}/field-mappings`,
        "POST",
        payload,
        idempotencyKey,
      ),
    createAuditRun: (payload: AuditRunCreate, idempotencyKey: string) =>
      write<AuditRun>("/audit-runs", "POST", payload, idempotencyKey),
    getAuditRun: (runId: string) => request<AuditRun>(`/audit-runs/${runId}`),
    getJob: (jobId: string) => request<BackgroundJob>(`/jobs/${jobId}`),
  };
}
