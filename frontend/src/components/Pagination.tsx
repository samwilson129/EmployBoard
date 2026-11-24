import { ChevronLeft, ChevronRight } from "lucide-react";

import { cn, formatNumber } from "../lib/format";

interface PaginationProps {
  page: number;
  pages: number;
  total: number;
  limit: number;
  disabled?: boolean;
  onPageChange: (page: number) => void;
  onLimitChange: (limit: number) => void;
}

function pageItems(page: number, pages: number): Array<number | "gap"> {
  if (pages <= 7) {
    return Array.from({ length: pages }, (_, index) => index + 1);
  }
  const items: Array<number | "gap"> = [1];
  const start = Math.max(2, page - 1);
  const end = Math.min(pages - 1, page + 1);
  if (start > 2) items.push("gap");
  for (let current = start; current <= end; current += 1) items.push(current);
  if (end < pages - 1) items.push("gap");
  items.push(pages);
  return items;
}

export function Pagination({
  page,
  pages,
  total,
  limit,
  disabled = false,
  onPageChange,
  onLimitChange,
}: PaginationProps) {
  if (total === 0) return null;

  const first = (page - 1) * limit + 1;
  const last = Math.min(page * limit, total);
  const items = pageItems(page, pages);

  return (
    <nav
      className="mt-5 flex flex-col gap-3 border-t border-slate-200 pt-4 sm:flex-row sm:items-center sm:justify-between"
      aria-label="Job results pages"
    >
      <div className="flex items-center gap-3 text-xs text-slate-500">
        <span>
          Showing <span className="font-medium text-slate-800">{formatNumber(first)}</span>-
          <span className="font-medium text-slate-800">{formatNumber(last)}</span> of{" "}
          <span className="font-medium text-slate-800">{formatNumber(total)}</span>
        </span>
        <label htmlFor="page-size" className="sr-only">
          Jobs per page
        </label>
        <select
          id="page-size"
          value={limit}
          disabled={disabled}
          onChange={(event) => onLimitChange(Number(event.target.value))}
          className="rounded-md border border-slate-300 bg-white px-2 py-1 text-xs text-slate-700 outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/20"
        >
          <option value={20}>20 / page</option>
          <option value={50}>50 / page</option>
          <option value={100}>100 / page</option>
        </select>
      </div>

      {pages > 1 && (
        <div className="flex items-center gap-1">
          <button
            type="button"
            onClick={() => onPageChange(page - 1)}
            disabled={page <= 1 || disabled}
            className="inline-flex h-8 items-center gap-1 rounded-md border border-slate-300 bg-white px-2 text-xs font-medium text-slate-700 transition hover:border-slate-400 disabled:cursor-not-allowed disabled:opacity-40"
          >
            <ChevronLeft className="h-3.5 w-3.5" aria-hidden />
            Prev
          </button>

          {items.map((item, index) =>
            item === "gap" ? (
              <span key={`gap-${index}`} className="px-1 text-xs text-slate-400">
                …
              </span>
            ) : (
              <button
                key={item}
                type="button"
                onClick={() => onPageChange(item)}
                disabled={disabled}
                aria-current={item === page ? "page" : undefined}
                className={cn(
                  "inline-flex h-8 min-w-8 items-center justify-center rounded-md border px-2 text-xs font-medium transition disabled:cursor-not-allowed disabled:opacity-40",
                  item === page
                    ? "border-indigo-600 bg-indigo-600 text-white"
                    : "border-slate-300 bg-white text-slate-700 hover:border-slate-400",
                )}
              >
                {item}
              </button>
            ),
          )}

          <button
            type="button"
            onClick={() => onPageChange(page + 1)}
            disabled={page >= pages || disabled}
            className="inline-flex h-8 items-center gap-1 rounded-md border border-slate-300 bg-white px-2 text-xs font-medium text-slate-700 transition hover:border-slate-400 disabled:cursor-not-allowed disabled:opacity-40"
          >
            Next
            <ChevronRight className="h-3.5 w-3.5" aria-hidden />
          </button>
        </div>
      )}
    </nav>
  );
}
