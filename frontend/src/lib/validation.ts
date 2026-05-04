const POLISH_LETTER_PATTERN = /[A-Za-zĄĆĘŁŃÓŚŹŻąćęłńóśźż]/;
const NUMERIC_ONLY_PATTERN = /^[\d\s.,+-]+$/;

export function hasText(value: unknown): boolean {
  return value !== undefined && value !== null && String(value).trim().length > 0;
}

export function validateBusinessText(value: unknown, label: string): string | null {
  const text = String(value ?? "").trim();
  if (!text) {
    return `Uzupełnij pole: ${label}.`;
  }
  if (!POLISH_LETTER_PATTERN.test(text) || NUMERIC_ONLY_PATTERN.test(text)) {
    return `${label} musi zawierać tekst, nie same cyfry.`;
  }
  return null;
}

export function validateCity(value: unknown): string | null {
  const text = String(value ?? "").trim();
  if (!text) {
    return "Uzupełnij pole: Miasto.";
  }
  if (!POLISH_LETTER_PATTERN.test(text) || NUMERIC_ONLY_PATTERN.test(text)) {
    return "Miasto musi zawierać litery, nie same cyfry.";
  }
  if (/[^A-Za-zĄĆĘŁŃÓŚŹŻąćęłńóśźż\s.'-]/.test(text)) {
    return "Miasto może zawierać tylko litery, spacje, apostrof, kropkę i myślnik.";
  }
  return null;
}

export function validateNonNegativeNumber(value: unknown, label: string, required = false): string | null {
  if (!hasText(value)) {
    return required ? `Uzupełnij pole: ${label}.` : null;
  }
  const numeric = Number(value);
  if (!Number.isFinite(numeric) || numeric < 0) {
    return `${label} musi być liczbą nieujemną.`;
  }
  return null;
}

export function validateScore(value: unknown, label: string): string | null {
  if (!hasText(value)) {
    return null;
  }
  const numeric = Number(value);
  if (!Number.isFinite(numeric) || numeric < 1 || numeric > 5) {
    return `${label} musi być liczbą od 1 do 5.`;
  }
  return null;
}
