import { useCallback, useEffect, useState } from "react";

import { buildJobQuery } from "../api";
import { EMPTY_FILTERS } from "../types";
import type { DatePosted, JobFilters, JobSort } from "../types";

const SORTS: JobSort[] = ["posted_desc", "updated_desc", "company_asc"];
const DATES: DatePosted[] = ["all", "24h", "7d", "30d"];
const PAGE_SIZES = [20, 50, 100];

export interface UrlState {
  filters: JobFilters;
  selectedJobId: string | null;
}

function positiveInt(raw: string | null, fallback: number): number {
  const value = Number(raw);
  return Number.isFinite(value) && value > 0 ? Math.floor(value) : fallback;
}

export function parseUrlState(search: string): UrlState {
  const params = new URLSearchParams(search);
  const sort = params.get("sort") as JobSort | null;
  const datePosted = params.get("date_posted") as DatePosted | null;
  const limit = positiveInt(params.get("limit"), 20);

  return {
    filters: {
      q: params.get("q") ?? "",
      location: params.get("location") ?? "",
      company: params.get("company") ?? "",
      ats: params.get("ats") ?? "",
      employment_type: params.get("employment_type") ?? "",
      workplace_type: params.get("workplace_type") ?? "",
      experience_level: params.get("experience_level") ?? "",
      department: params.get("department") ?? "",
      date_posted: datePosted && DATES.includes(datePosted) ? datePosted : "all",
      sort: sort && SORTS.includes(sort) ? sort : "posted_desc",
      page: positiveInt(params.get("page"), 1),
      limit: PAGE_SIZES.includes(limit) ? limit : 20,
    },
    selectedJobId: params.get("job"),
  };
}

export function serializeUrlState(state: UrlState): string {
  const base = buildJobQuery(state.filters);
  const params = new URLSearchParams(base.startsWith("?") ? base.slice(1) : base);
  if (state.selectedJobId) params.set("job", state.selectedJobId);
  const query = params.toString();
  return query ? `?${query}` : "";
}

/**
 * Keeps filters and the open job in the address bar so searches are shareable
 * and the browser back/forward buttons work.
 */
export function useUrlState() {
  const [state, setState] = useState<UrlState>(() => parseUrlState(window.location.search));

  useEffect(() => {
    const onPopState = () => setState(parseUrlState(window.location.search));
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, []);

  useEffect(() => {
    const url = `${window.location.pathname}${serializeUrlState(state)}`;
    window.history.replaceState(null, "", url);
  }, [state]);

  const updateFilters = useCallback((patch: Partial<JobFilters>, resetPage = true) => {
    setState((current) => ({
      ...current,
      filters: {
        ...current.filters,
        ...patch,
        ...(resetPage ? { page: 1 } : {}),
      },
    }));
  }, []);

  const resetFilters = useCallback(() => {
    setState((current) => ({ ...current, filters: { ...EMPTY_FILTERS } }));
  }, []);

  const selectJob = useCallback((jobId: string | null) => {
    setState((current) => ({ ...current, selectedJobId: jobId }));
  }, []);

  return { ...state, updateFilters, resetFilters, selectJob };
}
