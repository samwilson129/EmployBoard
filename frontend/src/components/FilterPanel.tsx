import { useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
import { SlidersHorizontal } from "lucide-react";

import { useDebouncedValue } from "../hooks/useDebouncedValue";
import { countActiveFilters, DATE_LABELS } from "../lib/filters";
import { formatNumber } from "../lib/format";
import type { CompanyOut, FacetCount, FacetsResponse, JobFilters } from "../types";

interface FilterPanelProps {
  filters: JobFilters;
  facets: FacetsResponse | null;
  companies: CompanyOut[];
  onChange: (patch: Partial<JobFilters>) => void;
  onReset: () => void;
  showHeader?: boolean;
}

interface SelectFieldProps {
  id: string;
  label: string;
  value: string;
  onChange: (value: string) => void;
  children: ReactNode;
}

function SelectField({ id, label, value, onChange, children }: SelectFieldProps) {
  return (
    <div>
      <label htmlFor={id} className="field-label">
        {label}
      </label>
      <select
        id={id}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="field-select"
      >
        {children}
      </select>
    </div>
  );
}

interface FacetSelectProps {
  id: string;
  label: string;
  allLabel: string;
  value: string;
  facets: FacetCount[];
  onChange: (value: string) => void;
}

function FacetSelect({ id, label, allLabel, value, facets, onChange }: FacetSelectProps) {
  return (
    <SelectField id={id} label={label} value={value} onChange={onChange}>
      <option value="">{allLabel}</option>
      {facets.map((facet) => (
        <option key={facet.value} value={facet.value}>
          {facet.label} ({formatNumber(facet.count)})
        </option>
      ))}
    </SelectField>
  );
}

interface LocationInputProps {
  value: string;
  suggestions: string[];
  onChange: (value: string) => void;
}

function LocationInput({ value, suggestions, onChange }: LocationInputProps) {
  const [text, setText] = useState(value);
  const debounced = useDebouncedValue(text, 400);
  const lastEmitted = useRef(value);

  useEffect(() => {
    if (debounced !== lastEmitted.current) {
      lastEmitted.current = debounced;
      onChange(debounced);
    }
  }, [debounced, onChange]);

  useEffect(() => {
    if (value !== lastEmitted.current) {
      lastEmitted.current = value;
      setText(value);
    }
  }, [value]);

  return (
    <div>
      <label htmlFor="filter-location" className="field-label">
        Location
      </label>
      <input
        id="filter-location"
        type="text"
        list="filter-location-options"
        value={text}
        onChange={(event) => setText(event.target.value)}
        placeholder="City, region or country"
        className="field-input"
        autoComplete="off"
      />
      <datalist id="filter-location-options">
        {suggestions.map((option) => (
          <option key={option} value={option} />
        ))}
      </datalist>
    </div>
  );
}

export function FilterPanel({
  filters,
  facets,
  companies,
  onChange,
  onReset,
  showHeader = true,
}: FilterPanelProps) {
  const activeCount = countActiveFilters(filters);
  const topLocations = (facets?.locations ?? []).slice(0, 60).map((facet) => facet.value);

  return (
    <div>
      {showHeader && (
        <div className="flex items-center justify-between">
          <h2 className="flex items-center gap-2 text-sm font-semibold text-slate-900">
            <SlidersHorizontal className="h-4 w-4 text-slate-400" aria-hidden />
            Filters
          </h2>
          {activeCount > 0 && (
            <button
              type="button"
              onClick={onReset}
              className="text-xs font-medium text-indigo-600 transition hover:text-indigo-700"
            >
              Reset
            </button>
          )}
        </div>
      )}

      <div className={showHeader ? "mt-4 space-y-4" : "space-y-4"}>
        <LocationInput
          value={filters.location}
          suggestions={topLocations}
          onChange={(location) => onChange({ location })}
        />

        <SelectField
          id="filter-company"
          label="Company"
          value={filters.company}
          onChange={(company) => onChange({ company })}
        >
          <option value="">All companies</option>
          {companies.map((company) => (
            <option key={company.company_id} value={company.company_id}>
              {company.company_name} ({formatNumber(company.active_job_count)})
            </option>
          ))}
        </SelectField>

        <SelectField
          id="filter-date"
          label="Date posted"
          value={filters.date_posted}
          onChange={(value) => onChange({ date_posted: value as JobFilters["date_posted"] })}
        >
          <option value="all">Any time</option>
          {Object.entries(DATE_LABELS).map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </SelectField>

        <FacetSelect
          id="filter-employment"
          label="Employment type"
          allLabel="Any type"
          value={filters.employment_type}
          facets={facets?.employment_types ?? []}
          onChange={(employment_type) => onChange({ employment_type })}
        />

        <FacetSelect
          id="filter-workplace"
          label="Workplace"
          allLabel="Any workplace"
          value={filters.workplace_type}
          facets={facets?.workplace_types ?? []}
          onChange={(workplace_type) => onChange({ workplace_type })}
        />

        <FacetSelect
          id="filter-experience"
          label="Experience"
          allLabel="Any level"
          value={filters.experience_level}
          facets={facets?.experience_levels ?? []}
          onChange={(experience_level) => onChange({ experience_level })}
        />

        <FacetSelect
          id="filter-department"
          label="Department"
          allLabel="All departments"
          value={filters.department}
          facets={facets?.departments ?? []}
          onChange={(department) => onChange({ department })}
        />

        <FacetSelect
          id="filter-source"
          label="Source"
          allLabel="All sources"
          value={filters.ats}
          facets={facets?.ats_providers ?? []}
          onChange={(ats) => onChange({ ats })}
        />
      </div>
    </div>
  );
}
