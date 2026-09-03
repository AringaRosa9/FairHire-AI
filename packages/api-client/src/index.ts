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
export type AuditMetricSummary = components["schemas"]["AuditMetricSummary"];
export type MetricResult = components["schemas"]["MetricResultResponse"];
export type AuditComparison = components["schemas"]["AuditComparisonResponse"];
export type MetricComparison = components["schemas"]["MetricComparison"];
export type BackgroundJob = components["schemas"]["BackgroundJobResponse"];
export type PortfolioSummary = components["schemas"]["PortfolioSummary"];
export type Finding = components["schemas"]["FindingResponse"];
export type FindingDetail = components["schemas"]["FindingDetailResponse"];
export type FindingList = components["schemas"]["FindingListResponse"];
export type FindingCreate = components["schemas"]["FindingCreate"];
export type FindingTransition = components["schemas"]["FindingTransition"];
export type RiskAcceptanceCreate =
  components["schemas"]["RiskAcceptanceCreate"];
export type RemediationTask = components["schemas"]["RemediationTaskResponse"];
export type RemediationTaskList =
  components["schemas"]["RemediationTaskListResponse"];
export type RemediationTaskCreate =
  components["schemas"]["RemediationTaskCreate"];
export type RemediationTaskUpdate =
  components["schemas"]["RemediationTaskUpdate"];
export type FindingRetest = components["schemas"]["FindingRetestResponse"];
export type FindingRetestCreate = components["schemas"]["FindingRetestCreate"];
export type Approval = components["schemas"]["ApprovalResponse"];
export type ApprovalList = components["schemas"]["ApprovalListResponse"];
export type ApprovalChain = components["schemas"]["ApprovalChainResponse"];
export type ApprovalDecisionCreate =
  components["schemas"]["ApprovalDecisionCreate"];
export type ReleaseGate = components["schemas"]["ReleaseGateResponse"];

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
    getAuditMetrics: (
      runId: string,
      category?:
        | "data_quality"
        | "fairness"
        | "proxy"
        | "counterfactual"
        | "explainability"
        | "drift",
    ) =>
      request<AuditMetricSummary>(
        `/audit-runs/${runId}/metrics${category ? `?category=${category}` : ""}`,
      ),
    compareAuditRun: (runId: string, baselineRunId?: string) =>
      request<AuditComparison>(
        `/audit-runs/${runId}/comparison${baselineRunId ? `?baseline_run_id=${encodeURIComponent(baselineRunId)}` : ""}`,
      ),
    getJob: (jobId: string) => request<BackgroundJob>(`/jobs/${jobId}`),
    listFindings: (filters?: {
      status?: string;
      severity?: string;
      aiSystemId?: string;
    }) => {
      const query = new URLSearchParams();
      if (filters?.status) query.set("status", filters.status);
      if (filters?.severity) query.set("severity", filters.severity);
      if (filters?.aiSystemId) query.set("ai_system_id", filters.aiSystemId);
      return request<FindingList>(
        `/findings${query.size ? `?${query.toString()}` : ""}`,
      );
    },
    getFinding: (findingId: string) =>
      request<FindingDetail>(`/findings/${findingId}`),
    createFinding: (payload: FindingCreate, idempotencyKey: string) =>
      write<Finding>("/findings", "POST", payload, idempotencyKey),
    transitionFinding: (
      findingId: string,
      payload: FindingTransition,
      idempotencyKey: string,
    ) =>
      write<Finding>(
        `/findings/${findingId}/transition`,
        "POST",
        payload,
        idempotencyKey,
      ),
    acceptFinding: (
      findingId: string,
      payload: RiskAcceptanceCreate,
      idempotencyKey: string,
    ) =>
      write<Finding>(
        `/findings/${findingId}/accept`,
        "POST",
        payload,
        idempotencyKey,
      ),
    createRemediationTask: (
      findingId: string,
      payload: RemediationTaskCreate,
      idempotencyKey: string,
    ) =>
      write<RemediationTask>(
        `/findings/${findingId}/tasks`,
        "POST",
        payload,
        idempotencyKey,
      ),
    listRemediationTasks: (filters?: {
      status?: string;
      findingId?: string;
      dueBefore?: string;
      overdueOnly?: boolean;
    }) => {
      const query = new URLSearchParams();
      if (filters?.status) query.set("status", filters.status);
      if (filters?.findingId) query.set("finding_id", filters.findingId);
      if (filters?.dueBefore) query.set("due_before", filters.dueBefore);
      if (filters?.overdueOnly) query.set("overdue_only", "true");
      return request<RemediationTaskList>(
        `/remediation-tasks${query.size ? `?${query.toString()}` : ""}`,
      );
    },
    updateRemediationTask: (
      taskId: string,
      payload: RemediationTaskUpdate,
      idempotencyKey: string,
    ) =>
      write<RemediationTask>(
        `/remediation-tasks/${taskId}/status`,
        "POST",
        payload,
        idempotencyKey,
      ),
    recordFindingRetest: (
      findingId: string,
      payload: FindingRetestCreate,
      idempotencyKey: string,
    ) =>
      write<FindingRetest>(
        `/findings/${findingId}/retests`,
        "POST",
        payload,
        idempotencyKey,
      ),
    startApprovalChain: (
      systemId: string,
      reason: string,
      idempotencyKey: string,
    ) =>
      write<ApprovalChain>(
        `/ai-systems/${systemId}/approval-chain`,
        "POST",
        { reason },
        idempotencyKey,
      ),
    listApprovals: (filters?: { decision?: string; aiSystemId?: string }) => {
      const query = new URLSearchParams();
      if (filters?.decision) query.set("decision", filters.decision);
      if (filters?.aiSystemId) query.set("ai_system_id", filters.aiSystemId);
      return request<ApprovalList>(
        `/approvals${query.size ? `?${query.toString()}` : ""}`,
      );
    },
    decideApproval: (
      approvalId: string,
      payload: ApprovalDecisionCreate,
      idempotencyKey: string,
    ) =>
      write<Approval>(
        `/approvals/${approvalId}/decision`,
        "POST",
        payload,
        idempotencyKey,
      ),
    getReleaseGate: (systemId: string) =>
      request<ReleaseGate>(`/ai-systems/${systemId}/release-gate`),
  };
}
