export function formatDateTime(value?: string | null): string {
  if (!value) {
    return "Brak daty";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return new Intl.DateTimeFormat("pl-PL", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

export function formatDateInput(value?: string | null): string {
  if (!value) {
    return "";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value.slice(0, 16);
  }
  const offsetMs = date.getTimezoneOffset() * 60_000;
  return new Date(date.getTime() - offsetMs).toISOString().slice(0, 16);
}

export function fromDateInput(value: string): string {
  if (!value) {
    return "";
  }
  return new Date(value).toISOString();
}

export function daysUntil(value: string): number {
  const target = new Date(value).getTime();
  const now = Date.now();
  return Math.max(0, Math.ceil((target - now) / 86_400_000));
}

export function formatMoney(value?: string | number | null): string {
  const numeric = Number(value ?? 0);
  if (Number.isNaN(numeric)) {
    return "Brak danych";
  }
  return new Intl.NumberFormat("pl-PL", {
    style: "currency",
    currency: "PLN",
    maximumFractionDigits: 0,
  }).format(numeric);
}

export function parserSourceLabel(parserMode?: string, usedFallback?: boolean): string {
  if (usedFallback || parserMode?.includes("fallback") || parserMode === "heuristic") {
    return "Źródło: tryb awaryjny";
  }
  if (parserMode?.includes("llm") || parserMode === "llm" || parserMode === "hybrid_llm") {
    return "Źródło: LLM";
  }
  return "Źródło: parser deterministyczny";
}

export function translateStatus(value?: string | null): string {
  const map: Record<string, string> = {
    draft: "Szkic",
    submitted: "Zgłoszony",
    validated: "Zweryfikowany",
    planned: "Zaplanowany",
    confirmed: "Potwierdzony",
    in_progress: "W trakcie",
    completed: "Zakończony",
    cancelled: "Anulowany",
    available: "Dostępny",
    unavailable: "Niedostępny",
    maintenance: "Serwis",
    active: "Aktywny",
    inactive: "Nieaktywny",
  };
  return value ? map[value] ?? value : "Brak danych";
}
