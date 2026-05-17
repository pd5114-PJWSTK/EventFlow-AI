import { useEffect, useMemo, useState } from "react";
import { Alert, Box, Button, Checkbox, Chip, FormControlLabel, Grid, MenuItem, Paper, Stack, TextField, Typography } from "@mui/material";

import { AnimatedPipeline } from "../components/AnimatedPipeline";
import { BackCornerButton } from "../components/BackCornerButton";
import { EventDetailsCard } from "../components/EventDetailsCard";
import { EventSelect } from "../components/EventSelect";
import { StatusBanner } from "../components/StatusBanner";
import { useAuth } from "../lib/useAuth";
import { formatMoney, parserSourceLabel } from "../lib/format";
import { useSessionState } from "../lib/useSessionState";
import { validateBusinessText, validateNonNegativeNumber } from "../lib/validation";
import type { EquipmentItem, EquipmentTypeItem, ListResponse, PersonItem, ReplanOperatorAction, ReplanResponse, RuntimeIncidentParseResponse, VehicleItem } from "../types/api";

const replanSteps = ["Incident analysis", "Replanning", "Impact comparison", "Decision", "Approval"];
const incidentTypes = ["equipment_failure", "staff_absence", "transport_delay", "venue_issue", "weather_risk", "client_change", "other"];
const severityOptions = ["low", "medium", "high", "critical"];
const executionStages = ["Transport", "Setup", "Live execution", "Teardown", "Return logistics"];

interface IncidentSheet {
  incident_id?: string;
  incident_type: string;
  severity: string;
  description: string;
  root_cause: string;
  reported_by: string;
  cost_impact: string;
  sla_impact: boolean;
  parser_mode?: string;
  parse_confidence?: number;
}

interface ResourceOption {
  id: string;
  type: "person" | "equipment" | "vehicle";
  label: string;
}

function defaultActions(sheet: IncidentSheet | null, result: ReplanResponse | null, resources: ResourceOption[]): ReplanOperatorAction[] {
  const text = `${sheet?.incident_type || ""} ${sheet?.description || ""} ${sheet?.root_cause || ""}`.toLowerCase();
  const firstAudioEquipment = resources.find((item) => item.type === "equipment" && item.label.toLowerCase().includes("audio"));
  const firstTechnician = resources.find((item) => item.type === "person" && item.label.toLowerCase().includes("technician"));
  const firstVehicle = resources.find((item) => item.type === "vehicle" && item.label.toLowerCase().includes("van"));
  const actions: ReplanOperatorAction[] = [
    { action_type: "manual_note", label: "Keep already completed setup and assignments unchanged.", owner: "Operations lead", status: "done" },
    { action_type: "manual_note", label: "Confirm remaining agenda blocks that still need resources.", owner: "Event coordinator", status: "pending" },
  ];

  if (text.includes("audio") || text.includes("sound")) {
    if (firstAudioEquipment) actions.splice(1, 0, { action_type: "add_resource", label: "Deliver replacement audio equipment to the affected stage.", owner: "Audio lead", status: "pending", resource_type: firstAudioEquipment.type, resource_id: firstAudioEquipment.id });
    if (firstTechnician) actions.splice(2, 0, { action_type: "add_resource", label: "Assign an audio technician to install and test the replacement setup.", owner: "Audio lead", status: "pending", resource_type: firstTechnician.type, resource_id: firstTechnician.id });
  } else if (text.includes("transport") || text.includes("delivery") || text.includes("courier")) {
    if (firstVehicle) actions.splice(1, 0, { action_type: "add_resource", label: "Dispatch additional transport to cover the incident.", owner: "Logistics lead", status: "pending", resource_type: firstVehicle.type, resource_id: firstVehicle.id });
  }

  if (text.includes("delay") || text.includes("postpone") || text.includes("reschedule")) {
    actions.push({ action_type: "shift_timing", label: "Move the remaining operational window to absorb reported delay.", owner: "Project manager", status: "pending", timing_delta_minutes: 30 });
  }
  if (result?.comparison.cost_delta) {
    actions.push({ action_type: "manual_note", label: `Review budget impact before approval: ${formatMoney(result.comparison.cost_delta)}.`, owner: "Project manager", status: "pending" });
  }
  return actions;
}

function buildResourceOptions(people: PersonItem[], equipment: EquipmentItem[], vehicles: VehicleItem[], equipmentTypes: EquipmentTypeItem[]): ResourceOption[] {
  const typeById = new Map(equipmentTypes.map((item) => [item.equipment_type_id, item.type_name]));
  return [
    ...people.map((person) => ({ id: person.person_id, type: "person" as const, label: `${person.full_name} (${person.role.replace(/_/g, " ")})` })),
    ...equipment.map((item) => ({ id: item.equipment_id, type: "equipment" as const, label: `${typeById.get(item.equipment_type_id) || "Equipment"}${item.asset_tag ? ` - ${item.asset_tag}` : ""}` })),
    ...vehicles.map((vehicle) => ({ id: vehicle.vehicle_id, type: "vehicle" as const, label: `${vehicle.vehicle_name}${vehicle.registration_number ? ` (${vehicle.registration_number})` : ""}` })),
  ];
}

export function RuntimePage(): JSX.Element {
  const { api } = useAuth();
  const [eventId, setEventId] = useSessionState("cp05.runtime.eventId", "");
  const [incidentText, setIncidentText] = useSessionState("cp05.runtime.text", "Audio system failure on the main stage, approximately 30 minutes delay, reported by Jan.");
  const [sheet, setSheet] = useSessionState<IncidentSheet | null>("cp05.runtime.sheet", null);
  const [fieldErrors, setFieldErrors] = useSessionState<Record<string, string>>("cp05.runtime.errors", {});
  const [replanResult, setReplanResult] = useSessionState<ReplanResponse | null>("cp05.runtime.replan", null);
  const [checked, setChecked] = useSessionState("cp06.runtime.checked", false);
  const [actions, setActions] = useSessionState<ReplanOperatorAction[]>("cp09.runtime.actions", []);
  const [activeStep, setActiveStep] = useSessionState("cp05.runtime.step", 0);
  const [resourceOptions, setResourceOptions] = useState<ResourceOption[]>([]);
  const [success, setSuccess] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isWorking, setIsWorking] = useState(false);

  useEffect(() => {
    const loadResources = async (): Promise<void> => {
      const [peopleData, equipmentData, vehiclesData, equipmentTypesData] = await Promise.all([
        api.request<ListResponse<PersonItem>>("GET", "/api/resources/people?limit=100"),
        api.request<ListResponse<EquipmentItem>>("GET", "/api/resources/equipment?limit=100"),
        api.request<ListResponse<VehicleItem>>("GET", "/api/resources/vehicles?limit=100"),
        api.request<ListResponse<EquipmentTypeItem>>("GET", "/api/resources/equipment-types?limit=100"),
      ]);
      setResourceOptions(buildResourceOptions(peopleData.items, equipmentData.items, vehiclesData.items, equipmentTypesData.items));
    };
    void loadResources().catch(() => setResourceOptions([]));
  }, [api]);

  const resourceOptionsByType = useMemo(
    () => ({
      person: resourceOptions.filter((item) => item.type === "person"),
      equipment: resourceOptions.filter((item) => item.type === "equipment"),
      vehicle: resourceOptions.filter((item) => item.type === "vehicle"),
    }),
    [resourceOptions],
  );

  const resetFlow = (message?: string): void => {
    setEventId("");
    setIncidentText("Audio system failure on the main stage, approximately 30 minutes delay, reported by Jan.");
    setSheet(null);
    setFieldErrors({});
    setReplanResult(null);
    setActions([]);
    setChecked(false);
    setActiveStep(0);
    if (message) setSuccess(message);
  };

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

  const updateAction = (index: number, patch: Partial<ReplanOperatorAction>): void => {
    setActions((current) => current.map((item, itemIndex) => itemIndex === index ? { ...item, ...patch } : item));
  };

  const parseIncident = async (): Promise<void> => {
    setError(null);
    setSuccess(null);
    setReplanResult(null);
    if (!eventId.trim()) { setFieldErrors({ eventId: "Select an event." }); return; }
    setIsWorking(true);
    try {
      const data = await api.request<RuntimeIncidentParseResponse>("POST", `/api/runtime/events/${eventId}/incident/parse`, { raw_log: incidentText, prefer_llm: true, idempotency_key: `incident-${Date.now()}` });
      setSheet({ incident_id: data.incident_id, incident_type: data.incident_type, severity: data.severity, description: data.description, root_cause: data.root_cause || "", reported_by: data.reported_by || "", cost_impact: data.cost_impact ? String(data.cost_impact) : "", sla_impact: data.sla_impact, parser_mode: data.parser_mode, parse_confidence: data.parse_confidence });
      setFieldErrors({});
      setChecked(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not parse the incident.");
    } finally {
      setIsWorking(false);
    }
  };

  const acceptIncidentAndReplan = async (): Promise<void> => {
    if (!validateSheet() || !sheet) return;
    setError(null);
    setSuccess("Incident accepted. Replanning is running.");
    setIsWorking(true);
    try {
      setActiveStep(1);
      const data = await api.request<ReplanResponse>("POST", `/api/planner/replan/${eventId}`, { incident_id: sheet.incident_id, incident_summary: sheet.description, commit_to_assignments: false, idempotency_key: `replan-${Date.now()}` });
      setReplanResult(data);
      setActions(defaultActions(sheet, data, resourceOptions));
      setActiveStep(3);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not run replanning.");
    } finally {
      setIsWorking(false);
    }
  };

  const acceptReplan = async (): Promise<void> => {
    if (!sheet) return;
    setError(null);
    setIsWorking(true);
    try {
      const operatorActions = actions.filter((action) => {
        if (action.action_type === "add_resource" || action.action_type === "swap_resource") return action.resource_type && action.resource_id;
        if (action.action_type === "shift_timing") return action.timing_delta_minutes !== undefined && action.timing_delta_minutes !== null;
        return action.label.trim().length > 0;
      });
      await api.request<ReplanResponse>("POST", `/api/planner/replan/${eventId}`, {
        incident_id: sheet.incident_id,
        incident_summary: sheet.description,
        operator_actions: operatorActions,
        commit_to_assignments: true,
        idempotency_key: `replan-accept-${Date.now()}`,
      });
      setActiveStep(4);
      resetFlow("The replan was approved, operator actions were saved, and the view has been reset.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not approve the replan.");
    } finally {
      setIsWorking(false);
    }
  };

  return (
    <Stack spacing={2.5}>
      <Typography variant="h4">Live replanning</Typography>
      {success && <StatusBanner severity="success" title="Status" message={success} />}
      {error && <Alert severity="error">{error}</Alert>}

      {!sheet && (
        <Paper variant="outlined" sx={{ p: 3, borderRadius: 1 }}>
          <Stack spacing={2}>
            <EventSelect label="Event for incident" value={eventId} onChange={handleEventChange} scope="runtime" error={Boolean(fieldErrors.eventId)} helperText={fieldErrors.eventId} />
            {eventId && <EventDetailsCard eventId={eventId} title="Event context and assigned resources" />}
            <TextField label="Incident description" placeholder="Describe what happened, where it happened, which resource or schedule element is affected, who reported it, expected delay, cost impact and whether the event can continue." multiline minRows={7} value={incidentText} onChange={(event) => setIncidentText(event.target.value)} helperText="Use operational language. The next sheet will let you correct type, severity, root cause and impact before replanning." fullWidth />
            <Box><Button variant="contained" disabled={!eventId || isWorking} onClick={() => void parseIncident()}>Import</Button></Box>
          </Stack>
        </Paper>
      )}

      {sheet && !replanResult && (
        <Paper variant="outlined" sx={{ p: 3, borderRadius: 1, position: "relative" }}>
          <Stack spacing={2}>
            <BackCornerButton onClick={() => setSheet(null)} />
            <Stack direction="row" spacing={1} alignItems="center"><Typography variant="h6">Incident sheet</Typography><Chip label={parserSourceLabel(sheet.parser_mode)} variant="outlined" color={sheet.parser_mode === "llm" ? "success" : "warning"} /></Stack>
            <Grid container spacing={2}>
              <Grid item xs={12} md={4}><TextField select label="Type" value={sheet.incident_type} onChange={(event) => updateSheet({ incident_type: event.target.value })} error={Boolean(fieldErrors.incident_type)} helperText={fieldErrors.incident_type} fullWidth>{incidentTypes.map((item) => <MenuItem key={item} value={item}>{item.replace(/_/g, " ")}</MenuItem>)}</TextField></Grid>
              <Grid item xs={12} md={4}><TextField select label="Severity" value={sheet.severity || "medium"} onChange={(event) => updateSheet({ severity: event.target.value })} fullWidth>{severityOptions.map((item) => <MenuItem key={item} value={item}>{item}</MenuItem>)}</TextField></Grid>
              <Grid item xs={12} md={4}><TextField label="Reporter" placeholder="Name of the coordinator, technician or client contact who reported the incident." value={sheet.reported_by} onChange={(event) => updateSheet({ reported_by: event.target.value })} error={Boolean(fieldErrors.reported_by)} helperText={fieldErrors.reported_by} fullWidth /></Grid>
              <Grid item xs={12}><TextField label="Description" placeholder="Explain the operational impact in plain language: what is blocked, what can continue, which resources are affected and how urgent the decision is." multiline minRows={4} value={sheet.description} onChange={(event) => updateSheet({ description: event.target.value })} error={Boolean(fieldErrors.description)} helperText={fieldErrors.description} fullWidth /></Grid>
              <Grid item xs={12} md={6}><TextField label="Root cause" placeholder="Known cause, suspected cause, or what still needs verification before final approval." value={sheet.root_cause} onChange={(event) => updateSheet({ root_cause: event.target.value })} fullWidth /></Grid>
              <Grid item xs={12} md={6}><TextField label="Cost impact" placeholder="Estimated extra cost in PLN, e.g. replacement device, additional courier, extra staff hours." value={sheet.cost_impact} onChange={(event) => updateSheet({ cost_impact: event.target.value })} error={Boolean(fieldErrors.cost_impact)} helperText={fieldErrors.cost_impact} fullWidth /></Grid>
            </Grid>
            <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
              <Button variant="outlined" onClick={validateSheet}>Check</Button>
              <Button variant="contained" color="success" disabled={isWorking || !checked || Object.keys(fieldErrors).length > 0} onClick={() => void acceptIncidentAndReplan()}>Accept incident</Button>
              <Button variant="text" color="warning" onClick={() => resetFlow()}>Reject</Button>
            </Stack>
          </Stack>
        </Paper>
      )}

      {(isWorking || replanResult) && <AnimatedPipeline title={isWorking ? "Replanning in progress" : "Replan decision"} steps={replanSteps} activeStep={activeStep} />}

      {replanResult && (
        <Paper variant="outlined" sx={{ p: 3, borderRadius: 1, position: "relative" }}>
          <Stack spacing={2}>
            <BackCornerButton onClick={() => setReplanResult(null)} />
            <Typography variant="h6">Replan recommendation</Typography>
            <Typography>{replanResult.comparison.decision_note.includes("No baseline") ? "No approved baseline was found, so this is treated as the first operational replan. Review the proposed resource actions below and approve only if they match the real situation." : replanResult.comparison.decision_note}</Typography>
            <Grid container spacing={1.5}>{executionStages.map((stage, index) => <Grid item xs={12} md={2.4} key={stage}><Paper variant="outlined" sx={{ p: 1.5, height: "100%", bgcolor: index === 1 ? "rgba(15, 118, 110, 0.08)" : "background.paper" }}><Typography variant="caption" color="text.secondary">{stage}</Typography><Typography fontWeight={800}>{index === 0 ? "Completed or locked" : index === 1 ? "Currently affected" : "Still adjustable"}</Typography></Paper></Grid>)}</Grid>
            <Grid container spacing={2}>
              <Grid item xs={12} md={3}><Typography variant="caption" color="text.secondary">Before replan</Typography><Typography fontWeight={900}>{formatMoney(Number(replanResult.comparison.new_cost || 0) - Number(replanResult.comparison.cost_delta || 0))}</Typography></Grid>
              <Grid item xs={12} md={3}><Typography variant="caption" color="text.secondary">After replan</Typography><Typography fontWeight={900}>{formatMoney(replanResult.comparison.new_cost)}</Typography></Grid>
              <Grid item xs={12} md={3}><Typography variant="caption" color="text.secondary">Budget change</Typography><Typography fontWeight={900}>{formatMoney(replanResult.comparison.cost_delta)}</Typography></Grid>
              <Grid item xs={12} md={3}><Typography variant="caption" color="text.secondary">Assigned resources in proposal</Typography><Typography fontWeight={900}>{replanResult.generated_plan.assignments.reduce((sum, item) => sum + item.resource_ids.length, 0)}</Typography></Grid>
            </Grid>
            <Paper variant="outlined" sx={{ p: 2, borderRadius: 1, bgcolor: "rgba(15, 118, 110, 0.05)" }}>
              <Stack spacing={1.5}>
                <Typography fontWeight={800}>Operator action plan</Typography>
                <Typography variant="body2" color="text.secondary">These structured actions are sent as `operator_actions`. Resource actions create manual event assignments on approval and are included in the before/after cost impact. Timing actions update the replan comparison so the decision is visible before approval.</Typography>
                {actions.map((action, index) => (
                  <Grid container spacing={1.5} key={index} alignItems="center">
                    <Grid item xs={12} md={2}><TextField select label="Action type" value={action.action_type} onChange={(event) => updateAction(index, { action_type: event.target.value as ReplanOperatorAction["action_type"], resource_type: null, resource_id: null })} fullWidth><MenuItem value="add_resource">Add resource</MenuItem><MenuItem value="swap_resource">Swap resource</MenuItem><MenuItem value="shift_timing">Shift timing</MenuItem><MenuItem value="manual_note">Manual note</MenuItem></TextField></Grid>
                    <Grid item xs={12} md={3}><TextField label="Action" placeholder="Concrete replan decision, e.g. deliver replacement audio kit or add technician." value={action.label} onChange={(event) => updateAction(index, { label: event.target.value })} fullWidth /></Grid>
                    <Grid item xs={12} md={2}><TextField label="Owner" placeholder="Person or team responsible." value={action.owner} onChange={(event) => updateAction(index, { owner: event.target.value })} fullWidth /></Grid>
                    {(action.action_type === "add_resource" || action.action_type === "swap_resource") && (
                      <>
                        <Grid item xs={12} md={2}><TextField select label="Resource type" value={action.resource_type || ""} onChange={(event) => updateAction(index, { resource_type: event.target.value as ReplanOperatorAction["resource_type"], resource_id: null })} fullWidth><MenuItem value="person">Person</MenuItem><MenuItem value="equipment">Equipment</MenuItem><MenuItem value="vehicle">Vehicle</MenuItem></TextField></Grid>
                        <Grid item xs={12} md={2}><TextField select label="Resource" value={action.resource_id || ""} onChange={(event) => updateAction(index, { resource_id: event.target.value })} fullWidth disabled={!action.resource_type}><MenuItem value="">Select resource</MenuItem>{(action.resource_type ? resourceOptionsByType[action.resource_type] : []).map((item) => <MenuItem key={item.id} value={item.id}>{item.label}</MenuItem>)}</TextField></Grid>
                      </>
                    )}
                    {action.action_type === "shift_timing" && (
                      <Grid item xs={12} md={2}><TextField label="Minutes" type="number" value={action.timing_delta_minutes ?? 30} onChange={(event) => updateAction(index, { timing_delta_minutes: Number(event.target.value) })} fullWidth /></Grid>
                    )}
                    <Grid item xs={12} md={1}><FormControlLabel control={<Checkbox checked={action.status === "done"} onChange={(event) => updateAction(index, { status: event.target.checked ? "done" : "pending" })} />} label={action.status === "done" ? "Done" : "Pending"} /></Grid>
                    <Grid item xs={12} md={1}><Button color="warning" onClick={() => setActions((current) => current.filter((_item, itemIndex) => itemIndex !== index))}>Remove</Button></Grid>
                  </Grid>
                ))}
                <Button variant="outlined" onClick={() => setActions((current) => [...current, { action_type: "manual_note", label: "Add an operational step, resource swap or timing change.", owner: "Coordinator", status: "pending" }])}>Add action</Button>
              </Stack>
            </Paper>
            <Stack direction="row" spacing={1}><Button variant="contained" color="success" disabled={isWorking} onClick={() => void acceptReplan()}>Approve</Button><Button variant="outlined" color="warning" onClick={() => resetFlow("The replan was rejected and the view was reset.")}>Reject</Button></Stack>
          </Stack>
        </Paper>
      )}
    </Stack>
  );
}
