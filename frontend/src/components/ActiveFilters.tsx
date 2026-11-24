import { X } from "lucide-react";

import { activeFilterChips } from "../lib/filters";
import type { CompanyOut, JobFilters } from "../types";

interface ActiveFiltersProps {
  filters: JobFilters;
  companies: CompanyOut[];
  onRemove: (key: keyof JobFilters) => void;
  onReset: () => void;
}

export function ActiveFilters({ filters, companies, onRemove, onReset }: ActiveFiltersProps) {
  const chips = activeFilterChips(filters, companies);
  if (chips.length === 0) return null;

  return (
    <div className="mt-3 flex flex-wrap items-center gap-1.5">
      {chips.map((chip) => (
        <span key={chip.key} className="filter-chip">
          <span className="max-w-[220px] truncate">{chip.label}</span>
          <button
            type="button"
            onClick={() => onRemove(chip.key)}
            className="rounded-full p-0.5 text-slate-400 transition hover:bg-slate-100 hover:text-slate-700"
            aria-label={`Remove filter: ${chip.label}`}
          >
            <X className="h-3 w-3" />
          </button>
        </span>
      ))}
      <button
        type="button"
        onClick={onReset}
        className="ml-1 text-xs font-medium text-slate-500 underline decoration-slate-300 underline-offset-2 transition hover:text-indigo-600"
      >
        Clear all
      </button>
    </div>
  );
}
