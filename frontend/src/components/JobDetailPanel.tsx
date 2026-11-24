import { useEffect, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";
import DOMPurify from "dompurify";
import { AlertCircle, ExternalLink, RefreshCw, X } from "lucide-react";

import { fetchJob } from "../api";
import {
  cn,
  employmentBadgeClass,
  formatDate,
  formatRelative,
  formatSalary,
  providerBadgeClass,
  providerLabel,
  workplaceBadgeClass,
} from "../lib/format";
import type { JobDetail } from "../types";
import { CompanyLogo } from "./CompanyLogo";

interface JobDetailPanelProps {
  jobId: string;
  onClose: () => void;
}

function Meta({ label, value }: { label: string; value: string | null }) {
  return (
    <div className="min-w-0">
      <dt className="meta-label">{label}</dt>
      <dd className="meta-value break-words">{value || "Not disclosed"}</dd>
    </div>
  );
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section>
      <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">{title}</h3>
      <div className="mt-2">{children}</div>
    </section>
  );
}

function RichText({ value }: { value: string }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const isHtml = /<\/?[a-z][\s\S]*>/i.test(value);
  const html = useMemo(
    () => (isHtml ? DOMPurify.sanitize(value, { USE_PROFILES: { html: true } }) : ""),
    [isHtml, value],
  );

  useEffect(() => {
    containerRef.current?.querySelectorAll("a").forEach((anchor) => {
      anchor.setAttribute("target", "_blank");
      anchor.setAttribute("rel", "noopener noreferrer");
    });
  }, [html]);

  if (!html) {
    return (
      <p className="whitespace-pre-line text-sm leading-relaxed text-slate-700">{value}</p>
    );
  }

  return (
    <div
      ref={containerRef}
      className="job-html"
      dangerouslySetInnerHTML={{ __html: html }}
    />
  );
}

function DetailSkeleton() {
  return (
    <div className="space-y-5 p-4" aria-busy="true" aria-label="Loading job details">
      <div className="flex items-start gap-3">
        <div className="h-14 w-14 animate-pulse rounded-lg bg-slate-200" />
        <div className="flex-1 space-y-2">
          <div className="h-5 w-3/4 animate-pulse rounded bg-slate-200" />
          <div className="h-3 w-1/3 animate-pulse rounded bg-slate-100" />
          <div className="h-5 w-1/2 animate-pulse rounded bg-slate-100" />
        </div>
      </div>
      <div className="h-24 animate-pulse rounded-lg bg-slate-100" />
      <div className="space-y-2">
        <div className="h-3 w-full animate-pulse rounded bg-slate-100" />
        <div className="h-3 w-full animate-pulse rounded bg-slate-100" />
        <div className="h-3 w-5/6 animate-pulse rounded bg-slate-100" />
        <div className="h-3 w-2/3 animate-pulse rounded bg-slate-100" />
      </div>
    </div>
  );
}

function DetailBody({ job }: { job: JobDetail }) {
  const salary = formatSalary(
    job.salary_min,
    job.salary_max,
    job.salary_currency,
    job.salary_interval,
  );

  return (
    <div className="space-y-5 p-4">
      <div className="flex items-start gap-3">
        <CompanyLogo
          name={job.company.company_name}
          logoUrl={job.company.company_logo_url}
          size="lg"
        />
        <div className="min-w-0">
          <h1 className="text-base font-semibold leading-snug text-slate-900">{job.title}</h1>
          <p className="mt-0.5 text-sm text-slate-600">{job.company.company_name}</p>
          <div className="mt-2 flex flex-wrap gap-1.5">
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
          </div>
        </div>
      </div>

      <dl className="grid grid-cols-2 gap-x-3 gap-y-3 rounded-lg border border-slate-200 bg-slate-50/70 p-3">
        <Meta label="Location" value={job.location} />
        <Meta label="Department" value={job.department} />
        <Meta label="Employment" value={job.employment_type} />
        <Meta
          label="Workplace"
          value={job.workplace_type === "Unknown" ? null : job.workplace_type}
        />
        <Meta
          label="Experience"
          value={job.experience_level === "Unknown" ? null : job.experience_level}
        />
        <Meta label="Posted" value={job.posted_at ? formatDate(job.posted_at) : null} />
      </dl>

      {salary && (
        <div className="rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2">
          <p className="text-[11px] font-semibold uppercase tracking-wide text-emerald-700">
            Compensation
          </p>
          <p className="mt-0.5 text-sm font-semibold text-emerald-900">{salary}</p>
        </div>
      )}

      {job.description && (
        <Section title="About this role">
          <RichText value={job.description} />
        </Section>
      )}

      {job.requirements && (
        <Section title="Requirements">
          <RichText value={job.requirements} />
        </Section>
      )}

      {job.responsibilities && (
        <Section title="Responsibilities">
          <RichText value={job.responsibilities} />
        </Section>
      )}

      {job.skills && job.skills.length > 0 && (
        <Section title="Skills">
          <ul className="flex flex-wrap gap-1.5">
            {job.skills.map((skill) => (
              <li key={skill} className="tag bg-slate-100 text-slate-700">
                {skill}
              </li>
            ))}
          </ul>
        </Section>
      )}

      <Section title="Sources">
        <ul className="space-y-2">
          {job.sources.map((source) => (
            <li
              key={source.source_id}
              className="flex items-center justify-between gap-2 rounded-lg border border-slate-200 px-3 py-2"
            >
              <div className="min-w-0">
                <span
                  className={cn(
                    "inline-flex items-center rounded-md px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide ring-1 ring-inset",
                    providerBadgeClass(source.ats_provider),
                  )}
                >
                  {providerLabel(source.ats_provider)}
                </span>
                <p className="mt-1 truncate font-mono text-[11px] text-slate-400">
                  ID {source.external_job_id}
                </p>
              </div>
              {source.original_job_url ? (
                <a
                  href={source.original_job_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex shrink-0 items-center gap-1 text-xs font-medium text-indigo-600 hover:underline"
                >
                  Original
                  <ExternalLink className="h-3 w-3" aria-hidden />
                </a>
              ) : (
                <span className="shrink-0 text-xs text-slate-400">No link</span>
              )}
            </li>
          ))}
        </ul>
      </Section>

      {job.duplicate_of_job_id && (
        <p className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
          This posting also appears from another source and has been linked as a duplicate.
        </p>
      )}

      <div className="space-y-1 border-t border-slate-100 pt-3 text-[11px] text-slate-400">
        <p>Posted {job.posted_at ? formatDate(job.posted_at) : "not disclosed"}</p>
        <p>Last verified {formatRelative(job.last_synced_at ?? job.last_seen_at)}</p>
      </div>
    </div>
  );
}

export function JobDetailPanel({ jobId, onClose }: JobDetailPanelProps) {
  const [job, setJob] = useState<JobDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError(null);
    setJob(null);

    fetchJob(jobId, controller.signal)
      .then((data) => {
        if (controller.signal.aborted) return;
        setJob(data);
        setLoading(false);
      })
      .catch((caught: unknown) => {
        if (controller.signal.aborted) return;
        setError(caught instanceof Error ? caught.message : "Unable to load this job.");
        setLoading(false);
      });

    return () => controller.abort();
  }, [jobId, reloadKey]);

  return (
    <div className="flex h-full min-h-0 flex-col bg-white">
      <div className="flex items-start justify-between gap-3 border-b border-slate-200 px-4 py-3">
        <div className="min-w-0">
          <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-400">
            Job details
          </p>
          <h2 className="mt-0.5 truncate text-sm font-semibold text-slate-900">
            {job?.company.company_name ?? "Loading job"}
          </h2>
        </div>
        <button
          type="button"
          onClick={onClose}
          className="shrink-0 rounded-lg border border-slate-200 p-1.5 text-slate-500 transition hover:bg-slate-50 hover:text-slate-800"
          aria-label="Close job details"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto scroll-slim">
        {loading && <DetailSkeleton />}

        {!loading && error && (
          <div className="p-6 text-center">
            <AlertCircle className="mx-auto h-8 w-8 text-rose-400" aria-hidden />
            <p className="mt-3 text-sm font-semibold text-slate-900">Could not load this job</p>
            <p className="mt-1 text-sm text-slate-500">{error}</p>
            <button
              type="button"
              onClick={() => setReloadKey((key) => key + 1)}
              className="mt-4 inline-flex items-center gap-2 rounded-lg border border-slate-300 px-3 py-2 text-sm font-medium text-slate-700 transition hover:border-slate-400"
            >
              <RefreshCw className="h-4 w-4" aria-hidden />
              Try again
            </button>
          </div>
        )}

        {!loading && !error && job && <DetailBody job={job} />}
      </div>

      {job && (
        <div className="border-t border-slate-200 bg-white p-4">
          <a
            href={job.application_url}
            target="_blank"
            rel="noopener noreferrer"
            className="flex w-full items-center justify-center gap-2 rounded-lg bg-indigo-600 px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-indigo-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500/40"
          >
            Apply on {providerLabel(job.primary_ats_provider)}
            <ExternalLink className="h-4 w-4" aria-hidden />
          </a>
          <p className="mt-2 text-center text-[11px] text-slate-400">
            Opens the original posting in a new tab.
          </p>
        </div>
      )}
    </div>
  );
}
