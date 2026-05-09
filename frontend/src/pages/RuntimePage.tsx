import { useState } from "react";
import { Alert, Box, Button, Checkbox, Chip, FormControlLabel, Grid, MenuItem, Paper, Stack, TextField, Typography } from "@mui/material";

import { AnimatedPipeline } from "../components/AnimatedPipeline";
import { BackCornerButton } from "../components/BackCornerButton";
import { EventDetailsCard } from "../components/EventDetailsCard";
import { EventSelect } from "../components/EventSelect";
import { StatusBanner } from "../components/StatusBanner";
import { useAuth } from "../lib/auth";
import { formatMoney, parserSourceLabel } from "../lib/format";
import { useSessionState } from "../lib/useSessionState";
import { validateBusinessText, validateNonNegativeNumber } from "../lib/validation";
import type { ReplanResponse, RuntimeIncidentParseResponse } from "../types/api";

const replanSteps = ["Incident analysis", "Replanning", "Impact comparison", "Decision", "Approval"];
const incidentTypes = ["equipment_failure", "staff_absence", "transport_delay", "venue_issue", "weather_risk", "client_change", "other"];
const severityOptions = ["low", "medium", "high", "critical"];
const executionStages = ["Transport", "Setup", "Live execution", "Teardown", "Return logistics"];

interface IncidentSheet { incident_id?: string; incident_type: string; severity: string; description: string; root_cause: string; reported_by: string; cost_impact: string; sla_impact: boolean; parser_mode?: string; parse_confidence?: number; }
interface ReplanAction { label: string; owner: string; status: "done" | "pending"; }

function defaultActions(sheet: IncidentSheet | null, result: ReplanResponse | null): ReplanAction[] {
  const text = `${sheet?.incident_type || ""} ${sheet?.description || ""} ${sheet?.root_cause || ""}`.toLowerCase();
  const isAudio = text.includes("audio") || text.includes("sound");
  const isEquipment = isAudio || text.includes("equipment") || text.includes("device");
  const actions: ReplanAction[] = [
    { label: "Keep already completed setup and assignments unchanged.", owner: "Operations lead", status: "done" },
    { label: "Confirm remaining agenda blocks that still need resources.", owner: "Event coordinator", status: "pending" },
  ];
  if (isAudio) {
    actions.splice(1, 0, { label: "Dispatch replacement audio kit and assign an audio technician to install it.", owner: "Audio lead", status: "pending" });
  } else if (isEquipment) {
    actions.splice(1, 0, { label: "Dispatch replacement equipment and assign a technician to validate it.", owner: "Technical lead", status: "pending" });
  }
  if (result?.comparison.cost_delta) {
    actions.push({ label: `Review budget impact before approval: ${formatMoney(result.comparison.cost_delta)}.`, owner: "Project manager", status: "pending" });
  }
  if (text.includes("delay") || text.includes("postpone") || text.includes("reschedule")) {
    actions.push({ label: "Review whether the event window should move before execution starts.", owner: "Project manager", status: "pending" });
  }
  return actions;
}

export function RuntimePage(): JSX.Element {
  const { api } = useAuth();
  const [eventId, setEventId] = useSessionState("cp05.runtime.eventId", "");
  const [incidentText, setIncidentText] = useSessionState("cp05.runtime.text", "Audio system failure on the main stage, approximately 30 minutes delay, reported by Jan.");
  const [sheet, setSheet] = useSessionState<IncidentSheet | null>("cp05.runtime.sheet", null);
  const [fieldErrors, setFieldErrors] = useSessionState<Record<string, string>>("cp05.runtime.errors", {});
  const [replanResult, setReplanResult] = useSessionState<ReplanResponse | null>("cp05.runtime.replan", null);
  const [checked, setChecked] = useSessionState("cp06.runtime.checked", false);
  const [actions, setActions] = useSessionState<ReplanAction[]>("cp06.runtime.actions", []);
  const [activeStep, setActiveStep] = useSessionState("cp05.runtime.step", 0);
  const [success, setSuccess] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isWorking, setIsWorking] = useState(false);

  const resetFlow = (message?: string): void => { setEventId(""); setIncidentText("Audio system failure on the main stage, approximately 30 minutes delay, reported by Jan."); setSheet(null); setFieldErrors({}); setReplanResult(null); setActions([]); setChecked(false); setActiveStep(0); if (message) setSuccess(message); };
  const handleEventChange = (nextEventId: string): void => {
    setEventId(nextEventId);
    setSheet(null);
    setFieldErrors({});
    setReplanResult(null);
    setActions([]);
    setChecked(false);
    setActiveStep(0);
    setError(null);
    setSuccess(null);
  };

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
    const isValid = Object.keys(next).length === 0;
    setChecked(isValid);
    return isValid;
  };

  const updateSheet = (patch: Partial<IncidentSheet>): void => {
    setChecked(false);
    setSheet((current) => current ? { ...current, ...patch } : current);
  };

  const parseIncident = async (): Promise<void> => {
    setError(null); setSuccess(null); setReplanResult(null);
    if (!eventId.trim()) { setFieldErrors({ eventId: "Select an event." }); return; }
    setIsWorking(true);
    try {
      const data = await api.request<RuntimeIncidentParseResponse>("POST", `/api/runtime/events/${eventId}/incident/parse`, { raw_log: incidentText, prefer_llm: true, idempotency_key: `incident-${Date.now()}` });
      setSheet({ incident_id: data.incident_id, incident_type: data.incident_type, severity: data.severity, description: data.description, root_cause: data.root_cause || "", reported_by: data.reported_by || "", cost_impact: data.cost_impact ? String(data.cost_impact) : "", sla_impact: data.sla_impact, parser_mode: data.parser_mode, parse_confidence: data.parse_confidence });
      setFieldErrors({});
      setChecked(false);
    } catch (err) { setError(err instanceof Error ? err.message : "Could not parse the incident."); } finally { setIsWorking(false); }
  };

  const acceptIncidentAndReplan = async (): Promise<void> => {
    if (!validateSheet() || !sheet) return;
    setError(null); setSuccess("Incident accepted. Replanning is running."); setIsWorking(true);
    try {
      setActiveStep(1);
      const data = await api.request<ReplanResponse>("POST", `/api/planner/replan/${eventId}`, { incident_id: sheet.incident_id, incident_summary: sheet.description, commit_to_assignments: false, idempotency_key: `replan-${Date.now()}` });
      setReplanResult(data); setActions(defaultActions(sheet, data)); setActiveStep(3);
    } catch (err) { setError(err instanceof Error ? err.message : "Could not run replanning."); } finally { setIsWorking(false); }
  };

  const acceptReplan = async (): Promise<void> => {
    if (!sheet) return;
    setError(null); setIsWorking(true);
    try {
      await api.request<ReplanResponse>("POST", `/api/planner/replan/${eventId}`, { incident_id: sheet.incident_id, incident_summary: `${sheet.description}\nOperator action plan:\n${actions.map((action) => `- ${action.status}: ${action.label} (${action.owner})`).join("\n")}`, commit_to_assignments: true, idempotency_key: `replan-accept-${Date.now()}` });
      setActiveStep(4); resetFlow("The replan was approved and saved. The live replanning view has been reset.");
    } catch (err) { setError(err instanceof Error ? err.message : "Could not approve the replan."); } finally { setIsWorking(false); }
  };

  return (
    <Stack spacing={2.5}>
      <Typography variant="h4">Live replanning</Typography>
      {success && <StatusBanner severity="success" title="Status" message={success} />}
      {error && <Alert severity="error">{error}</Alert>}
      {!sheet && <Paper variant="outlined" sx={{ p: 3, borderRadius: 2 }}><Stack spacing={2}><EventSelect label="Event for incident" value={eventId} onChange={handleEventChange} scope="runtime" error={Boolean(fieldErrors.eventId)} helperText={fieldErrors.eventId} />{eventId && <EventDetailsCard eventId={eventId} title="Event context and assigned resources" />}<TextField label="Incident description" placeholder="Describe what happened, where it happened, which resource or schedule element is affected, who reported it, expected delay, cost impact and whether the event can continue." multiline minRows={7} value={incidentText} onChange={(event) => setIncidentText(event.target.value)} helperText="Use operational language. The next sheet will let you correct type, severity, root cause and impact before replanning." fullWidth /><Box><Button variant="contained" disabled={!eventId || isWorking} onClick={() => void parseIncident()}>Import</Button></Box></Stack></Paper>}
      {sheet && !replanResult && <Paper variant="outlined" sx={{ p: 3, borderRadius: 2, position: "relative" }}><Stack spacing={2}><BackCornerButton onClick={() => setSheet(null)} /><Stack direction="row" spacing={1} alignItems="center"><Typography variant="h6">Incident sheet</Typography><Chip label={parserSourceLabel(sheet.parser_mode)} variant="outlined" color={sheet.parser_mode === "llm" ? "success" : "warning"} /></Stack><Grid container spacing={2}><Grid item xs={12} md={4}><TextField select label="Type" value={sheet.incident_type} onChange={(event) => updateSheet({ incident_type: event.target.value })} error={Boolean(fieldErrors.incident_type)} helperText={fieldErrors.incident_type} fullWidth>{incidentTypes.map((item) => <MenuItem key={item} value={item}>{item.replace(/_/g, " ")}</MenuItem>)}</TextField></Grid><Grid item xs={12} md={4}><TextField select label="Severity" value={sheet.severity || "medium"} onChange={(event) => updateSheet({ severity: event.target.value })} fullWidth>{severityOptions.map((item) => <MenuItem key={item} value={item}>{item}</MenuItem>)}</TextField></Grid><Grid item xs={12} md={4}><TextField label="Reporter" placeholder="Name of the coordinator, technician or client contact who reported the incident." value={sheet.reported_by} onChange={(event) => updateSheet({ reported_by: event.target.value })} error={Boolean(fieldErrors.reported_by)} helperText={fieldErrors.reported_by} fullWidth /></Grid><Grid item xs={12}><TextField label="Description" placeholder="Explain the operational impact in plain language: what is blocked, what can continue, which resources are affected and how urgent the decision is." multiline minRows={4} value={sheet.description} onChange={(event) => updateSheet({ description: event.target.value })} error={Boolean(fieldErrors.description)} helperText={fieldErrors.description} fullWidth /></Grid><Grid item xs={12} md={6}><TextField label="Root cause" placeholder="Known cause, suspected cause, or what still needs verification before final approval." value={sheet.root_cause} onChange={(event) => updateSheet({ root_cause: event.target.value })} fullWidth /></Grid><Grid item xs={12} md={6}><TextField label="Cost impact" placeholder="Estimated extra cost in PLN, e.g. replacement device, additional courier, extra staff hours." value={sheet.cost_impact} onChange={(event) => updateSheet({ cost_impact: event.target.value })} error={Boolean(fieldErrors.cost_impact)} helperText={fieldErrors.cost_impact} fullWidth /></Grid></Grid><Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap><Button variant="outlined" onClick={validateSheet}>Check</Button><Button variant="contained" color="success" disabled={isWorking || !checked || Object.keys(fieldErrors).length > 0} onClick={() => void acceptIncidentAndReplan()}>Accept incident</Button><Button variant="text" color="warning" onClick={() => resetFlow()}>Reject</Button></Stack></Stack></Paper>}
      {(isWorking || replanResult) && <AnimatedPipeline title={isWorking ? "Replanning in progress" : "Replan decision"} steps={replanSteps} activeStep={activeStep} />}
      {replanResult && <Paper variant="outlined" sx={{ p: 3, borderRadius: 2, position: "relative" }}><Stack spacing={2}><BackCornerButton onClick={() => setReplanResult(null)} /><Typography variant="h6">Replan recommendation</Typography><Typography>{replanResult.comparison.decision_note.includes("No baseline") ? "No approved baseline was found, so this is treated as the first operational replan. Review the proposed resource actions below and approve only if they match the real situation." : replanResult.comparison.decision_note}</Typography><Grid container spacing={1.5}>{executionStages.map((stage, index) => <Grid item xs={12} md={2.4} key={stage}><Paper variant="outlined" sx={{ p: 1.5, height: "100%", bgcolor: index === 1 ? "rgba(15, 118, 110, 0.08)" : "background.paper" }}><Typography variant="caption" color="text.secondary">{stage}</Typography><Typography fontWeight={800}>{index === 0 ? "Completed or locked" : index === 1 ? "Currently affected" : "Still adjustable"}</Typography></Paper></Grid>)}</Grid><Grid container spacing={2}><Grid item xs={12} md={3}><Typography variant="caption" color="text.secondary">Before replan</Typography><Typography fontWeight={900}>{formatMoney(Number(replanResult.comparison.new_cost || 0) - Number(replanResult.comparison.cost_delta || 0))}</Typography></Grid><Grid item xs={12} md={3}><Typography variant="caption" color="text.secondary">After replan</Typography><Typography fontWeight={900}>{formatMoney(replanResult.comparison.new_cost)}</Typography></Grid><Grid item xs={12} md={3}><Typography variant="caption" color="text.secondary">Budget change</Typography><Typography fontWeight={900}>{formatMoney(replanResult.comparison.cost_delta)}</Typography></Grid><Grid item xs={12} md={3}><Typography variant="caption" color="text.secondary">Assigned resources in proposal</Typography><Typography fontWeight={900}>{replanResult.generated_plan.assignments.reduce((sum, item) => sum + item.resource_ids.length, 0)}</Typography></Grid></Grid><Paper variant="outlined" sx={{ p: 2, borderRadius: 2, bgcolor: "rgba(15, 118, 110, 0.05)" }}><Stack spacing={1}><Typography fontWeight={800}>Operator action plan</Typography><Typography variant="body2" color="text.secondary">These actions are written into the approved replan summary and influence what assignments/timing changes the operator commits for this event. Use them to confirm concrete decisions, such as replacing an audio kit, adding a technician, swapping a vehicle, or delaying a future setup block.</Typography>{actions.map((action, index) => <Grid container spacing={1.5} key={index} alignItems="center"><Grid item xs={12} md={2}><FormControlLabel control={<Checkbox checked={action.status === "done"} onChange={(event) => setActions((current) => current.map((item, itemIndex) => itemIndex === index ? { ...item, status: event.target.checked ? "done" : "pending" } : item))} />} label={action.status === "done" ? "Done" : "Pending"} /></Grid><Grid item xs={12} md={6}><TextField label="Action" placeholder="Describe a concrete replan decision: add a technician, replace equipment, swap vehicle, move setup or shift event timing." value={action.label} onChange={(event) => setActions((current) => current.map((item, itemIndex) => itemIndex === index ? { ...item, label: event.target.value } : item))} fullWidth /></Grid><Grid item xs={12} md={3}><TextField label="Owner" placeholder="Person or role responsible for this action." value={action.owner} onChange={(event) => setActions((current) => current.map((item, itemIndex) => itemIndex === index ? { ...item, owner: event.target.value } : item))} fullWidth /></Grid><Grid item xs={12} md={1}><Button color="warning" onClick={() => setActions((current) => current.filter((_item, itemIndex) => itemIndex !== index))}>Remove</Button></Grid></Grid>)}<Button variant="outlined" onClick={() => setActions((current) => [...current, { label: "Add an operational step, resource swap or timing change.", owner: "Coordinator", status: "pending" }])}>Add action</Button></Stack></Paper><Stack direction="row" spacing={1}><Button variant="contained" color="success" disabled={isWorking} onClick={() => void acceptReplan()}>Approve</Button><Button variant="outlined" color="warning" onClick={() => resetFlow("The replan was rejected and the view was reset.")}>Reject</Button></Stack></Stack></Paper>}
    </Stack>
  );
}
