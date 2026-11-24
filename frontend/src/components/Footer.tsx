import { ExternalLink } from "lucide-react";

import { cn, formatNumber, providerDotClass } from "../lib/format";
import type { SourceProviderOut } from "../types";

interface FooterProps {
  sources: SourceProviderOut[];
}

export function Footer({ sources }: FooterProps) {
  const integrated = sources.filter((source) => source.is_integrated);

  return (
    <footer className="mt-10 border-t border-slate-200 bg-white">
      <div className="mx-auto max-w-[1400px] px-4 py-6 sm:px-6 lg:px-8">
        <div className="flex flex-col gap-6 md:flex-row md:items-start md:justify-between">
          <div className="max-w-md">
            <p className="text-sm font-semibold text-slate-900">EmployBoard</p>
            <p className="mt-1 text-xs leading-relaxed text-slate-500">
              Listings are pulled directly from public company career pages through official
              applicant tracking system APIs. Nothing is invented: details the source does not
              publish stay blank.
            </p>
          </div>

          <div>
            <p className="meta-label">Integrated sources</p>
            <ul className="mt-2 space-y-1.5">
              {integrated.map((source) => (
                <li
                  key={source.provider}
                  className="flex items-center gap-2 text-xs text-slate-600"
                >
                  <span
                    className={cn("h-1.5 w-1.5 rounded-full", providerDotClass(source.provider))}
                    aria-hidden
                  />
                  <span className="font-medium text-slate-800">{source.display_name}</span>
                  <span className="tabular-nums text-slate-400">
                    {formatNumber(source.active_job_count)} jobs
                  </span>
                  <a
                    href={source.documentation_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-slate-400 transition hover:text-indigo-600"
                    aria-label={`${source.display_name} API documentation`}
                  >
                    <ExternalLink className="h-3 w-3" />
                  </a>
                </li>
              ))}
              {integrated.length === 0 && (
                <li className="text-xs text-slate-400">No sources connected yet.</li>
              )}
            </ul>
          </div>
        </div>

        <p className="mt-6 border-t border-slate-100 pt-4 text-xs text-slate-400">
          Job data is refreshed every six hours. Always apply on the original posting.
        </p>
      </div>
    </footer>
  );
}
