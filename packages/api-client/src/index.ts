import type { components } from "./schema";

export type Session = components["schemas"]["SessionResponse"];
export type AISystem = components["schemas"]["AISystemResponse"];
export type AISystemList = components["schemas"]["AISystemListResponse"];

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

  return {
    health: () => request<{ status: string; version: string }>("/health"),
    session: () => request<Session>("/session"),
    listSystems: () => request<AISystemList>("/ai-systems"),
  };
}
