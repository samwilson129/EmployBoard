import { AlertCircle, RefreshCw, SearchX } from "lucide-react";

export function JobCardSkeleton() {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-card sm:p-5">
      <div className="flex items-start gap-3">
        <div className="h-10 w-10 shrink-0 animate-pulse rounded-lg bg-slate-200" />
        <div className="min-w-0 flex-1 space-y-2">
          <div className="h-4 w-2/3 animate-pulse rounded bg-slate-200" />
          <div className="h-3 w-1/3 animate-pulse rounded bg-slate-100" />
          <div className="h-3 w-1/2 animate-pulse rounded bg-slate-100" />
          <div className="h-3 w-full animate-pulse rounded bg-slate-100" />
          <div className="flex gap-1.5 pt-1">
            <div className="h-5 w-16 animate-pulse rounded bg-slate-100" />
            <div className="h-5 w-14 animate-pulse rounded bg-slate-100" />
          </div>
        </div>
      </div>
    </div>
  );
}

export function JobListSkeleton({ count = 6 }: { count?: number }) {
  return (
    <div className="space-y-3" aria-busy="true" aria-label="Loading jobs">
      {Array.from({ length: count }, (_, index) => (
        <JobCardSkeleton key={index} />
      ))}
    </div>
  );
}

interface EmptyStateProps {
  onReset: () => void;
  hasFilters: boolean;
}

export function EmptyState({ onReset, hasFilters }: EmptyStateProps) {
  return (
    <div className="rounded-xl border border-dashed border-slate-300 bg-white px-6 py-12 text-center">
      <SearchX className="mx-auto h-8 w-8 text-slate-300" aria-hidden />
      <h2 className="mt-3 text-sm font-semibold text-slate-900">No jobs match these filters</h2>
      <p className="mx-auto mt-1 max-w-sm text-sm text-slate-500">
        Try a broader search, a different location, or remove one of the filters.
      </p>
      {hasFilters && (
        <button
          type="button"
          onClick={onReset}
          className="mt-4 inline-flex items-center gap-2 rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm font-medium text-slate-700 transition hover:border-slate-400"
        >
          <RefreshCw className="h-4 w-4" aria-hidden />
          Clear filters
        </button>
      )}
    </div>
  );
}

interface ErrorStateProps {
  message: string;
  onRetry: () => void;
}

export function ErrorState({ message, onRetry }: ErrorStateProps) {
  return (
    <div className="rounded-xl border border-rose-200 bg-rose-50 px-6 py-10 text-center">
      <AlertCircle className="mx-auto h-8 w-8 text-rose-400" aria-hidden />
      <h2 className="mt-3 text-sm font-semibold text-rose-900">Could not load jobs</h2>
      <p className="mx-auto mt-1 max-w-md text-sm text-rose-700">{message}</p>
      <button
        type="button"
        onClick={onRetry}
        className="mt-4 inline-flex items-center gap-2 rounded-lg border border-rose-300 bg-white px-3 py-2 text-sm font-medium text-rose-700 transition hover:bg-rose-100"
      >
        <RefreshCw className="h-4 w-4" aria-hidden />
        Try again
      </button>
    </div>
  );
}
