export function formatDateTime(value?: string | null): string {
  if (!value) return "No date";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("en-GB", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

export function formatDateInput(value?: string | null): string {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value.slice(0, 16);
  const offsetMs = date.getTimezoneOffset() * 60_000;
  return new Date(date.getTime() - offsetMs).toISOString().slice(0, 16);
}

export function fromDateInput(value: string): string {
  return value ? new Date(value).toISOString() : "";
}

export function daysUntil(value: string): number {
  const target = new Date(value).getTime();
  return Math.max(0, Math.ceil((target - Date.now()) / 86_400_000));
}

export function formatMoney(value?: string | number | null): string {
  if (value === undefined || value === null || value === "") return "No data";
  const numeric = Number(value);
  if (Number.isNaN(numeric)) return "No data";
  return new Intl.NumberFormat("en-GB", {
    style: "currency",
    currency: "PLN",
    maximumFractionDigits: 0,
  }).format(numeric);
}

export function formatNumber(value?: string | number | null, fractionDigits = 0): string {
  const numeric = Number(value);
  if (Number.isNaN(numeric)) return "No data";
  return new Intl.NumberFormat("en-GB", {
    minimumFractionDigits: fractionDigits,
    maximumFractionDigits: fractionDigits,
  }).format(numeric);
}

export function formatDurationMinutes(value?: string | number | null): string {
  const minutes = Number(value);
  if (Number.isNaN(minutes)) return "No data";
  if (minutes < 90) return `${formatNumber(minutes, minutes % 1 === 0 ? 0 : 1)} min`;
  const hours = minutes / 60;
  return `${formatNumber(hours, 1)} h`;
}

export function formatPercent(value?: string | number | null): string {
  const numeric = Number(value);
  if (Number.isNaN(numeric)) return "No data";
  const percent = Math.abs(numeric) <= 1 ? numeric * 100 : numeric;
  return `${formatNumber(percent, 1)}%`;
}

export function parserSourceLabel(parserMode?: string, usedFallback?: boolean): string {
  if (usedFallback || parserMode?.includes("fallback") || parserMode === "heuristic") return "Source: fallback mode";
  if (parserMode?.includes("llm") || parserMode === "llm" || parserMode === "hybrid_llm") return "Source: LLM";
  return "Source: deterministic parser";
}

export function translateStatus(value?: string | null): string {
  const map: Record<string, string> = {
    draft: "Draft",
    submitted: "Needs review",
    validated: "Ready to plan",
    planned: "Planned",
    confirmed: "Confirmed",
    in_progress: "In progress",
    completed: "Completed",
    cancelled: "Cancelled",
    available: "Available",
    unavailable: "Unavailable",
    maintenance: "Maintenance",
    active: "Active",
    inactive: "Inactive",
    low: "Low",
    medium: "Medium",
    high: "High",
    critical: "Critical",
  };
  return value ? map[value] ?? value.replace(/_/g, " ") : "No data";
}
