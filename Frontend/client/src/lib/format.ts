/** Numeric columns arrive as strings; parse before doing any arithmetic. */
export function toAmount(value: string | number | null | undefined): number {
  if (value === null || value === undefined) return 0;
  const parsed = typeof value === "number" ? value : Number.parseFloat(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

export function formatPeso(value: string | number | null | undefined): string {
  return `₱${toAmount(value).toLocaleString("en-PH", {
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  })}`;
}

/** Today in the local timezone as YYYY-MM-DD, which is what the API expects. */
export function todayIso(): string {
  const now = new Date();
  const offsetMinutes = now.getTimezoneOffset();
  return new Date(now.getTime() - offsetMinutes * 60_000)
    .toISOString()
    .slice(0, 10);
}

export function formatDateLabel(iso: string): string {
  // Parse as a plain calendar date; `new Date("2026-08-31")` is UTC midnight and
  // would render as the previous day west of Greenwich.
  const [year, month, day] = iso.split("-").map(Number);
  if (!year || !month || !day) return iso;
  return new Date(year, month - 1, day).toLocaleDateString("en-PH", {
    weekday: "short",
    month: "short",
    day: "numeric",
  });
}

export function formatDateTimeLabel(iso: string | null): string | null {
  if (!iso) return null;
  return new Date(iso).toLocaleString("en-PH", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}
