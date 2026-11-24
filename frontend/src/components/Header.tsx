import { Briefcase, Building2, Clock, Database } from "lucide-react";
import type { LucideIcon } from "lucide-react";

import { formatNumber, formatRelative } from "../lib/format";
import type { StatsResponse } from "../types";

interface StatProps {
  icon: LucideIcon;
  label: string;
  value: string;
  loading: boolean;
  title?: string;
}

function Stat({ icon: Icon, label, value, loading, title }: StatProps) {
  return (
    <div className="flex items-center gap-2" title={title}>
      <Icon className="h-4 w-4 shrink-0 text-slate-400" aria-hidden />
      <div className="min-w-0">
        <dt className="text-[11px] font-medium uppercase tracking-wide text-slate-400">{label}</dt>
        <dd className="truncate text-sm font-semibold tabular-nums text-slate-900">
          {loading ? (
            <span className="inline-block h-4 w-10 animate-pulse rounded bg-slate-200" aria-hidden />
          ) : (
            value
          )}
        </dd>
      </div>
    </div>
  );
}

interface HeaderProps {
  stats: StatsResponse | null;
  loading: boolean;
}

export function Header({ stats, loading }: HeaderProps) {
  return (
    <header className="border-b border-slate-200 bg-white">
      <div className="mx-auto flex max-w-[1400px] flex-col gap-4 px-4 py-4 sm:px-6 lg:flex-row lg:items-center lg:justify-between lg:px-8">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-indigo-600 text-white shadow-sm">
            <Briefcase className="h-5 w-5" aria-hidden />
          </div>
          <div>
            <p className="text-base font-semibold leading-tight tracking-tight text-slate-900">
              EmployBoard
            </p>
            <p className="text-sm text-slate-500">Every job. Every source. One board.</p>
          </div>
        </div>

        <dl className="grid grid-cols-2 gap-x-6 gap-y-3 sm:grid-cols-4">
          <Stat
            icon={Briefcase}
            label="Active jobs"
            value={stats ? formatNumber(stats.total_active_jobs) : "—"}
            loading={loading}
            title="Jobs currently listed as open"
          />
          <Stat
            icon={Building2}
            label="Companies"
            value={stats ? formatNumber(stats.active_companies) : "—"}
            loading={loading}
            title="Companies with an active career board"
          />
          <Stat
            icon={Database}
            label="Sources"
            value={stats ? formatNumber(stats.integrated_sources) : "—"}
            loading={loading}
            title="Applicant tracking systems integrated"
          />
          <Stat
            icon={Clock}
            label="Last sync"
            value={stats ? formatRelative(stats.last_successful_sync) : "—"}
            loading={loading}
            title={stats?.last_successful_sync ?? "No successful sync recorded yet"}
          />
        </dl>
      </div>
    </header>
  );
}
