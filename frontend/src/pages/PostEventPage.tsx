import { useState } from "react";
import { Alert, Box, Button, Chip, Grid, Paper, Stack, TextField, Typography } from "@mui/material";

import { EventSelect } from "../components/EventSelect";
import { StatusBanner } from "../components/StatusBanner";
import { useAuth } from "../lib/auth";
import { formatDateInput, fromDateInput, parserSourceLabel } from "../lib/format";
import { useSessionState } from "../lib/useSessionState";
import { validateNonNegativeNumber, validateScore } from "../lib/validation";
import type { PostEventParseResponse } from "../types/api";

interface CompletionSheet { completed_at: string; finished_on_time: boolean; total_delay_minutes: number; actual_cost: string; sla_breached: boolean; client_satisfaction_score: string; internal_quality_score: string; summary_notes: string; }

const DEFAULT_SUMMARY = "Event finished on time. Actual cost 22000 PLN. Client was satisfied. No SLA breach.";

export function PostEventPage(): JSX.Element {
  const { api } = useAuth();
  const [eventId, setEventId] = useSessionState("cp05.post.eventId", "");
  const [summaryText, setSummaryText] = useSessionState("cp05.post.summary", DEFAULT_SUMMARY);
  const [sheet, setSheet] = useSessionState<CompletionSheet | null>("cp05.post.sheet", null);
  const [source, setSource] = useSessionState<string | null>("cp05.post.source", null);
  const [gaps, setGaps] = useSessionState<string[]>("cp05.post.gaps", []);
  const [fieldErrors, setFieldErrors] = useSessionState<Record<string, string>>("cp05.post.errors", {});
  const [success, setSuccess] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const resetFlow = (message?: string): void => { setEventId(""); setSummaryText(DEFAULT_SUMMARY); setSheet(null); setSource(null); setGaps([]); setFieldErrors({}); if (message) setSuccess(message); };

  const validateSheet = (): boolean => {
    const next: Record<string, string> = {};
    if (!eventId.trim()) next.eventId = "Select an event.";
    if (!sheet?.completed_at) next.completed_at = "Completion date is required.";
    if (!sheet?.summary_notes?.trim()) next.summary_notes = "Summary is required.";
    if (sheet) {
      const delayError = validateNonNegativeNumber(sheet.total_delay_minutes, "Delay", true); if (delayError) next.total_delay_minutes = delayError;
      const costError = validateNonNegativeNumber(sheet.actual_cost, "Actual cost"); if (costError) next.actual_cost = costError;
      const clientScoreError = validateScore(sheet.client_satisfaction_score, "Client score"); if (clientScoreError) next.client_satisfaction_score = clientScoreError;
      const internalScoreError = validateScore(sheet.internal_quality_score, "Internal score"); if (internalScoreError) next.internal_quality_score = internalScoreError;
    }
    setFieldErrors(next);
    return Object.keys(next).length === 0;
  };

  const parseSummary = async (): Promise<void> => {
    setError(null); setSuccess(null);
    if (!eventId.trim()) { setFieldErrors({ eventId: "Select an event." }); return; }
    setIsLoading(true);
    try {
      const data = await api.request<PostEventParseResponse>("POST", `/api/runtime/events/${eventId}/post-event/parse`, { raw_summary: summaryText, prefer_llm: true, idempotency_key: `post-parse-${Date.now()}` });
      const draft = data.draft_complete;
      setSheet({ completed_at: String(draft.completed_at ?? new Date().toISOString()), finished_on_time: Boolean(draft.finished_on_time ?? true), total_delay_minutes: Number(draft.total_delay_minutes ?? 0), actual_cost: String(draft.actual_cost ?? ""), sla_breached: Boolean(draft.sla_breached ?? false), client_satisfaction_score: String(draft.client_satisfaction_score ?? ""), internal_quality_score: String(draft.internal_quality_score ?? ""), summary_notes: String(draft.summary_notes ?? summaryText) });
      setSource(parserSourceLabel(data.parser_mode, data.parser_mode === "heuristic"));
      setGaps(data.gaps);
      setFieldErrors({});
    } catch (err) { setError(err instanceof Error ? err.message : "Could not parse the post-event log."); } finally { setIsLoading(false); }
  };

  const commitSummary = async (): Promise<void> => {
    if (!validateSheet() || !sheet) return;
    setError(null); setIsLoading(true);
    try {
      await api.request("POST", `/api/runtime/events/${eventId}/post-event/commit`, { completion: { completed_at: sheet.completed_at, finished_on_time: sheet.finished_on_time, total_delay_minutes: sheet.total_delay_minutes, actual_cost: sheet.actual_cost ? Number(sheet.actual_cost) : null, sla_breached: sheet.sla_breached, client_satisfaction_score: sheet.client_satisfaction_score ? Number(sheet.client_satisfaction_score) : null, internal_quality_score: sheet.internal_quality_score ? Number(sheet.internal_quality_score) : null, summary_notes: sheet.summary_notes }, source_mode: "sheet_review", idempotency_key: `post-commit-${Date.now()}` });
      resetFlow("The post-event log was saved and the view has been reset.");
    } catch (err) { setError(err instanceof Error ? err.message : "Could not save the post-event log."); } finally { setIsLoading(false); }
  };

  return (
    <Stack spacing={2.5}>
      <Typography variant="h4">Post-event log</Typography>
      {success && <StatusBanner severity="success" title="Log saved" message={success} />}
      {error && <Alert severity="error">{error}</Alert>}
      {!sheet && <Paper variant="outlined" sx={{ p: 3, borderRadius: 2 }}><Stack spacing={2}><EventSelect label="Event to close" value={eventId} onChange={setEventId} scope="post-event" error={Boolean(fieldErrors.eventId)} helperText={fieldErrors.eventId} /><TextField label="Post-event summary" multiline minRows={7} value={summaryText} onChange={(event) => setSummaryText(event.target.value)} fullWidth /><Box><Button variant="contained" disabled={!eventId || isLoading} onClick={() => void parseSummary()}>Import</Button></Box></Stack></Paper>}
      {sheet && <Paper variant="outlined" sx={{ p: 3, borderRadius: 2 }}><Stack spacing={2}><Stack direction="row" spacing={1} alignItems="center"><Typography variant="h6">Completion sheet</Typography>{source && <Chip label={source} variant="outlined" color={source.includes("LLM") ? "success" : "warning"} />}</Stack>{gaps.length > 0 && <Alert severity="warning">Missing details detected: {gaps.join(" ")}</Alert>}<Grid container spacing={2}><Grid item xs={12} md={6}><TextField label="Completed at" type="datetime-local" value={formatDateInput(sheet.completed_at)} onChange={(event) => setSheet({ ...sheet, completed_at: fromDateInput(event.target.value) })} error={Boolean(fieldErrors.completed_at)} helperText={fieldErrors.completed_at} fullWidth InputLabelProps={{ shrink: true }} /></Grid><Grid item xs={12} md={6}><TextField label="Delay (minutes)" type="number" value={sheet.total_delay_minutes} onChange={(event) => setSheet({ ...sheet, total_delay_minutes: Number(event.target.value) })} error={Boolean(fieldErrors.total_delay_minutes)} helperText={fieldErrors.total_delay_minutes} fullWidth /></Grid><Grid item xs={12} md={4}><TextField label="Actual cost" value={sheet.actual_cost} onChange={(event) => setSheet({ ...sheet, actual_cost: event.target.value })} error={Boolean(fieldErrors.actual_cost)} helperText={fieldErrors.actual_cost} fullWidth /></Grid><Grid item xs={12} md={4}><TextField label="Client score" value={sheet.client_satisfaction_score} onChange={(event) => setSheet({ ...sheet, client_satisfaction_score: event.target.value })} error={Boolean(fieldErrors.client_satisfaction_score)} helperText={fieldErrors.client_satisfaction_score} fullWidth /></Grid><Grid item xs={12} md={4}><TextField label="Internal score" value={sheet.internal_quality_score} onChange={(event) => setSheet({ ...sheet, internal_quality_score: event.target.value })} error={Boolean(fieldErrors.internal_quality_score)} helperText={fieldErrors.internal_quality_score} fullWidth /></Grid><Grid item xs={12}><TextField label="Summary" multiline minRows={4} value={sheet.summary_notes} onChange={(event) => setSheet({ ...sheet, summary_notes: event.target.value })} error={Boolean(fieldErrors.summary_notes)} helperText={fieldErrors.summary_notes} fullWidth /></Grid></Grid><Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap><Button variant="outlined" onClick={validateSheet}>Check</Button><Button variant="contained" color="success" disabled={isLoading || Object.keys(fieldErrors).length > 0} onClick={() => void commitSummary()}>Save</Button><Button variant="outlined" onClick={() => setSheet(null)}>Back</Button><Button variant="text" color="warning" onClick={() => resetFlow()}>Reject</Button></Stack></Stack></Paper>}
    </Stack>
  );
}
