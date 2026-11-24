import type {
  CompaniesResponse,
  FacetsResponse,
  JobDetail,
  JobFilters,
  JobListResponse,
  SourcesResponse,
  StatsResponse,
} from "./types";

const API_BASE = (import.meta.env.VITE_API_BASE_URL || "/api").replace(/\/+$/, "");

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function request<T>(path: string, signal?: AbortSignal): Promise<T> {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), 30_000);
  const forwardAbort = () => controller.abort();
  signal?.addEventListener("abort", forwardAbort, { once: true });

  try {
    const response = await fetch(`${API_BASE}${path}`, {
      headers: { Accept: "application/json" },
      signal: controller.signal,
    });
    if (!response.ok) {
      let detail = `Request failed with status ${response.status}`;
      try {
        const body = (await response.json()) as { detail?: unknown };
        if (typeof body.detail === "string") {
          detail = body.detail;
        } else if (Array.isArray(body.detail)) {
          detail = body.detail
            .map((item) => (item && typeof item === "object" && "msg" in item ? String(item.msg) : ""))
            .filter(Boolean)
            .join("; ");
        }
      } catch {
        // Keep the status-based message.
      }
      throw new ApiError(detail, response.status);
    }
    return (await response.json()) as T;
  } catch (error) {
    if (error instanceof ApiError) throw error;
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new ApiError("The request took too long or was cancelled.", 0);
    }
    throw new ApiError(
      error instanceof Error ? error.message : "Unable to reach the EmployBoard API.",
      0,
    );
  } finally {
    window.clearTimeout(timeout);
    signal?.removeEventListener("abort", forwardAbort);
  }
}

export function buildJobQuery(filters: JobFilters): string {
  const params = new URLSearchParams();
  if (filters.q.trim()) params.set("q", filters.q.trim());
  if (filters.location.trim()) params.set("location", filters.location.trim());
  if (filters.company) params.set("company", filters.company);
  if (filters.ats) params.set("ats", filters.ats);
  if (filters.employment_type) params.set("employment_type", filters.employment_type);
  if (filters.workplace_type) params.set("workplace_type", filters.workplace_type);
  if (filters.experience_level) params.set("experience_level", filters.experience_level);
  if (filters.department) params.set("department", filters.department);
  if (filters.date_posted !== "all") params.set("date_posted", filters.date_posted);
  if (filters.sort !== "posted_desc") params.set("sort", filters.sort);
  if (filters.page > 1) params.set("page", String(filters.page));
  if (filters.limit !== 20) params.set("limit", String(filters.limit));
  const query = params.toString();
  return query ? `?${query}` : "";
}

export function fetchJobs(filters: JobFilters, signal?: AbortSignal) {
  return request<JobListResponse>(`/jobs${buildJobQuery(filters)}`, signal);
}

export function fetchJob(jobId: string, signal?: AbortSignal) {
  return request<JobDetail>(`/jobs/${encodeURIComponent(jobId)}`, signal);
}

export function fetchFacets(signal?: AbortSignal) {
  return request<FacetsResponse>("/jobs/facets", signal);
}

export function fetchStats(signal?: AbortSignal) {
  return request<StatsResponse>("/stats", signal);
}

export function fetchCompanies(signal?: AbortSignal) {
  return request<CompaniesResponse>("/companies", signal);
}

export function fetchSources(signal?: AbortSignal) {
  return request<SourcesResponse>("/sources", signal);
}
