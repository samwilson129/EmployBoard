import { useCallback, useEffect, useRef, useState } from "react";
import { X } from "lucide-react";

import { fetchCompanies, fetchFacets, fetchJobs, fetchSources, fetchStats } from "./api";
import { ActiveFilters } from "./components/ActiveFilters";
import { FilterPanel } from "./components/FilterPanel";
import { Footer } from "./components/Footer";
import { Header } from "./components/Header";
import { JobCard } from "./components/JobCard";
import { JobDetailPanel } from "./components/JobDetailPanel";
import { Pagination } from "./components/Pagination";
import { SearchToolbar } from "./components/SearchToolbar";
import { EmptyState, ErrorState, JobListSkeleton } from "./components/States";
import { useDebouncedValue } from "./hooks/useDebouncedValue";
import { useUrlState } from "./hooks/useUrlState";
import { useBodyScrollLock, useMediaQuery } from "./hooks/useViewport";
import { clearFilterValue, countActiveFilters } from "./lib/filters";
import { cn, formatNumber } from "./lib/format";
import type {
  CompanyOut,
  FacetsResponse,
  JobFilters,
  JobListResponse,
  SourceProviderOut,
  StatsResponse,
} from "./types";

export default function App() {
  const { filters, selectedJobId, updateFilters, resetFilters, selectJob } = useUrlState();

  const [searchText, setSearchText] = useState(filters.q);
  const debouncedSearch = useDebouncedValue(searchText, 350);

  useEffect(() => {
    if (debouncedSearch !== filters.q) {
      updateFilters({ q: debouncedSearch });
    }
  }, [debouncedSearch, filters.q, updateFilters]);

  useEffect(() => {
    setSearchText(filters.q);
  }, [filters.q]);

  const [stats, setStats] = useState<StatsResponse | null>(null);
  const [facets, setFacets] = useState<FacetsResponse | null>(null);
  const [companies, setCompanies] = useState<CompanyOut[]>([]);
  const [sources, setSources] = useState<SourceProviderOut[]>([]);

  useEffect(() => {
    const controller = new AbortController();
    fetchStats(controller.signal).then(setStats).catch(() => undefined);
    fetchFacets(controller.signal).then(setFacets).catch(() => undefined);
    fetchCompanies(controller.signal)
      .then((response) => setCompanies(response.items))
      .catch(() => undefined);
    fetchSources(controller.signal)
      .then((response) => setSources(response.items))
      .catch(() => undefined);
    return () => controller.abort();
  }, []);

  const [jobs, setJobs] = useState<JobListResponse | null>(null);
  const [jobsLoading, setJobsLoading] = useState(true);
  const [jobsError, setJobsError] = useState<string | null>(null);
  const [reloadToken, setReloadToken] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    setJobsLoading(true);
    setJobsError(null);

    fetchJobs(filters, controller.signal)
      .then((response) => {
        if (controller.signal.aborted) return;
        setJobs(response);
        setJobsLoading(false);
      })
      .catch((caught: unknown) => {
        if (controller.signal.aborted) return;
        setJobsError(
          caught instanceof Error ? caught.message : "Unable to reach the EmployBoard API.",
        );
        setJobsLoading(false);
      });

    return () => controller.abort();
  }, [filters, reloadToken]);

  const [filtersOpen, setFiltersOpen] = useState(false);
  const isXl = useMediaQuery("(min-width: 1280px)");
  const detailIsDrawer = Boolean(selectedJobId) && !isXl;
  useBodyScrollLock(filtersOpen || detailIsDrawer);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      setFiltersOpen(false);
      if (selectedJobId) selectJob(null);
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [selectedJobId, selectJob]);

  const resultsRef = useRef<HTMLDivElement>(null);
  const firstRender = useRef(true);
  useEffect(() => {
    if (firstRender.current) {
      firstRender.current = false;
      return;
    }
    resultsRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, [filters.page]);

  const handleSearchChange = useCallback((value: string) => setSearchText(value), []);

  const handleFilterChange = useCallback(
    (patch: Partial<JobFilters>) => updateFilters(patch),
    [updateFilters],
  );

  const handleRemoveFilter = useCallback(
    (key: keyof JobFilters) => updateFilters(clearFilterValue(filters, key)),
    [filters, updateFilters],
  );

  const handleReset = useCallback(() => {
    resetFilters();
    setSearchText("");
  }, [resetFilters]);

  const handleRetry = useCallback(() => setReloadToken((token) => token + 1), []);

  const activeFilterCount = countActiveFilters(filters);

  const filterPanel = (
    <FilterPanel
      filters={filters}
      facets={facets}
      companies={companies}
      onChange={handleFilterChange}
      onReset={handleReset}
    />
  );

  return (
    <div className="min-h-screen bg-slate-50">
      <Header stats={stats} loading={!stats} />

      <main className="mx-auto max-w-[1400px] px-4 py-5 sm:px-6 lg:px-8">
        <div className="flex items-start gap-6">
          <aside className="hidden w-64 shrink-0 lg:block">
            <div className="sticky top-4 max-h-[calc(100vh-2rem)] overflow-y-auto scroll-slim rounded-xl border border-slate-200 bg-white p-4">
              {filterPanel}
            </div>
          </aside>

          <section className="min-w-0 flex-1" aria-label="Job results">
            <SearchToolbar
              search={searchText}
              onSearchChange={handleSearchChange}
              sort={filters.sort}
              onSortChange={(sort) => updateFilters({ sort })}
              activeFilterCount={activeFilterCount}
              onOpenFilters={() => setFiltersOpen(true)}
            />

            <ActiveFilters
              filters={filters}
              companies={companies}
              onRemove={handleRemoveFilter}
              onReset={handleReset}
            />

            <div ref={resultsRef} className="mt-4 scroll-mt-4">
              <div className="flex flex-wrap items-baseline justify-between gap-2">
                <p className="text-sm text-slate-600">
                  {jobs ? (
                    <>
                      <span className="font-semibold text-slate-900">
                        {formatNumber(jobs.total)}
                      </span>{" "}
                      {jobs.total === 1 ? "job" : "jobs"}
                      {filters.q.trim() && (
                        <span className="text-slate-400"> matching "{filters.q.trim()}"</span>
                      )}
                    </>
                  ) : (
                    "Loading jobs..."
                  )}
                </p>
                {jobsLoading && jobs && (
                  <span className="text-xs text-slate-400">Updating results...</span>
                )}
              </div>

              <div className="mt-3">
                {jobsLoading && !jobs ? (
                  <JobListSkeleton />
                ) : jobsError ? (
                  <ErrorState message={jobsError} onRetry={handleRetry} />
                ) : jobs && jobs.items.length === 0 ? (
                  <EmptyState onReset={handleReset} hasFilters={activeFilterCount > 0} />
                ) : (
                  <>
                    <div
                      className={cn(
                        "space-y-3 transition-opacity",
                        jobsLoading && "pointer-events-none opacity-60",
                      )}
                    >
                      {jobs?.items.map((job) => (
                        <JobCard
                          key={job.job_id}
                          job={job}
                          selected={job.job_id === selectedJobId}
                          onSelect={selectJob}
                        />
                      ))}
                    </div>

                    {jobs && (
                      <Pagination
                        page={jobs.page}
                        pages={jobs.pages}
                        total={jobs.total}
                        limit={jobs.limit}
                        disabled={jobsLoading}
                        onPageChange={(page) => updateFilters({ page }, false)}
                        onLimitChange={(limit) => updateFilters({ limit, page: 1 }, false)}
                      />
                    )}
                  </>
                )}
              </div>
            </div>
          </section>

          {selectedJobId && (
            <>
              <div
                className="fixed inset-0 z-40 bg-slate-900/40 xl:hidden"
                onClick={() => selectJob(null)}
                role="presentation"
              />
              <aside
                className="fixed inset-y-0 right-0 z-50 flex w-full max-w-xl flex-col border-l border-slate-200 bg-white shadow-2xl xl:sticky xl:inset-auto xl:top-4 xl:z-auto xl:h-[calc(100vh-2rem)] xl:w-[430px] xl:max-w-none xl:shrink-0 xl:rounded-xl xl:border xl:shadow-card"
                aria-label="Job details"
              >
                <JobDetailPanel jobId={selectedJobId} onClose={() => selectJob(null)} />
              </aside>
            </>
          )}
        </div>
      </main>

      <Footer sources={sources} />

      {filtersOpen && (
        <div className="fixed inset-0 z-50 lg:hidden" role="dialog" aria-modal="true" aria-label="Filters">
          <div
            className="absolute inset-0 bg-slate-900/40"
            onClick={() => setFiltersOpen(false)}
            role="presentation"
          />
          <div className="absolute inset-y-0 left-0 flex w-[88%] max-w-sm flex-col bg-white shadow-2xl">
            <div className="flex items-center justify-between border-b border-slate-200 px-4 py-3">
              <h2 className="text-sm font-semibold text-slate-900">Filters</h2>
              <button
                type="button"
                onClick={() => setFiltersOpen(false)}
                className="rounded-lg border border-slate-200 p-1.5 text-slate-500 transition hover:bg-slate-50"
                aria-label="Close filters"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
            <div className="flex-1 overflow-y-auto scroll-slim p-4">{filterPanel}</div>
            <div className="flex gap-2 border-t border-slate-200 p-4">
              <button
                type="button"
                onClick={handleReset}
                className="flex-1 rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm font-medium text-slate-700 transition hover:border-slate-400"
              >
                Clear all
              </button>
              <button
                type="button"
                onClick={() => setFiltersOpen(false)}
                className="flex-1 rounded-lg bg-indigo-600 px-3 py-2 text-sm font-semibold text-white transition hover:bg-indigo-700"
              >
                Show results
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
