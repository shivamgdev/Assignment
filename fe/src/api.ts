import {
  ApiError,
  type ApiErrorBody,
  type SortOrder,
  type Submission,
  type SubmissionListResponse,
} from "./types";

async function request<T>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  let response: Response;

  try {
    response = await fetch(path, {
      ...init,
      headers: {
        Accept: "application/json",
        ...(init?.body ? { "Content-Type": "application/json" } : {}),
        ...init?.headers,
      },
    });
  } catch {
    throw new ApiError(
      "Unable to reach the review service. Check that the API server is running.",
      0,
      "NETWORK_ERROR",
    );
  }

  const body: unknown = await response.json().catch(() => null);

  if (!response.ok) {
    const payload = body as ApiErrorBody | null;
    throw new ApiError(
      payload?.error?.message ?? "The request could not be completed.",
      response.status,
      payload?.error?.code ?? "REQUEST_FAILED",
      payload?.submission,
    );
  }

  return body as T;
}

export interface ListFilters {
  query: string;
  group: string;
  reason: string;
  sort: SortOrder;
}

export function listSubmissions(
  filters: ListFilters,
  signal?: AbortSignal,
): Promise<SubmissionListResponse> {
  const params = new URLSearchParams({
    query: filters.query,
    group: filters.group,
    reason: filters.reason,
    sort: filters.sort,
  });

  return request<SubmissionListResponse>(
    `/api/submissions?${params.toString()}`,
    { signal },
  );
}

export function getSubmission(
  id: string,
  signal?: AbortSignal,
): Promise<Submission> {
  return request<Submission>(
    `/api/submissions/${encodeURIComponent(id)}`,
    { signal },
  );
}

export type Decision = "APPROVE" | "RETURN";

export function recordDecision(
  id: string,
  decision: Decision,
  note: string,
): Promise<Submission> {
  return request<Submission>(
    `/api/submissions/${encodeURIComponent(id)}/decision`,
    {
      method: "POST",
      body: JSON.stringify({ decision, note }),
    },
  );
}
