import { useMemo, useState } from "react";
import { Alert, Box, Button, Chip, Grid, Paper, Stack, TextField, Typography } from "@mui/material";

import { StatusBanner } from "../components/StatusBanner";
import { useAuth } from "../lib/auth";
import { formatDateInput, fromDateInput, parserSourceLabel } from "../lib/format";
import { validateBusinessText, validateCity, validateNonNegativeNumber } from "../lib/validation";
import type { EventDraft, IntakeCommitResponse, IntakePreviewResponse } from "../types/api";

const EMPTY_TEXT = `Gala firmowa Q3 w Warszawie, 12 czerwca 2026 od 10:00 do 18:00. Około 250 osób, potrzebny koordynator i van transportowy.`;

const requiredFields: Array<{ key: keyof EventDraft; label: string }> = [
  { key: "event_name", label: "Nazwa eventu" },
  { key: "client_name", label: "Klient" },
  { key: "location_name", label: "Miejsce" },
  { key: "city", label: "Miasto" },
  { key: "event_type", label: "Typ eventu" },
  { key: "planned_start", label: "Start" },
  { key: "planned_end", label: "Koniec" },
];

export function IntakePage(): JSX.Element {
  const { api } = useAuth();
  const [rawInput, setRawInput] = useState(EMPTY_TEXT);
  const [draft, setDraft] = useState<EventDraft | null>(null);
  const [source, setSource] = useState<string | null>(null);
  const [assumptions, setAssumptions] = useState<string[]>([]);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [success, setSuccess] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const hasDraft = Boolean(draft);
  const canAdd = hasDraft && Object.keys(fieldErrors).length === 0;

  const updateDraft = (patch: Partial<EventDraft>): void => {
    setDraft((current) => (current ? { ...current, ...patch } : current));
  };

  const validateDraft = (): boolean => {
    if (!draft) {
      setFieldErrors({ form: "Najpierw wprowadź opis eventu." });
      return false;
    }
    const nextErrors: Record<string, string> = {};
    for (const field of requiredFields) {
      const value = draft[field.key];
      if (value === undefined || value === null || String(value).trim() === "") {
        nextErrors[field.key] = `Uzupełnij pole: ${field.label}.`;
      }
    }
    const eventNameError = validateBusinessText(draft.event_name, "Nazwa eventu");
    if (eventNameError) nextErrors.event_name = eventNameError;
    const clientError = validateBusinessText(draft.client_name, "Klient");
    if (clientError) nextErrors.client_name = clientError;
    const locationError = validateBusinessText(draft.location_name, "Miejsce");
    if (locationError) nextErrors.location_name = locationError;
    const cityError = validateCity(draft.city);
    if (cityError) nextErrors.city = cityError;
    const eventTypeError = validateBusinessText(draft.event_type, "Typ eventu");
    if (eventTypeError) nextErrors.event_type = eventTypeError;
    const attendeeError = validateNonNegativeNumber(draft.attendee_count, "Liczba uczestników", true);
    if (attendeeError) nextErrors.attendee_count = attendeeError;
    const budgetError = validateNonNegativeNumber(draft.budget_estimate, "Budżet");
    if (budgetError) nextErrors.budget_estimate = budgetError;
    if (draft.planned_start && draft.planned_end && new Date(draft.planned_end) <= new Date(draft.planned_start)) {
      nextErrors.planned_end = "Koniec musi być po starcie eventu.";
    }
    setFieldErrors(nextErrors);
    return Object.keys(nextErrors).length === 0;
  };

  const preview = async (): Promise<void> => {
    setError(null);
    setSuccess(null);
    setIsLoading(true);
    try {
      const data = await api.request<IntakePreviewResponse>("POST", "/api/ai-agents/ingest-event/preview", {
        raw_input: rawInput,
        prefer_langgraph: true,
      });
      setDraft(data.draft);
      setAssumptions(data.assumptions);
      setSource(parserSourceLabel(data.parser_mode, data.used_fallback));
      const gapErrors = Object.fromEntries(data.gaps.filter((gap) => gap.severity === "critical").map((gap) => [gap.field, gap.message]));
      setFieldErrors(gapErrors);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Nie udało się przygotować arkusza eventu.");
    } finally {
      setIsLoading(false);
    }
  };

  const commit = async (): Promise<void> => {
    if (!validateDraft() || !draft) {
      return;
    }
    setError(null);
    setIsLoading(true);
    try {
      const data = await api.request<IntakeCommitResponse>("POST", "/api/ai-agents/ingest-event/commit", {
        draft,
        assumptions,
        parser_mode: source?.includes("LLM") ? "hybrid_llm" : "manual_commit",
        used_fallback: source?.includes("awaryjny") ?? false,
      });
      setSuccess(`Dodano event do bazy. Numer eventu: ${data.event_id}.`);
      setDraft(null);
      setRawInput(EMPTY_TEXT);
      setFieldErrors({});
      setAssumptions([]);
      setSource(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Nie udało się dodać eventu.");
    } finally {
      setIsLoading(false);
    }
  };

  const requiredErrorCount = useMemo(() => Object.keys(fieldErrors).filter((key) => key !== "form").length, [fieldErrors]);

  return (
    <Stack spacing={2.5}>
      <Typography variant="h4">Nowy event</Typography>
      {success && <StatusBanner severity="success" title="Event dodany" message={success} />}
      {error && <Alert severity="error">{error}</Alert>}
      {!draft && (
        <Paper variant="outlined" sx={{ p: 3, borderRadius: 2 }}>
          <Stack spacing={2}>
            <TextField
              label="Opis eventu"
              multiline
              minRows={8}
              value={rawInput}
              onChange={(event) => setRawInput(event.target.value)}
              fullWidth
            />
            <Box>
              <Button variant="contained" onClick={() => void preview()} disabled={isLoading || rawInput.trim().length === 0}>
                Wprowadź
              </Button>
            </Box>
          </Stack>
        </Paper>
      )}
      {draft && (
        <Paper variant="outlined" sx={{ p: 3, borderRadius: 2 }}>
          <Stack spacing={2.5}>
            <Stack direction={{ xs: "column", sm: "row" }} spacing={1} alignItems={{ xs: "flex-start", sm: "center" }}>
              <Typography variant="h6">Arkusz eventu</Typography>
              {source && <Chip label={source} color={source.includes("LLM") ? "success" : "warning"} variant="outlined" />}
              {requiredErrorCount > 0 && <Chip label={`Braki: ${requiredErrorCount}`} color="error" />}
            </Stack>
            {fieldErrors.form && <Alert severity="warning">{fieldErrors.form}</Alert>}
            <Grid container spacing={2}>
              <Grid item xs={12} md={6}>
                <TextField
                  label="Nazwa eventu"
                  value={draft.event_name}
                  onChange={(event) => updateDraft({ event_name: event.target.value })}
                  error={Boolean(fieldErrors.event_name)}
                  helperText={fieldErrors.event_name}
                  fullWidth
                />
              </Grid>
              <Grid item xs={12} md={6}>
                <TextField
                  label="Klient"
                  value={draft.client_name}
                  onChange={(event) => updateDraft({ client_name: event.target.value })}
                  error={Boolean(fieldErrors.client_name)}
                  helperText={fieldErrors.client_name}
                  fullWidth
                />
              </Grid>
              <Grid item xs={12} md={6}>
                <TextField
                  label="Miejsce"
                  value={draft.location_name}
                  onChange={(event) => updateDraft({ location_name: event.target.value })}
                  error={Boolean(fieldErrors.location_name)}
                  helperText={fieldErrors.location_name}
                  fullWidth
                />
              </Grid>
              <Grid item xs={12} md={6}>
                <TextField
                  label="Miasto"
                  value={draft.city}
                  onChange={(event) => updateDraft({ city: event.target.value })}
                  error={Boolean(fieldErrors.city)}
                  helperText={fieldErrors.city}
                  fullWidth
                />
              </Grid>
              <Grid item xs={12} md={4}>
                <TextField
                  label="Typ eventu"
                  value={draft.event_type}
                  onChange={(event) => updateDraft({ event_type: event.target.value })}
                  error={Boolean(fieldErrors.event_type)}
                  helperText={fieldErrors.event_type}
                  fullWidth
                />
              </Grid>
              <Grid item xs={12} md={4}>
                <TextField
                  label="Liczba uczestników"
                  type="number"
                  value={draft.attendee_count}
                  onChange={(event) => updateDraft({ attendee_count: Number(event.target.value) })}
                  error={Boolean(fieldErrors.attendee_count)}
                  helperText={fieldErrors.attendee_count}
                  fullWidth
                />
              </Grid>
              <Grid item xs={12} md={4}>
                <TextField
                  label="Budżet"
                  type="number"
                  value={draft.budget_estimate}
                  onChange={(event) => updateDraft({ budget_estimate: Number(event.target.value) })}
                  error={Boolean(fieldErrors.budget_estimate)}
                  helperText={fieldErrors.budget_estimate}
                  fullWidth
                />
              </Grid>
              <Grid item xs={12} md={6}>
                <TextField
                  label="Start"
                  type="datetime-local"
                  value={formatDateInput(draft.planned_start)}
                  onChange={(event) => updateDraft({ planned_start: fromDateInput(event.target.value) })}
                  error={Boolean(fieldErrors.planned_start)}
                  helperText={fieldErrors.planned_start}
                  fullWidth
                  InputLabelProps={{ shrink: true }}
                />
              </Grid>
              <Grid item xs={12} md={6}>
                <TextField
                  label="Koniec"
                  type="datetime-local"
                  value={formatDateInput(draft.planned_end)}
                  onChange={(event) => updateDraft({ planned_end: fromDateInput(event.target.value) })}
                  error={Boolean(fieldErrors.planned_end)}
                  helperText={fieldErrors.planned_end}
                  fullWidth
                  InputLabelProps={{ shrink: true }}
                />
              </Grid>
            </Grid>
            {draft.requirements.length > 0 && (
              <Stack spacing={1}>
                <Typography fontWeight={800}>Wymagania wykryte z opisu</Typography>
                <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
                  {draft.requirements.map((requirement, index) => (
                    <Chip
                      key={index}
                      label={`${requirement.requirement_type}: ${requirement.quantity}`}
                      variant="outlined"
                    />
                  ))}
                </Stack>
              </Stack>
            )}
            <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
              <Button variant="outlined" onClick={validateDraft}>
                Sprawdź
              </Button>
              <Button variant="contained" color="success" disabled={!canAdd || isLoading} onClick={() => void commit()}>
                Dodaj
              </Button>
              <Button variant="text" color="warning" onClick={() => { setDraft(null); setFieldErrors({}); setSource(null); }}>
                Odrzuć
              </Button>
            </Stack>
          </Stack>
        </Paper>
      )}
    </Stack>
  );
}
