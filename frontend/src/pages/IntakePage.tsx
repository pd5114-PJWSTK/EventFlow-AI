import { useEffect, useMemo, useState } from "react";
import { Alert, Box, Button, Chip, Grid, MenuItem, Paper, Stack, TextField, Typography } from "@mui/material";

import { BackCornerButton } from "../components/BackCornerButton";
import { StatusBanner } from "../components/StatusBanner";
import { useAuth } from "../lib/useAuth";
import { formatDateInput, fromDateInput, parserSourceLabel } from "../lib/format";
import { useSessionState } from "../lib/useSessionState";
import { validateBusinessText, validateCity, validateNonNegativeNumber } from "../lib/validation";
import type { EquipmentTypeItem, EventDraft, IntakeCommitResponse, IntakePreviewResponse, ListResponse, SkillItem } from "../types/api";

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

const requirementTypes = [
  { value: "person_role", label: "Person role" },
  { value: "equipment_type", label: "Equipment type" },
  { value: "vehicle_type", label: "Vehicle type" },
  { value: "person_skill", label: "Person skill" },
  { value: "other", label: "Other" },
];

const personRoles = [
  "technician_audio",
  "technician_light",
  "technician_video",
  "stage_manager",
  "coordinator",
  "driver",
  "warehouse_operator",
  "project_manager",
  "freelancer",
  "other",
];

const vehicleTypes = ["van", "truck", "car", "trailer", "other"];

function cleanEquipmentName(value?: string | null): string {
  return String(value || "").replace("__AUTO_EQUIPMENT_TYPE__::", "").replace(/_/g, " ");
}

function humanize(value?: string | null): string {
  return String(value || "Not selected").replace(/_/g, " ");
}

export function IntakePage(): JSX.Element {
  const { api } = useAuth();
  const [rawInput, setRawInput] = useSessionState("cp05.intake.rawInput", EMPTY_TEXT);
  const [draft, setDraft] = useSessionState<EventDraft | null>("cp05.intake.draft", null);
  const [source, setSource] = useSessionState<string | null>("cp05.intake.source", null);
  const [assumptions, setAssumptions] = useSessionState<string[]>("cp05.intake.assumptions", []);
  const [fieldErrors, setFieldErrors] = useSessionState<Record<string, string>>("cp05.intake.errors", {});
  const [checked, setChecked] = useSessionState("cp06.intake.checked", false);
  const [success, setSuccess] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [equipmentTypes, setEquipmentTypes] = useState<EquipmentTypeItem[]>([]);
  const [skills, setSkills] = useState<SkillItem[]>([]);

  const hasDraft = Boolean(draft);
  const canAdd = hasDraft && checked && Object.keys(fieldErrors).length === 0;

  useEffect(() => {
    const loadCatalogs = async (): Promise<void> => {
      const [equipmentTypesData, skillsData] = await Promise.all([
        api.request<ListResponse<EquipmentTypeItem>>("GET", "/api/resources/equipment-types?limit=100"),
        api.request<ListResponse<SkillItem>>("GET", "/api/resources/skills?limit=100"),
      ]);
      setEquipmentTypes(equipmentTypesData.items);
      setSkills(skillsData.items);
    };
    void loadCatalogs().catch(() => {
      setEquipmentTypes([]);
      setSkills([]);
    });
  }, [api]);

  const resetFlow = (message?: string): void => {
    setDraft(null);
    setRawInput(EMPTY_TEXT);
    setFieldErrors({});
    setChecked(false);
    setAssumptions([]);
    setSource(null);
    if (message) setSuccess(message);
  };

  const updateDraft = (patch: Partial<EventDraft>): void => {
    setChecked(false);
    setDraft((current) => (current ? { ...current, ...patch } : current));
  };

  const updateRequirement = (index: number, patch: Partial<EventDraft["requirements"][number]>): void => {
    setChecked(false);
    setDraft((current) => {
      if (!current) return current;
      return {
        ...current,
        requirements: current.requirements.map((item, itemIndex) => itemIndex === index ? { ...item, ...patch } : item),
      };
    });
  };

  const addRequirement = (): void => {
    setChecked(false);
    setDraft((current) => current ? {
      ...current,
      requirements: [
        ...current.requirements,
        { requirement_type: "person_role", role_required: "coordinator", quantity: 1, mandatory: true, notes: "" },
      ],
    } : current);
  };

  const removeRequirement = (index: number): void => {
    setChecked(false);
    setDraft((current) => current ? { ...current, requirements: current.requirements.filter((_item, itemIndex) => itemIndex !== index) } : current);
  };

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
    if (draft.requirements.length === 0) nextErrors.requirements = "Add at least one requirement.";
    draft.requirements.forEach((requirement, index) => {
      const prefix = `requirements.${index}`;
      const quantityError = validateNonNegativeNumber(requirement.quantity, `Requirement ${index + 1} quantity`, true);
      if (quantityError || Number(requirement.quantity) <= 0) nextErrors[`${prefix}.quantity`] = quantityError || "Quantity must be greater than zero.";
      if (requirement.requirement_type === "person_role" && !requirement.role_required) nextErrors[`${prefix}.role_required`] = "Select a person role.";
      if (requirement.requirement_type === "equipment_type" && !requirement.equipment_type_id) nextErrors[`${prefix}.equipment_type_id`] = "Select equipment type.";
      if (requirement.requirement_type === "vehicle_type" && !requirement.vehicle_type_required) nextErrors[`${prefix}.vehicle_type_required`] = "Select a vehicle type.";
      if (requirement.requirement_type === "person_skill" && !requirement.skill_id) nextErrors[`${prefix}.skill_id`] = "Select a skill or switch to person role.";
    });
    setFieldErrors(nextErrors);
    const isValid = Object.keys(nextErrors).length === 0;
    setChecked(isValid);
    return isValid;
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
      setChecked(false);
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
        <Paper variant="outlined" sx={{ p: 3, borderRadius: 1 }}>
          <Stack spacing={2}>
            <TextField
              label="Event description"
              placeholder="Describe the client, venue, city, date and time window, expected guest count, budget, operational requirements and any constraints the planner should know about."
              multiline
              minRows={8}
              value={rawInput}
              onChange={(event) => setRawInput(event.target.value)}
              helperText="Use natural language. The parser will prepare a review sheet, but you will still approve every important field before saving."
              fullWidth
            />
            <Box><Button variant="contained" onClick={() => void preview()} disabled={isLoading || rawInput.trim().length === 0}>Import</Button></Box>
          </Stack>
        </Paper>
      )}
      {draft && (
        <Paper variant="outlined" sx={{ p: 3, borderRadius: 1, position: "relative" }}>
          <Stack spacing={2.5}>
            <BackCornerButton onClick={() => setDraft(null)} />
            <Stack direction={{ xs: "column", sm: "row" }} spacing={1} alignItems={{ xs: "flex-start", sm: "center" }}>
              <Typography variant="h6">Event sheet</Typography>
              {source && <Chip label={source} color={source.includes("LLM") ? "success" : "warning"} variant="outlined" />}
              {requiredErrorCount > 0 && <Chip label={`Missing: ${requiredErrorCount}`} color="error" />}
            </Stack>
            <Paper variant="outlined" sx={{ p: 2, borderRadius: 1, bgcolor: "rgba(15, 118, 110, 0.04)" }}>
              <Typography variant="caption" color="text.secondary" fontWeight={800}>Original text entered by operator</Typography>
              <Typography sx={{ whiteSpace: "pre-wrap" }}>{rawInput}</Typography>
            </Paper>
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
            <Stack spacing={1.5}>
              <Stack direction="row" spacing={1} alignItems="center" justifyContent="space-between">
                <Box>
                  <Typography fontWeight={800}>Requirements</Typography>
                  <Typography variant="body2" color="text.secondary">Review what the LLM understood: roles, equipment, vehicles, quantities and notes.</Typography>
                </Box>
                <Button variant="outlined" onClick={addRequirement}>Add requirement</Button>
              </Stack>
              {fieldErrors.requirements && <Alert severity="warning">{fieldErrors.requirements}</Alert>}
              {draft.requirements.map((requirement, index) => (
                <Paper key={index} variant="outlined" sx={{ p: 2, borderRadius: 1 }}>
                  <Grid container spacing={2}>
                    <Grid item xs={12} md={3}>
                      <TextField
                        select
                        label="Requirement"
                        value={requirement.requirement_type}
                        onChange={(event) => updateRequirement(index, { requirement_type: event.target.value, role_required: null, equipment_type_id: null, vehicle_type_required: null })}
                        fullWidth
                      >
                        {requirementTypes.map((item) => <MenuItem key={item.value} value={item.value}>{item.label}</MenuItem>)}
                      </TextField>
                    </Grid>
                    {requirement.requirement_type === "person_role" && (
                      <Grid item xs={12} md={3}>
                        <TextField
                          select
                          label="Role"
                          value={requirement.role_required || ""}
                          onChange={(event) => updateRequirement(index, { role_required: event.target.value })}
                          error={Boolean(fieldErrors[`requirements.${index}.role_required`])}
                          helperText={fieldErrors[`requirements.${index}.role_required`]}
                          fullWidth
                        >
                          {personRoles.map((role) => <MenuItem key={role} value={role}>{humanize(role)}</MenuItem>)}
                        </TextField>
                      </Grid>
                    )}
                    {requirement.requirement_type === "equipment_type" && (
                      <Grid item xs={12} md={3}>
                        <TextField
                          select
                          label="Equipment type"
                          value={requirement.equipment_type_id || ""}
                          onChange={(event) => updateRequirement(index, { equipment_type_id: event.target.value })}
                          error={Boolean(fieldErrors[`requirements.${index}.equipment_type_id`])}
                          helperText={fieldErrors[`requirements.${index}.equipment_type_id`]}
                          fullWidth
                        >
                          {requirement.equipment_type_id && !equipmentTypes.some((item) => item.equipment_type_id === requirement.equipment_type_id) && (
                            <MenuItem value={requirement.equipment_type_id}>{cleanEquipmentName(requirement.equipment_type_id)}</MenuItem>
                          )}
                          {equipmentTypes.map((item) => <MenuItem key={item.equipment_type_id} value={item.equipment_type_id}>{item.type_name}</MenuItem>)}
                        </TextField>
                      </Grid>
                    )}
                    {requirement.requirement_type === "vehicle_type" && (
                      <Grid item xs={12} md={3}>
                        <TextField
                          select
                          label="Vehicle"
                          value={requirement.vehicle_type_required || ""}
                          onChange={(event) => updateRequirement(index, { vehicle_type_required: event.target.value })}
                          error={Boolean(fieldErrors[`requirements.${index}.vehicle_type_required`])}
                          helperText={fieldErrors[`requirements.${index}.vehicle_type_required`]}
                          fullWidth
                        >
                          {vehicleTypes.map((vehicle) => <MenuItem key={vehicle} value={vehicle}>{humanize(vehicle)}</MenuItem>)}
                        </TextField>
                      </Grid>
                    )}
                    {requirement.requirement_type === "person_skill" && (
                      <Grid item xs={12} md={3}>
                        <TextField
                          select
                          label="Skill"
                          value={requirement.skill_id || ""}
                          onChange={(event) => updateRequirement(index, { skill_id: event.target.value })}
                          error={Boolean(fieldErrors[`requirements.${index}.skill_id`])}
                          helperText={fieldErrors[`requirements.${index}.skill_id`] || "Select the business skill required for this role."}
                          fullWidth
                        >
                          {requirement.skill_id && !skills.some((item) => item.skill_id === requirement.skill_id) && (
                            <MenuItem value={requirement.skill_id}>{humanize(requirement.skill_id)}</MenuItem>
                          )}
                          {skills.map((item) => <MenuItem key={item.skill_id} value={item.skill_id}>{item.skill_name}</MenuItem>)}
                        </TextField>
                      </Grid>
                    )}
                    <Grid item xs={12} md={2}>
                      <TextField
                        label="Quantity"
                        type="number"
                        value={requirement.quantity}
                        onChange={(event) => updateRequirement(index, { quantity: Number(event.target.value) })}
                        error={Boolean(fieldErrors[`requirements.${index}.quantity`])}
                        helperText={fieldErrors[`requirements.${index}.quantity`]}
                        fullWidth
                      />
                    </Grid>
                    <Grid item xs={12} md={4}>
                      <TextField
                        label="Notes"
                        placeholder="Add business context, timing constraints, preferred crew profile or any instruction that helps validate this requirement."
                        value={requirement.notes || ""}
                        onChange={(event) => updateRequirement(index, { notes: event.target.value })}
                        fullWidth
                      />
                    </Grid>
                    <Grid item xs={12} md={requirement.requirement_type === "other" ? 3 : 12}>
                      <Button color="warning" onClick={() => removeRequirement(index)}>Remove</Button>
                    </Grid>
                  </Grid>
                </Paper>
              ))}
            </Stack>
            <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
              <Button variant="outlined" onClick={validateDraft}>Check</Button>
              <Button variant="contained" color="success" disabled={!canAdd || isLoading} onClick={() => void commit()}>Add</Button>
              <Button variant="text" color="warning" onClick={() => resetFlow()}>Reject</Button>
            </Stack>
          </Stack>
        </Paper>
      )}
    </Stack>
  );
}
