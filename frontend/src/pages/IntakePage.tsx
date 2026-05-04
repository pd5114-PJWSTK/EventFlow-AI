import { useMemo, useState } from "react";
import { Alert, Box, Button, Chip, Grid, Paper, Stack, TextField, Typography } from "@mui/material";

import { StatusBanner } from "../components/StatusBanner";
import { useAuth } from "../lib/auth";
import { formatDateInput, fromDateInput, parserSourceLabel } from "../lib/format";
import { useSessionState } from "../lib/useSessionState";
import { validateBusinessText, validateCity, validateNonNegativeNumber } from "../lib/validation";
import type { EventDraft, IntakeCommitResponse, IntakePreviewResponse } from "../types/api";

const EMPTY_TEXT = `Executive product launch for ACME in Gdansk at Amber Expo on 2026-07-20 from 09:00 to 18:00 for 420 attendees, budget 85000 PLN. Need two coordinators, one audio technician, LED screens and one van.`;

const requiredFields: Array<{ key: keyof EventDraft; label: string }> = [
  { key: "event_name", label: "Event name" },
  { key: "client_name", label: "Client" },
  { key: "location_name", label: "Venue" },
  { key: "city", label: "City" },
  { key: "event_type", label: "Event type" },
  { key: "planned_start", label: "Start" },
  { key: "planned_end", label: "End" },
];

export function IntakePage(): JSX.Element {
  const { api } = useAuth();
  const [rawInput, setRawInput] = useSessionState("cp05.intake.rawInput", EMPTY_TEXT);
  const [draft, setDraft] = useSessionState<EventDraft | null>("cp05.intake.draft", null);
  const [source, setSource] = useSessionState<string | null>("cp05.intake.source", null);
  const [assumptions, setAssumptions] = useSessionState<string[]>("cp05.intake.assumptions", []);
  const [fieldErrors, setFieldErrors] = useSessionState<Record<string, string>>("cp05.intake.errors", {});
  const [success, setSuccess] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const hasDraft = Boolean(draft);
  const canAdd = hasDraft && Object.keys(fieldErrors).length === 0;

  const resetFlow = (message?: string): void => {
    setDraft(null);
    setRawInput(EMPTY_TEXT);
    setFieldErrors({});
    setAssumptions([]);
    setSource(null);
    if (message) setSuccess(message);
  };

  const updateDraft = (patch: Partial<EventDraft>): void => setDraft((current) => (current ? { ...current, ...patch } : current));

  const validateDraft = (): boolean => {
    if (!draft) {
      setFieldErrors({ form: "Enter an event description first." });
      return false;
    }
    const nextErrors: Record<string, string> = {};
    for (const field of requiredFields) {
      const value = draft[field.key];
      if (value === undefined || value === null || String(value).trim() === "") nextErrors[field.key] = `Fill in: ${field.label}.`;
    }
    const checks = [
      ["event_name", validateBusinessText(draft.event_name, "Event name")],
      ["client_name", validateBusinessText(draft.client_name, "Client")],
      ["location_name", validateBusinessText(draft.location_name, "Venue")],
      ["city", validateCity(draft.city)],
      ["event_type", validateBusinessText(draft.event_type, "Event type")],
      ["attendee_count", validateNonNegativeNumber(draft.attendee_count, "Attendee count", true)],
      ["budget_estimate", validateNonNegativeNumber(draft.budget_estimate, "Budget")],
    ] as const;
    for (const [key, validationError] of checks) if (validationError) nextErrors[key] = validationError;
    if (draft.planned_start && draft.planned_end && new Date(draft.planned_end) <= new Date(draft.planned_start)) nextErrors.planned_end = "End must be after event start.";
    setFieldErrors(nextErrors);
    return Object.keys(nextErrors).length === 0;
  };

  const preview = async (): Promise<void> => {
    setError(null);
    setSuccess(null);
    setIsLoading(true);
    try {
      const data = await api.request<IntakePreviewResponse>("POST", "/api/ai-agents/ingest-event/preview", { raw_input: rawInput, prefer_langgraph: true });
      setDraft(data.draft);
      setAssumptions(data.assumptions);
      setSource(parserSourceLabel(data.parser_mode, data.used_fallback));
      setFieldErrors(Object.fromEntries(data.gaps.filter((gap) => gap.severity === "critical").map((gap) => [gap.field, gap.message])));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not prepare the event sheet.");
    } finally {
      setIsLoading(false);
    }
  };

  const commit = async (): Promise<void> => {
    if (!validateDraft() || !draft) return;
    setError(null);
    setIsLoading(true);
    try {
      const data = await api.request<IntakeCommitResponse>("POST", "/api/ai-agents/ingest-event/commit", {
        draft,
        assumptions,
        parser_mode: source?.includes("LLM") ? "llm" : "manual_commit",
        used_fallback: source?.includes("fallback") ?? false,
      });
      resetFlow(`Event saved. Business reference: EVT-${data.event_id.slice(0, 8).toUpperCase()}.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save the event.");
    } finally {
      setIsLoading(false);
    }
  };

  const requiredErrorCount = useMemo(() => Object.keys(fieldErrors).filter((key) => key !== "form").length, [fieldErrors]);

  return (
    <Stack spacing={2.5}>
      <Typography variant="h4">New event</Typography>
      {success && <StatusBanner severity="success" title="Event saved" message={success} />}
      {error && <Alert severity="error">{error}</Alert>}
      {!draft && (
        <Paper variant="outlined" sx={{ p: 3, borderRadius: 2 }}>
          <Stack spacing={2}>
            <TextField label="Event description" multiline minRows={8} value={rawInput} onChange={(event) => setRawInput(event.target.value)} fullWidth />
            <Box><Button variant="contained" onClick={() => void preview()} disabled={isLoading || rawInput.trim().length === 0}>Import</Button></Box>
          </Stack>
        </Paper>
      )}
      {draft && (
        <Paper variant="outlined" sx={{ p: 3, borderRadius: 2 }}>
          <Stack spacing={2.5}>
            <Stack direction={{ xs: "column", sm: "row" }} spacing={1} alignItems={{ xs: "flex-start", sm: "center" }}>
              <Typography variant="h6">Event sheet</Typography>
              {source && <Chip label={source} color={source.includes("LLM") ? "success" : "warning"} variant="outlined" />}
              {requiredErrorCount > 0 && <Chip label={`Missing: ${requiredErrorCount}`} color="error" />}
            </Stack>
            {fieldErrors.form && <Alert severity="warning">{fieldErrors.form}</Alert>}
            <Grid container spacing={2}>
              <Grid item xs={12} md={6}><TextField label="Event name" value={draft.event_name} onChange={(event) => updateDraft({ event_name: event.target.value })} error={Boolean(fieldErrors.event_name)} helperText={fieldErrors.event_name} fullWidth /></Grid>
              <Grid item xs={12} md={6}><TextField label="Client" value={draft.client_name} onChange={(event) => updateDraft({ client_name: event.target.value })} error={Boolean(fieldErrors.client_name)} helperText={fieldErrors.client_name} fullWidth /></Grid>
              <Grid item xs={12} md={6}><TextField label="Venue" value={draft.location_name} onChange={(event) => updateDraft({ location_name: event.target.value })} error={Boolean(fieldErrors.location_name)} helperText={fieldErrors.location_name} fullWidth /></Grid>
              <Grid item xs={12} md={6}><TextField label="City" value={draft.city} onChange={(event) => updateDraft({ city: event.target.value })} error={Boolean(fieldErrors.city)} helperText={fieldErrors.city} fullWidth /></Grid>
              <Grid item xs={12} md={4}><TextField label="Event type" value={draft.event_type} onChange={(event) => updateDraft({ event_type: event.target.value })} error={Boolean(fieldErrors.event_type)} helperText={fieldErrors.event_type} fullWidth /></Grid>
              <Grid item xs={12} md={4}><TextField label="Attendee count" type="number" value={draft.attendee_count} onChange={(event) => updateDraft({ attendee_count: Number(event.target.value) })} error={Boolean(fieldErrors.attendee_count)} helperText={fieldErrors.attendee_count} fullWidth /></Grid>
              <Grid item xs={12} md={4}><TextField label="Budget" type="number" value={draft.budget_estimate} onChange={(event) => updateDraft({ budget_estimate: Number(event.target.value) })} error={Boolean(fieldErrors.budget_estimate)} helperText={fieldErrors.budget_estimate} fullWidth /></Grid>
              <Grid item xs={12} md={6}><TextField label="Start" type="datetime-local" value={formatDateInput(draft.planned_start)} onChange={(event) => updateDraft({ planned_start: fromDateInput(event.target.value) })} error={Boolean(fieldErrors.planned_start)} helperText={fieldErrors.planned_start} fullWidth InputLabelProps={{ shrink: true }} /></Grid>
              <Grid item xs={12} md={6}><TextField label="End" type="datetime-local" value={formatDateInput(draft.planned_end)} onChange={(event) => updateDraft({ planned_end: fromDateInput(event.target.value) })} error={Boolean(fieldErrors.planned_end)} helperText={fieldErrors.planned_end} fullWidth InputLabelProps={{ shrink: true }} /></Grid>
            </Grid>
            {draft.requirements.length > 0 && (
              <Stack spacing={1}>
                <Typography fontWeight={800}>Requirements detected from the description</Typography>
                <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>{draft.requirements.map((requirement, index) => <Chip key={index} label={`${requirement.requirement_type.replace(/_/g, " ")}: ${requirement.quantity}`} variant="outlined" />)}</Stack>
              </Stack>
            )}
            <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
              <Button variant="outlined" onClick={validateDraft}>Check</Button>
              <Button variant="contained" color="success" disabled={!canAdd || isLoading} onClick={() => void commit()}>Add</Button>
              <Button variant="outlined" onClick={() => setDraft(null)}>Back</Button>
              <Button variant="text" color="warning" onClick={() => resetFlow()}>Reject</Button>
            </Stack>
          </Stack>
        </Paper>
      )}
    </Stack>
  );
}
