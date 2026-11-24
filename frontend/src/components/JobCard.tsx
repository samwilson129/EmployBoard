import { ArrowUpRight, Clock, Layers, MapPin } from "lucide-react";
import type { KeyboardEvent } from "react";

import {
  cn,
  employmentBadgeClass,
  formatRelative,
  formatSalary,
  providerBadgeClass,
  providerLabel,
  workplaceBadgeClass,
} from "../lib/format";
import type { JobListItem } from "../types";
import { CompanyLogo } from "./CompanyLogo";

interface JobCardProps {
  job: JobListItem;
  selected: boolean;
  onSelect: (jobId: string) => void;
}

export function JobCard({ job, selected, onSelect }: JobCardProps) {
  const salary = formatSalary(
    job.salary_min,
    job.salary_max,
    job.salary_currency,
    job.salary_interval,
  );
  const posted = job.posted_at ?? job.first_seen_at;

  const handleKeyDown = (event: KeyboardEvent<HTMLElement>) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      onSelect(job.job_id);
    }
  };

  return (
    <article
      className={cn(
        "job-card group cursor-pointer focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500/40",
        selected && "border-indigo-300 ring-1 ring-indigo-200",
      )}
      onClick={() => onSelect(job.job_id)}
      onKeyDown={handleKeyDown}
      role="button"
      tabIndex={0}
      aria-pressed={selected}
      aria-label={`${job.title} at ${job.company.company_name}`}
    >
      <div className="flex items-start gap-3">
        <CompanyLogo
          name={job.company.company_name}
          logoUrl={job.company.company_logo_url}
          size="md"
        />

        <div className="min-w-0 flex-1">
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <h3 className="truncate text-sm font-semibold text-slate-900 transition group-hover:text-indigo-700">
                {job.title}
              </h3>
              <p className="mt-0.5 truncate text-sm text-slate-600">
                {job.company.company_name}
              </p>
            </div>
            <a
              href={job.application_url}
              target="_blank"
              rel="noopener noreferrer"
              onClick={(event) => event.stopPropagation()}
              className="inline-flex shrink-0 items-center gap-1 rounded-md border border-slate-300 bg-white px-2 py-1 text-xs font-medium text-slate-700 transition hover:border-indigo-300 hover:text-indigo-700"
              aria-label={`Apply for ${job.title} at ${job.company.company_name} on ${providerLabel(job.primary_ats_provider)}`}
            >
              Apply
              <ArrowUpRight className="h-3 w-3" aria-hidden />
            </a>
          </div>

          <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-slate-500">
            {job.location && (
              <span className="inline-flex min-w-0 items-center gap-1">
                <MapPin className="h-3 w-3 shrink-0" aria-hidden />
                <span className="truncate">{job.location}</span>
              </span>
            )}
            {job.department && (
              <span className="inline-flex min-w-0 items-center gap-1">
                <Layers className="h-3 w-3 shrink-0" aria-hidden />
                <span className="truncate">{job.department}</span>
              </span>
            )}
            <span className="inline-flex items-center gap-1">
              <Clock className="h-3 w-3 shrink-0" aria-hidden />
              {job.posted_at ? `Posted ${formatRelative(posted)}` : `Added ${formatRelative(posted)}`}
            </span>
          </div>

          {job.description_snippet && (
            <p className="mt-2 line-clamp-2 text-xs leading-relaxed text-slate-500">
              {job.description_snippet}
            </p>
          )}

          <div className="mt-3 flex flex-wrap items-center gap-1.5">
            {job.employment_type && (
              <span className={cn("tag", employmentBadgeClass(job.employment_type))}>
                {job.employment_type}
              </span>
            )}
            {job.workplace_type && job.workplace_type !== "Unknown" && (
              <span className={cn("tag", workplaceBadgeClass(job.workplace_type))}>
                {job.workplace_type}
              </span>
            )}
            {job.experience_level && job.experience_level !== "Unknown" && (
              <span className="tag bg-slate-100 text-slate-600">{job.experience_level}</span>
            )}
            {salary && (
              <span className="tag bg-emerald-50 text-emerald-800">{salary}</span>
            )}

            {job.primary_ats_provider && (
              <span
                className={cn(
                  "ml-auto inline-flex items-center rounded-md px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide ring-1 ring-inset",
                  providerBadgeClass(job.primary_ats_provider),
                )}
              >
                {providerLabel(job.primary_ats_provider)}
              </span>
            )}
          </div>
        </div>
      </div>
    </article>
  );
}
