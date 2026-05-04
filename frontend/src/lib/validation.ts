const LETTER_PATTERN = /\p{L}/u;
const CITY_PATTERN = /^[\p{L}\s.'-]+$/u;

export function validateBusinessText(value: unknown, label: string): string | null {
  const text = String(value ?? "").trim();
  if (!text) return `Fill in: ${label}.`;
  if (!LETTER_PATTERN.test(text)) return `${label} must contain text, not only digits.`;
  return null;
}

export function validateCity(value: unknown): string | null {
  const text = String(value ?? "").trim();
  if (!text) return "Fill in: City.";
  if (!LETTER_PATTERN.test(text)) return "City must contain letters, not only digits.";
  if (!CITY_PATTERN.test(text)) {
    return "City can contain only letters, spaces, apostrophe, dot and hyphen.";
  }
  return null;
}

export function validateNonNegativeNumber(value: unknown, label: string, required = false): string | null {
  const raw = String(value ?? "").trim();
  if (!raw) return required ? `Fill in: ${label}.` : null;
  const numeric = Number(raw);
  if (Number.isNaN(numeric) || numeric < 0) return `${label} must be a non-negative number.`;
  return null;
}

export function validateScore(value: unknown, label: string): string | null {
  const raw = String(value ?? "").trim();
  if (!raw) return null;
  const numeric = Number(raw);
  if (Number.isNaN(numeric) || numeric < 1 || numeric > 5) return `${label} must be a number from 1 to 5.`;
  return null;
}
