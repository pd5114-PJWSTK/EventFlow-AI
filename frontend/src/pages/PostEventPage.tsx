import { useState } from "react";
import { Alert, Box, Button, Chip, Grid, Paper, Stack, TextField, Typography } from "@mui/material";

import { StatusBanner } from "../components/StatusBanner";
import { useAuth } from "../lib/auth";
import { formatDateInput, fromDateInput, parserSourceLabel } from "../lib/format";
import type { PostEventParseResponse } from "../types/api";

interface CompletionSheet {
  completed_at: string;
  finished_on_time: boolean;
  total_delay_minutes: number;
  actual_cost: string;
  sla_breached: boolean;
  client_satisfaction_score: string;
  internal_quality_score: string;
  summary_notes: string;
}

export function PostEventPage(): JSX.Element {
  const { api } = useAuth();
  const [eventId, setEventId] = useState("");
  const [summaryText, setSummaryText] = useState("Event zakończony na czas, koszt 22000 PLN, klient zadowolony, bez naruszenia SLA.");
  const [sheet, setSheet] = useState<CompletionSheet | null>(null);
  const [source, setSource] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [success, setSuccess] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const validateSheet = (): boolean => {
    const next: Record<string, string> = {};
    if (!eventId.trim()) next.eventId = "Event jest wymagany.";
    if (!sheet?.completed_at) next.completed_at = "Data zakończenia jest wymagana.";
    if (!sheet?.summary_notes?.trim()) next.summary_notes = "Podsumowanie jest wymagane.";
    setFieldErrors(next);
    return Object.keys(next).length === 0;
  };

  const parseSummary = async (): Promise<void> => {
    setError(null);
    setSuccess(null);
    setIsLoading(true);
    try {
      const data = await api.request<PostEventParseResponse>("POST", `/api/runtime/events/${eventId}/post-event/parse`, {
        raw_summary: summaryText,
        prefer_llm: true,
        idempotency_key: `post-parse-${Date.now()}`,
      });
      const draft = data.draft_complete;
      setSheet({
        completed_at: String(draft.completed_at ?? new Date().toISOString()),
        finished_on_time: Boolean(draft.finished_on_time ?? true),
        total_delay_minutes: Number(draft.total_delay_minutes ?? 0),
        actual_cost: String(draft.actual_cost ?? ""),
        sla_breached: Boolean(draft.sla_breached ?? false),
        client_satisfaction_score: String(draft.client_satisfaction_score ?? ""),
        internal_quality_score: String(draft.internal_quality_score ?? ""),
        summary_notes: String(draft.summary_notes ?? summaryText),
      });
      setSource(parserSourceLabel(data.parser_mode, data.parser_mode === "heuristic"));
      setFieldErrors(Object.fromEntries(data.gaps.map((gap) => [gap, gap])));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Nie udało się przetworzyć logu po evencie.");
    } finally {
      setIsLoading(false);
    }
  };

  const commitSummary = async (): Promise<void> => {
    if (!validateSheet() || !sheet) return;
    setError(null);
    setIsLoading(true);
    try {
      await api.request("POST", `/api/runtime/events/${eventId}/post-event/commit`, {
        completion: {
          completed_at: sheet.completed_at,
          finished_on_time: sheet.finished_on_time,
          total_delay_minutes: sheet.total_delay_minutes,
          actual_cost: sheet.actual_cost ? Number(sheet.actual_cost) : null,
          sla_breached: sheet.sla_breached,
          client_satisfaction_score: sheet.client_satisfaction_score ? Number(sheet.client_satisfaction_score) : null,
          internal_quality_score: sheet.internal_quality_score ? Number(sheet.internal_quality_score) : null,
          summary_notes: sheet.summary_notes,
        },
        source_mode: "sheet_review",
        idempotency_key: `post-commit-${Date.now()}`,
      });
      setSuccess("Log po evencie został wprowadzony.");
      setSheet(null);
      setSummaryText("Event zakończony na czas, koszt 22000 PLN, klient zadowolony, bez naruszenia SLA.");
      setSource(null);
      setFieldErrors({});
    } catch (err) {
      setError(err instanceof Error ? err.message : "Nie udało się zapisać logu po evencie.");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <Stack spacing={2.5}>
      <Typography variant="h4">Post-event log</Typography>
      {success && <StatusBanner severity="success" title="Log zapisany" message={success} />}
      {error && <Alert severity="error">{error}</Alert>}
      {!sheet && (
        <Paper variant="outlined" sx={{ p: 3, borderRadius: 2 }}>
          <Stack spacing={2}>
            <TextField label="Event ID" value={eventId} onChange={(event) => setEventId(event.target.value)} error={Boolean(fieldErrors.eventId)} helperText={fieldErrors.eventId} />
            <TextField label="Opis po evencie" multiline minRows={7} value={summaryText} onChange={(event) => setSummaryText(event.target.value)} fullWidth />
            <Box>
              <Button variant="contained" disabled={!eventId || isLoading} onClick={() => void parseSummary()}>
                Wprowadź
              </Button>
            </Box>
          </Stack>
        </Paper>
      )}
      {sheet && (
        <Paper variant="outlined" sx={{ p: 3, borderRadius: 2 }}>
          <Stack spacing={2}>
            <Stack direction="row" spacing={1} alignItems="center">
              <Typography variant="h6">Arkusz podsumowania</Typography>
              {source && <Chip label={source} variant="outlined" color={source.includes("LLM") ? "success" : "warning"} />}
            </Stack>
            <Grid container spacing={2}>
              <Grid item xs={12} md={6}>
                <TextField label="Zakończono" type="datetime-local" value={formatDateInput(sheet.completed_at)} onChange={(event) => setSheet({ ...sheet, completed_at: fromDateInput(event.target.value) })} error={Boolean(fieldErrors.completed_at)} helperText={fieldErrors.completed_at} fullWidth InputLabelProps={{ shrink: true }} />
              </Grid>
              <Grid item xs={12} md={6}>
                <TextField label="Opóźnienie (min)" type="number" value={sheet.total_delay_minutes} onChange={(event) => setSheet({ ...sheet, total_delay_minutes: Number(event.target.value) })} fullWidth />
              </Grid>
              <Grid item xs={12} md={4}><TextField label="Koszt rzeczywisty" value={sheet.actual_cost} onChange={(event) => setSheet({ ...sheet, actual_cost: event.target.value })} fullWidth /></Grid>
              <Grid item xs={12} md={4}><TextField label="Ocena klienta" value={sheet.client_satisfaction_score} onChange={(event) => setSheet({ ...sheet, client_satisfaction_score: event.target.value })} fullWidth /></Grid>
              <Grid item xs={12} md={4}><TextField label="Ocena wewnętrzna" value={sheet.internal_quality_score} onChange={(event) => setSheet({ ...sheet, internal_quality_score: event.target.value })} fullWidth /></Grid>
              <Grid item xs={12}><TextField label="Podsumowanie" multiline minRows={4} value={sheet.summary_notes} onChange={(event) => setSheet({ ...sheet, summary_notes: event.target.value })} error={Boolean(fieldErrors.summary_notes)} helperText={fieldErrors.summary_notes} fullWidth /></Grid>
            </Grid>
            <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
              <Button variant="outlined" onClick={validateSheet}>Sprawdź</Button>
              <Button variant="contained" color="success" disabled={isLoading || Object.keys(fieldErrors).length > 0} onClick={() => void commitSummary()}>Wprowadź</Button>
              <Button variant="text" color="warning" onClick={() => { setSheet(null); setFieldErrors({}); setSource(null); }}>Odrzuć</Button>
            </Stack>
          </Stack>
        </Paper>
      )}
    </Stack>
  );
}
