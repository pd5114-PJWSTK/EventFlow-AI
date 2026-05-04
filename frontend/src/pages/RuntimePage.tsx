import { useState } from "react";
import { Alert, Box, Button, Chip, Grid, Paper, Stack, TextField, Typography } from "@mui/material";

import { AnimatedPipeline } from "../components/AnimatedPipeline";
import { EventSelect } from "../components/EventSelect";
import { StatusBanner } from "../components/StatusBanner";
import { useAuth } from "../lib/auth";
import { formatMoney, parserSourceLabel } from "../lib/format";
import { useSessionState } from "../lib/useSessionState";
import { validateBusinessText, validateNonNegativeNumber } from "../lib/validation";
import type { ReplanResponse, RuntimeIncidentParseResponse } from "../types/api";

const replanSteps = ["Incident analysis", "Replanning", "Impact comparison", "Decision", "Approval"];

interface IncidentSheet { incident_id?: string; incident_type: string; severity: string; description: string; root_cause: string; reported_by: string; cost_impact: string; sla_impact: boolean; parser_mode?: string; parse_confidence?: number; }

export function RuntimePage(): JSX.Element {
  const { api } = useAuth();
  const [eventId, setEventId] = useSessionState("cp05.runtime.eventId", "");
  const [incidentText, setIncidentText] = useSessionState("cp05.runtime.text", "Audio system failure on the main stage, approximately 30 minutes delay, reported by Jan.");
  const [sheet, setSheet] = useSessionState<IncidentSheet | null>("cp05.runtime.sheet", null);
  const [fieldErrors, setFieldErrors] = useSessionState<Record<string, string>>("cp05.runtime.errors", {});
  const [replanResult, setReplanResult] = useSessionState<ReplanResponse | null>("cp05.runtime.replan", null);
  const [activeStep, setActiveStep] = useSessionState("cp05.runtime.step", 0);
  const [success, setSuccess] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isWorking, setIsWorking] = useState(false);

  const resetFlow = (message?: string): void => { setEventId(""); setIncidentText("Audio system failure on the main stage, approximately 30 minutes delay, reported by Jan."); setSheet(null); setFieldErrors({}); setReplanResult(null); setActiveStep(0); if (message) setSuccess(message); };

  const validateSheet = (): boolean => {
    const next: Record<string, string> = {};
    if (!eventId.trim()) next.eventId = "Select an event.";
    if (sheet) {
      const typeError = validateBusinessText(sheet.incident_type, "Incident type"); if (typeError) next.incident_type = typeError;
      const descriptionError = validateBusinessText(sheet.description, "Incident description"); if (descriptionError) next.description = descriptionError;
      const reporterError = sheet.reported_by ? validateBusinessText(sheet.reported_by, "Reporter") : null; if (reporterError) next.reported_by = reporterError;
      const costError = validateNonNegativeNumber(sheet.cost_impact, "Cost impact"); if (costError) next.cost_impact = costError;
    }
    setFieldErrors(next);
    return Object.keys(next).length === 0;
  };

  const parseIncident = async (): Promise<void> => {
    setError(null); setSuccess(null); setReplanResult(null);
    if (!eventId.trim()) { setFieldErrors({ eventId: "Select an event." }); return; }
    setIsWorking(true);
    try {
      const data = await api.request<RuntimeIncidentParseResponse>("POST", `/api/runtime/events/${eventId}/incident/parse`, { raw_log: incidentText, prefer_llm: true, idempotency_key: `incident-${Date.now()}` });
      setSheet({ incident_id: data.incident_id, incident_type: data.incident_type, severity: data.severity, description: data.description, root_cause: data.root_cause || "", reported_by: data.reported_by || "", cost_impact: data.cost_impact ? String(data.cost_impact) : "", sla_impact: data.sla_impact, parser_mode: data.parser_mode, parse_confidence: data.parse_confidence });
      setFieldErrors({});
    } catch (err) { setError(err instanceof Error ? err.message : "Could not parse the incident."); } finally { setIsWorking(false); }
  };

  const acceptIncidentAndReplan = async (): Promise<void> => {
    if (!validateSheet() || !sheet) return;
    setError(null); setSuccess("Incident accepted. Replanning is running."); setIsWorking(true);
    try {
      setActiveStep(1);
      const data = await api.request<ReplanResponse>("POST", `/api/planner/replan/${eventId}`, { incident_id: sheet.incident_id, incident_summary: sheet.description, commit_to_assignments: false, idempotency_key: `replan-${Date.now()}` });
      setReplanResult(data); setActiveStep(3);
    } catch (err) { setError(err instanceof Error ? err.message : "Could not run replanning."); } finally { setIsWorking(false); }
  };

  const acceptReplan = async (): Promise<void> => {
    if (!sheet) return;
    setError(null); setIsWorking(true);
    try {
      await api.request<ReplanResponse>("POST", `/api/planner/replan/${eventId}`, { incident_id: sheet.incident_id, incident_summary: sheet.description, commit_to_assignments: true, idempotency_key: `replan-accept-${Date.now()}` });
      setActiveStep(4); resetFlow("The replan was approved and saved. The live replanning view has been reset.");
    } catch (err) { setError(err instanceof Error ? err.message : "Could not approve the replan."); } finally { setIsWorking(false); }
  };

  return (
    <Stack spacing={2.5}>
      <Typography variant="h4">Live replanning</Typography>
      {success && <StatusBanner severity="success" title="Status" message={success} />}
      {error && <Alert severity="error">{error}</Alert>}
      {!sheet && <Paper variant="outlined" sx={{ p: 3, borderRadius: 2 }}><Stack spacing={2}><EventSelect label="Event for incident" value={eventId} onChange={setEventId} scope="runtime" error={Boolean(fieldErrors.eventId)} helperText={fieldErrors.eventId} /><TextField label="Incident description" multiline minRows={7} value={incidentText} onChange={(event) => setIncidentText(event.target.value)} fullWidth /><Box><Button variant="contained" disabled={!eventId || isWorking} onClick={() => void parseIncident()}>Import</Button></Box></Stack></Paper>}
      {sheet && !replanResult && <Paper variant="outlined" sx={{ p: 3, borderRadius: 2 }}><Stack spacing={2}><Stack direction="row" spacing={1} alignItems="center"><Typography variant="h6">Incident sheet</Typography><Chip label={parserSourceLabel(sheet.parser_mode)} variant="outlined" color={sheet.parser_mode === "llm" ? "success" : "warning"} /></Stack><Grid container spacing={2}><Grid item xs={12} md={4}><TextField label="Type" value={sheet.incident_type} onChange={(event) => setSheet({ ...sheet, incident_type: event.target.value })} error={Boolean(fieldErrors.incident_type)} helperText={fieldErrors.incident_type} fullWidth /></Grid><Grid item xs={12} md={4}><TextField label="Severity" value={sheet.severity} onChange={(event) => setSheet({ ...sheet, severity: event.target.value })} fullWidth /></Grid><Grid item xs={12} md={4}><TextField label="Reporter" value={sheet.reported_by} onChange={(event) => setSheet({ ...sheet, reported_by: event.target.value })} error={Boolean(fieldErrors.reported_by)} helperText={fieldErrors.reported_by} fullWidth /></Grid><Grid item xs={12}><TextField label="Description" multiline minRows={4} value={sheet.description} onChange={(event) => setSheet({ ...sheet, description: event.target.value })} error={Boolean(fieldErrors.description)} helperText={fieldErrors.description} fullWidth /></Grid><Grid item xs={12} md={6}><TextField label="Root cause" value={sheet.root_cause} onChange={(event) => setSheet({ ...sheet, root_cause: event.target.value })} fullWidth /></Grid><Grid item xs={12} md={6}><TextField label="Cost impact" value={sheet.cost_impact} onChange={(event) => setSheet({ ...sheet, cost_impact: event.target.value })} error={Boolean(fieldErrors.cost_impact)} helperText={fieldErrors.cost_impact} fullWidth /></Grid></Grid><Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap><Button variant="outlined" onClick={validateSheet}>Check</Button><Button variant="contained" color="success" disabled={isWorking || Object.keys(fieldErrors).length > 0} onClick={() => void acceptIncidentAndReplan()}>Accept incident</Button><Button variant="outlined" onClick={() => setSheet(null)}>Back</Button><Button variant="text" color="warning" onClick={() => resetFlow()}>Reject</Button></Stack></Stack></Paper>}
      {(isWorking || replanResult) && <AnimatedPipeline title={isWorking ? "Replanning in progress" : "Replan decision"} steps={replanSteps} activeStep={activeStep} />}
      {replanResult && <Paper variant="outlined" sx={{ p: 3, borderRadius: 2 }}><Stack spacing={2}><Typography variant="h6">Replan recommendation</Typography><Typography>{replanResult.comparison.decision_note}</Typography><Typography color="text.secondary">New cost: {formatMoney(replanResult.comparison.new_cost)}. Cost change: {formatMoney(replanResult.comparison.cost_delta)}.</Typography><Stack direction="row" spacing={1}><Button variant="contained" color="success" disabled={isWorking} onClick={() => void acceptReplan()}>Approve</Button><Button variant="outlined" onClick={() => setReplanResult(null)}>Back</Button><Button variant="outlined" color="warning" onClick={() => resetFlow("The replan was rejected and the view was reset.")}>Reject</Button></Stack></Stack></Paper>}
    </Stack>
  );
}
