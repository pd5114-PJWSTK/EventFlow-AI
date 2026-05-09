import { useState } from "react";
import { Alert, Box, Button, Chip, Grid, MenuItem, Paper, Stack, TextField, Typography } from "@mui/material";

import { BackCornerButton } from "../components/BackCornerButton";
import { EventDetailsCard } from "../components/EventDetailsCard";
import { EventSelect } from "../components/EventSelect";
import { StatusBanner } from "../components/StatusBanner";
import { useAuth } from "../lib/auth";
import { formatDateInput, fromDateInput, parserSourceLabel } from "../lib/format";
import { useSessionState } from "../lib/useSessionState";
import { validateNonNegativeNumber, validateScore } from "../lib/validation";
import type { PostEventParseResponse } from "../types/api";

interface CompletionSheet { completed_at: string; finished_on_time: boolean; total_delay_minutes: string; actual_cost: string; sla_breached: boolean; client_satisfaction_score: string; internal_quality_score: string; summary_notes: string; }

const DEFAULT_SUMMARY = "Event finished with a 12 minute delay caused by extended soundcheck. Actual cost was 22450 PLN. No SLA breach. Client satisfaction score 5/5, internal quality score 4/5. The team should reserve a backup audio interface for similar music events.";
const scoreOptions = ["1", "2", "3", "4", "5"];

function normalizeScore(value: unknown): string {
  const numeric = Number(value);
  if (Number.isNaN(numeric)) return "";
  return String(Math.min(5, Math.max(1, Math.round(numeric))));
}

export function PostEventPage(): JSX.Element {
  const { api } = useAuth();
  const [eventId, setEventId] = useSessionState("cp05.post.eventId", "");
  const [summaryText, setSummaryText] = useSessionState("cp05.post.summary", DEFAULT_SUMMARY);
  const [sheet, setSheet] = useSessionState<CompletionSheet | null>("cp05.post.sheet", null);
  const [source, setSource] = useSessionState<string | null>("cp05.post.source", null);
  const [gaps, setGaps] = useSessionState<string[]>("cp05.post.gaps", []);
  const [fieldErrors, setFieldErrors] = useSessionState<Record<string, string>>("cp05.post.errors", {});
  const [checked, setChecked] = useSessionState("cp06.post.checked", false);
  const [success, setSuccess] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const resetFlow = (message?: string): void => { setEventId(""); setSummaryText(DEFAULT_SUMMARY); setSheet(null); setSource(null); setGaps([]); setFieldErrors({}); setChecked(false); if (message) setSuccess(message); };
  const handleEventChange = (nextEventId: string): void => {
    setEventId(nextEventId);
    setSheet(null);
    setSource(null);
    setGaps([]);
    setFieldErrors({});
    setChecked(false);
    setError(null);
    setSuccess(null);
  };
  const updateSheet = (patch: Partial<CompletionSheet>): void => {
    setChecked(false);
    setSheet((current) => current ? { ...current, ...patch } : current);
  };

  const validateSheet = (): boolean => {
    const next: Record<string, string> = {};
    if (!eventId.trim()) next.eventId = "Select an event.";
    if (!sheet?.completed_at) next.completed_at = "Completion date is required.";
    if (!sheet?.summary_notes?.trim()) next.summary_notes = "Summary is required.";
    if (sheet) {
      const delayError = validateNonNegativeNumber(sheet.total_delay_minutes, "Delay", true); if (delayError) next.total_delay_minutes = delayError;
      const costError = validateNonNegativeNumber(sheet.actual_cost, "Actual cost", true); if (costError) next.actual_cost = costError;
      if (!String(sheet.client_satisfaction_score ?? "").trim()) next.client_satisfaction_score = "Client score is required.";
      else {
        const clientScoreError = validateScore(sheet.client_satisfaction_score, "Client score"); if (clientScoreError) next.client_satisfaction_score = clientScoreError;
      }
      if (!String(sheet.internal_quality_score ?? "").trim()) next.internal_quality_score = "Internal score is required.";
      else {
        const internalScoreError = validateScore(sheet.internal_quality_score, "Internal score"); if (internalScoreError) next.internal_quality_score = internalScoreError;
      }
    }
    setFieldErrors(next);
    const isValid = Object.keys(next).length === 0;
    setChecked(isValid);
    return isValid;
  };

  const parseSummary = async (): Promise<void> => {
    setError(null); setSuccess(null);
    if (!eventId.trim()) { setFieldErrors({ eventId: "Select an event." }); return; }
    setIsLoading(true);
    try {
      const data = await api.request<PostEventParseResponse>("POST", `/api/runtime/events/${eventId}/post-event/parse`, { raw_summary: summaryText, prefer_llm: true, idempotency_key: `post-parse-${Date.now()}` });
      const draft = data.draft_complete;
      setSheet({ completed_at: String(draft.completed_at ?? new Date().toISOString()), finished_on_time: Boolean(draft.finished_on_time ?? true), total_delay_minutes: draft.total_delay_minutes === undefined || draft.total_delay_minutes === null ? "" : String(draft.total_delay_minutes), actual_cost: String(draft.actual_cost ?? ""), sla_breached: Boolean(draft.sla_breached ?? false), client_satisfaction_score: normalizeScore(draft.client_satisfaction_score), internal_quality_score: normalizeScore(draft.internal_quality_score), summary_notes: String(draft.summary_notes ?? summaryText) });
      setSource(parserSourceLabel(data.parser_mode, data.parser_mode === "heuristic"));
      setGaps(data.gaps);
      setFieldErrors({});
      setChecked(false);
    } catch (err) { setError(err instanceof Error ? err.message : "Could not parse the post-event log."); } finally { setIsLoading(false); }
  };

  const commitSummary = async (): Promise<void> => {
    if (!validateSheet() || !sheet) return;
    setError(null); setIsLoading(true);
    try {
      await api.request("POST", `/api/runtime/events/${eventId}/post-event/commit`, { completion: { completed_at: sheet.completed_at, finished_on_time: sheet.finished_on_time, total_delay_minutes: Number(sheet.total_delay_minutes), actual_cost: Number(sheet.actual_cost), sla_breached: sheet.sla_breached, client_satisfaction_score: Number(sheet.client_satisfaction_score), internal_quality_score: Number(sheet.internal_quality_score), summary_notes: sheet.summary_notes }, source_mode: "sheet_review", idempotency_key: `post-commit-${Date.now()}` });
      resetFlow("The post-event log was saved and the view has been reset.");
    } catch (err) { setError(err instanceof Error ? err.message : "Could not save the post-event log."); } finally { setIsLoading(false); }
  };

  return (
    <Stack spacing={2.5}>
      <Typography variant="h4">Post-event log</Typography>
      {success && <StatusBanner severity="success" title="Log saved" message={success} />}
      {error && <Alert severity="error">{error}</Alert>}
      {!sheet && <Paper variant="outlined" sx={{ p: 3, borderRadius: 2 }}><Stack spacing={2}><EventSelect label="Completed event to log" value={eventId} onChange={handleEventChange} scope="post-event" error={Boolean(fieldErrors.eventId)} helperText={fieldErrors.eventId} />{eventId && <EventDetailsCard eventId={eventId} title="Completed event context" />}<TextField label="Post-event summary" placeholder="Summarize what happened after completion: final timing, exact delay in minutes, actual cost, SLA result, client satisfaction score from 1 to 5, internal quality score from 1 to 5 and any issue worth feeding into model training." multiline minRows={7} value={summaryText} onChange={(event) => setSummaryText(event.target.value)} helperText="The parser will prepare a completion sheet. Missing delay or quality scores must be filled before saving." fullWidth /><Box><Button variant="contained" disabled={!eventId || isLoading} onClick={() => void parseSummary()}>Import</Button></Box></Stack></Paper>}
      {sheet && <Paper variant="outlined" sx={{ p: 3, borderRadius: 2, position: "relative" }}><Stack spacing={2}><BackCornerButton onClick={() => setSheet(null)} /><Stack direction="row" spacing={1} alignItems="center"><Typography variant="h6">Completion sheet</Typography>{source && <Chip label={source} variant="outlined" color={source.includes("LLM") ? "success" : "warning"} />}</Stack>{gaps.length > 0 && <Alert severity="warning">Missing details detected. Fill the highlighted fields before saving: {gaps.join(" ")}</Alert>}<Grid container spacing={2}><Grid item xs={12} md={6}><TextField label="Completed at" type="datetime-local" value={formatDateInput(sheet.completed_at)} onChange={(event) => updateSheet({ completed_at: fromDateInput(event.target.value) })} error={Boolean(fieldErrors.completed_at)} helperText={fieldErrors.completed_at} fullWidth InputLabelProps={{ shrink: true }} /></Grid><Grid item xs={12} md={6}><TextField label="Delay (minutes)" type="number" value={sheet.total_delay_minutes} onChange={(event) => updateSheet({ total_delay_minutes: event.target.value })} error={Boolean(fieldErrors.total_delay_minutes)} helperText={fieldErrors.total_delay_minutes || "Use 0 only when the event finished without operational delay."} fullWidth /></Grid><Grid item xs={12} md={4}><TextField label="Actual cost" placeholder="Final cost in PLN after staff, equipment, transport and incident changes." value={sheet.actual_cost} onChange={(event) => updateSheet({ actual_cost: event.target.value })} error={Boolean(fieldErrors.actual_cost)} helperText={fieldErrors.actual_cost} fullWidth /></Grid><Grid item xs={12} md={4}><TextField select label="Client score" value={sheet.client_satisfaction_score} onChange={(event) => updateSheet({ client_satisfaction_score: event.target.value })} error={Boolean(fieldErrors.client_satisfaction_score)} helperText={fieldErrors.client_satisfaction_score || "1 means poor, 5 means excellent."} fullWidth>{scoreOptions.map((score) => <MenuItem key={score} value={score}>{score}</MenuItem>)}</TextField></Grid><Grid item xs={12} md={4}><TextField select label="Internal score" value={sheet.internal_quality_score} onChange={(event) => updateSheet({ internal_quality_score: event.target.value })} error={Boolean(fieldErrors.internal_quality_score)} helperText={fieldErrors.internal_quality_score || "Rate internal execution quality from 1 to 5."} fullWidth>{scoreOptions.map((score) => <MenuItem key={score} value={score}>{score}</MenuItem>)}</TextField></Grid><Grid item xs={12}><TextField label="Summary" placeholder="Write the final operational conclusion in business language. Include what went well, what failed, and what should affect future planning." multiline minRows={4} value={sheet.summary_notes} onChange={(event) => updateSheet({ summary_notes: event.target.value })} error={Boolean(fieldErrors.summary_notes)} helperText={fieldErrors.summary_notes} fullWidth /></Grid></Grid><Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap><Button variant="outlined" onClick={validateSheet}>Check</Button><Button variant="contained" color="success" disabled={isLoading || !checked || Object.keys(fieldErrors).length > 0} onClick={() => void commitSummary()}>Save</Button><Button variant="text" color="warning" onClick={() => resetFlow()}>Reject</Button></Stack></Stack></Paper>}
    </Stack>
  );
}
