import { providerLabel } from "./format";
import type { CompanyOut, JobFilters } from "../types";

export const DATE_LABELS: Record<string, string> = {
  "24h": "Past 24 hours",
  "7d": "Past 7 days",
  "30d": "Past 30 days",
};

export function countActiveFilters(filters: JobFilters): number {
  let count = 0;
  if (filters.q.trim()) count += 1;
  if (filters.location.trim()) count += 1;
  if (filters.company) count += 1;
  if (filters.ats) count += 1;
  if (filters.employment_type) count += 1;
  if (filters.workplace_type) count += 1;
  if (filters.experience_level) count += 1;
  if (filters.department) count += 1;
  if (filters.date_posted !== "all") count += 1;
  return count;
}

export interface FilterChip {
  key: keyof JobFilters;
  label: string;
}

export function activeFilterChips(
  filters: JobFilters,
  companies: CompanyOut[],
): FilterChip[] {
  const chips: FilterChip[] = [];
  if (filters.q.trim()) chips.push({ key: "q", label: `"${filters.q.trim()}"` });
  if (filters.location.trim()) {
    chips.push({ key: "location", label: `Location: ${filters.location.trim()}` });
  }
  if (filters.company) {
    const match = companies.find((company) => company.company_id === filters.company);
    chips.push({ key: "company", label: `Company: ${match?.company_name ?? filters.company}` });
  }
  if (filters.ats) {
    chips.push({ key: "ats", label: `Source: ${providerLabel(filters.ats)}` });
  }
  if (filters.employment_type) {
    chips.push({ key: "employment_type", label: filters.employment_type });
  }
  if (filters.workplace_type) {
    chips.push({ key: "workplace_type", label: filters.workplace_type });
  }
  if (filters.experience_level) {
    chips.push({ key: "experience_level", label: `${filters.experience_level} level` });
  }
  if (filters.department) {
    chips.push({ key: "department", label: `Department: ${filters.department}` });
  }
  if (filters.date_posted !== "all") {
    chips.push({ key: "date_posted", label: DATE_LABELS[filters.date_posted] ?? filters.date_posted });
  }
  return chips;
}

export function clearFilterValue(filters: JobFilters, key: keyof JobFilters): JobFilters {
  if (key === "date_posted") return { ...filters, date_posted: "all" };
  if (key === "sort" || key === "page" || key === "limit") return filters;
  return { ...filters, [key]: "" };
}
