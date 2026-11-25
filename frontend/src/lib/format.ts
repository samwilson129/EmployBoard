import type { AtsProvider, EmploymentType, WorkplaceType } from "../types";

export function cn(...values: Array<string | false | null | undefined>): string {
  return values.filter(Boolean).join(" ");
}

export function formatNumber(value: number): string {
  return new Intl.NumberFormat("en-US").format(value);
}

export function formatDate(value: string | null | undefined): string {
  if (!value) return "Not disclosed";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Not disclosed";
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  }).format(date);
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) return "Not disclosed";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Not disclosed";
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(date);
}

export function formatRelative(value: string | null | undefined): string {
  if (!value) return "Not disclosed";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Not disclosed";
  const seconds = Math.round((date.getTime() - Date.now()) / 1000);
  const formatter = new Intl.RelativeTimeFormat("en", { numeric: "auto" });
  const ranges: Array<[Intl.RelativeTimeFormatUnit, number]> = [
    ["year", 60 * 60 * 24 * 365],
    ["month", 60 * 60 * 24 * 30],
    ["week", 60 * 60 * 24 * 7],
    ["day", 60 * 60 * 24],
    ["hour", 60 * 60],
    ["minute", 60],
  ];
  for (const [unit, secondsInUnit] of ranges) {
    if (Math.abs(seconds) >= secondsInUnit) {
      return formatter.format(Math.round(seconds / secondsInUnit), unit);
    }
  }
  return "just now";
}

export function formatSalary(
  min: number | null,
  max: number | null,
  currency: string | null,
  interval: string | null,
): string | null {
  if (min == null && max == null) return null;
  const format = (value: number) => {
    if (currency && /^[A-Z]{3}$/.test(currency)) {
      try {
        return new Intl.NumberFormat("en-US", {
          style: "currency",
          currency,
          maximumFractionDigits: 0,
        }).format(value);
      } catch {
        // Fall through to a plain number for unknown ISO codes.
      }
    }
    return new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 }).format(value);
  };

  let range: string;
  if (min != null && max != null && min !== max) {
    range = `${format(min)} – ${format(max)}`;
  } else {
    range = format((min ?? max) as number);
  }
  if (!interval) return range;
  const suffix: Record<string, string> = {
    year: "per year",
    month: "per month",
    week: "per week",
    day: "per day",
    hour: "per hour",
  };
  return `${range} ${suffix[interval] ?? `per ${interval}`}`;
}

export function providerLabel(provider: string | null | undefined): string {
  const labels: Record<string, string> = {
    greenhouse: "Greenhouse",
    lever: "Lever",
    ashby: "Ashby",
    smartrecruiters: "SmartRecruiters",
    recruitee: "Recruitee",
    workable: "Workable",
    personio: "Personio",
    teamtailor: "Teamtailor",
  };
  return provider ? labels[provider] ?? provider : "Unknown source";
}

export function providerBadgeClass(provider: string | null | undefined): string {
  const classes: Record<string, string> = {
    greenhouse: "bg-emerald-50 text-emerald-700 ring-emerald-600/20",
    lever: "bg-violet-50 text-violet-700 ring-violet-600/20",
    ashby: "bg-amber-50 text-amber-800 ring-amber-600/20",
    smartrecruiters: "bg-sky-50 text-sky-700 ring-sky-600/20",
    recruitee: "bg-rose-50 text-rose-700 ring-rose-600/20",
    workable: "bg-blue-50 text-blue-700 ring-blue-600/20",
    personio: "bg-orange-50 text-orange-700 ring-orange-600/20",
    teamtailor: "bg-cyan-50 text-cyan-700 ring-cyan-600/20",
  };
  return provider ? classes[provider] ?? "bg-slate-100 text-slate-700 ring-slate-500/20" : "bg-slate-100 text-slate-700 ring-slate-500/20";
}

export function providerDotClass(provider: AtsProvider | string): string {
  const classes: Record<string, string> = {
    greenhouse: "bg-emerald-500",
    lever: "bg-violet-500",
    ashby: "bg-amber-500",
    smartrecruiters: "bg-sky-500",
    recruitee: "bg-rose-500",
    workable: "bg-blue-500",
    personio: "bg-orange-500",
    teamtailor: "bg-cyan-500",
  };
  return classes[provider] ?? "bg-slate-400";
}

export function employmentBadgeClass(value: EmploymentType | string | null): string {
  const classes: Record<string, string> = {
    "Full-time": "bg-slate-100 text-slate-700",
    "Part-time": "bg-blue-50 text-blue-700",
    Contract: "bg-amber-50 text-amber-800",
    Internship: "bg-purple-50 text-purple-700",
    Temporary: "bg-orange-50 text-orange-800",
    Other: "bg-slate-100 text-slate-600",
  };
  return value ? classes[value] ?? "bg-slate-100 text-slate-600" : "bg-slate-100 text-slate-600";
}

export function workplaceBadgeClass(value: WorkplaceType | string | null): string {
  const classes: Record<string, string> = {
    Remote: "bg-teal-50 text-teal-700",
    Hybrid: "bg-indigo-50 text-indigo-700",
    "On-site": "bg-slate-100 text-slate-700",
    Unknown: "bg-slate-100 text-slate-600",
  };
  return value ? classes[value] ?? "bg-slate-100 text-slate-600" : "bg-slate-100 text-slate-600";
}

export function initials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return "?";
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return `${parts[0][0]}${parts[parts.length - 1][0]}`.toUpperCase();
}

const AVATAR_COLORS = [
  "bg-indigo-100 text-indigo-700",
  "bg-emerald-100 text-emerald-700",
  "bg-amber-100 text-amber-800",
  "bg-sky-100 text-sky-700",
  "bg-rose-100 text-rose-700",
  "bg-violet-100 text-violet-700",
  "bg-teal-100 text-teal-700",
];

export function avatarColor(name: string): string {
  let hash = 0;
  for (let index = 0; index < name.length; index += 1) {
    hash = (hash * 31 + name.charCodeAt(index)) >>> 0;
  }
  return AVATAR_COLORS[hash % AVATAR_COLORS.length];
}

export function truncate(value: string, length: number): string {
  return value.length <= length ? value : `${value.slice(0, length).trimEnd()}…`;
}
