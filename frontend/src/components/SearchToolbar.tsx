import { Search, SlidersHorizontal, X } from "lucide-react";

import type { JobSort } from "../types";

interface SearchToolbarProps {
  search: string;
  onSearchChange: (value: string) => void;
  sort: JobSort;
  onSortChange: (value: JobSort) => void;
  activeFilterCount: number;
  onOpenFilters: () => void;
}

export function SearchToolbar({
  search,
  onSearchChange,
  sort,
  onSortChange,
  activeFilterCount,
  onOpenFilters,
}: SearchToolbarProps) {
  return (
    <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
      <div className="relative flex-1">
        <Search
          className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400"
          aria-hidden
        />
        <input
          type="search"
          value={search}
          onChange={(event) => onSearchChange(event.target.value)}
          placeholder="Search roles, companies, skills, locations..."
          className="field-input pl-9 pr-9"
          aria-label="Search jobs"
          autoComplete="off"
        />
        {search && (
          <button
            type="button"
            onClick={() => onSearchChange("")}
            className="absolute right-2.5 top-1/2 -translate-y-1/2 rounded p-1 text-slate-400 transition hover:text-slate-700"
            aria-label="Clear search"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        )}
      </div>

      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={onOpenFilters}
          className="inline-flex flex-1 items-center justify-center gap-2 rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm font-medium text-slate-700 shadow-sm transition hover:border-slate-400 hover:text-slate-900 sm:flex-none lg:hidden"
        >
          <SlidersHorizontal className="h-4 w-4" aria-hidden />
          Filters
          {activeFilterCount > 0 && (
            <span className="inline-flex h-5 min-w-5 items-center justify-center rounded-full bg-indigo-600 px-1.5 text-[11px] font-semibold text-white">
              {activeFilterCount}
            </span>
          )}
        </button>

        <label htmlFor="sort" className="sr-only">
          Sort by
        </label>
        <select
          id="sort"
          value={sort}
          onChange={(event) => onSortChange(event.target.value as JobSort)}
          className="field-select sm:w-44"
        >
          <option value="posted_desc">Newest first</option>
          <option value="updated_desc">Recently updated</option>
          <option value="company_asc">Company A-Z</option>
        </select>
      </div>
    </div>
  );
}
