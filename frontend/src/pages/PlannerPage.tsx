import { useMemo, useState } from "react";
import AutoFixHighIcon from "@mui/icons-material/AutoFixHigh";
import CompareArrowsIcon from "@mui/icons-material/CompareArrows";
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import { Accordion, AccordionDetails, AccordionSummary, Alert, Box, Button, Chip, Grid, MenuItem, Paper, Stack, Switch, TextField, Typography } from "@mui/material";

import { AnimatedPipeline } from "../components/AnimatedPipeline";
import { BackCornerButton } from "../components/BackCornerButton";
import { EventDetailsCard } from "../components/EventDetailsCard";
import { EventSelect } from "../components/EventSelect";
import { StatusBanner } from "../components/StatusBanner";
import { useAuth } from "../lib/useAuth";
import { formatDurationMinutes, formatMoney, formatNumber, formatPercent } from "../lib/format";
import { useSessionState } from "../lib/useSessionState";
import type {
  AssignmentSlot,
  EquipmentItem,
  EquipmentTypeItem,
  EventAssignmentItem,
  EventRequirementItem,
  GeneratedPlanAssignment,
  GeneratedPlanResponse,
  ListResponse,
  PersonItem,
  PlanCandidate,
  PlanMetricDelta,
  PlanMetrics,
  RecommendBestPlanResponse,
  SkillItem,
  VehicleItem,
} from "../types/api";

const steps = ["Baseline plan", "Resource preview", "ML optimization", "Resource review", "Approval"];

function candidateTitle(candidateName?: string): string {
  return String(candidateName || "optimized").replace(/_/g, " ").replace(/\b\w/g, (char) => char.toUpperCase());
}

function humanize(value?: string | null): string {
  return value ? value.replace(/_/g, " ") : "Not specified";
}

function Metric({ label, value, helper }: { label: string; value: string; helper?: string }): JSX.Element {
  return (
    <Paper variant="outlined" sx={{ p: 1.5, borderRadius: 999, height: "100%" }}>
      <Typography variant="caption" color="text.secondary" fontWeight={800}>{label}</Typography>
      <Typography fontWeight={900}>{value}</Typography>
      {helper && <Typography variant="caption" color="text.secondary">{helper}</Typography>}
    </Paper>
  );
}

function buildResourceMap(people: PersonItem[], equipment: EquipmentItem[], vehicles: VehicleItem[], equipmentTypes: EquipmentTypeItem[]): Record<string, string> {
  const typeById = new Map(equipmentTypes.map((item) => [item.equipment_type_id, item.type_name]));
  const map: Record<string, string> = {};
  people.forEach((person) => { map[person.person_id] = `${person.full_name} (${humanize(person.role)})`; });
  equipment.forEach((item) => {
    const typeName = typeById.get(item.equipment_type_id) || "Equipment";
    map[item.equipment_id] = `${typeName}${item.asset_tag ? ` - ${item.asset_tag}` : ""}`;
  });
  vehicles.forEach((vehicle) => { map[vehicle.vehicle_id] = `${vehicle.vehicle_name}${vehicle.registration_number ? ` (${vehicle.registration_number})` : ""}`; });
  return map;
}

function requirementLabel(
  requirement: EventRequirementItem | undefined,
  equipmentTypeNames: Record<string, string>,
  skillNames: Record<string, string>,
): string {
  if (!requirement) return "Operational requirement";
  const quantity = formatNumber(requirement.quantity);
  if (requirement.requirement_type === "person_role") return `${quantity} x ${humanize(requirement.role_required)}`;
  if (requirement.requirement_type === "equipment_type") return `${quantity} x ${equipmentTypeNames[requirement.equipment_type_id || ""] || "equipment"}`;
  if (requirement.requirement_type === "vehicle_type") return `${quantity} x ${humanize(requirement.vehicle_type_required)} vehicle`;
  if (requirement.requirement_type === "person_skill") return `${quantity} x ${skillNames[requirement.skill_id || ""] || "skill"}`;
  return `${quantity} x ${humanize(requirement.requirement_type)}`;
}

function assignmentSentence(
  assignment: GeneratedPlanAssignment,
  resourceMap: Record<string, string>,
  labelByRequirement: Record<string, string>,
): string {
  const names = assignment.resource_ids.map((id) => resourceMap[id] || "Unnamed resource");
  const label = labelByRequirement[assignment.requirement_id] || humanize(assignment.resource_type);
  if (names.length === 0) return `${label}: still missing ${formatNumber(assignment.unassigned_count || 1)} resource(s).`;
  return `${label}: ${names.join(", ")}.`;
}

function planUsage(
  plan: GeneratedPlanResponse | null,
  resourceMap: Record<string, string>,
  labelByRequirement: Record<string, string>,
): string[] {
  if (!plan || plan.assignments.length === 0) return ["No resource assignments were generated yet."];
  return plan.assignments.map((assignment) => assignmentSentence(assignment, resourceMap, labelByRequirement));
}

function selectedCandidate(recommendation: RecommendBestPlanResponse | null): PlanCandidate | undefined {
  if (!recommendation) return undefined;
  return recommendation.candidates.find((candidate) => candidate.candidate_name === recommendation.selected_candidate_name);
}

function fallbackMetrics(plan: GeneratedPlanResponse | null): PlanMetrics | null {
  if (!plan) return null;
  const assigned = plan.assignments.reduce((sum, item) => sum + item.resource_ids.length, 0);
  const missing = plan.assignments.reduce((sum, item) => sum + item.unassigned_count, 0);
  const total = assigned + missing;
  const coverage = total > 0 ? assigned / total : 1;
  return {
    event_budget: null,
    resource_cost_to_budget_ratio: null,
    estimated_cost: plan.estimated_cost,
    estimated_duration_minutes: 0,
    predicted_delay_risk: 0,
    predicted_incident_risk: 0,
    predicted_sla_breach_risk: 0,
    coverage_ratio: coverage,
    reliability_score: 0,
    backup_coverage_ratio: 0,
    missing_resource_count: missing,
    assigned_resource_count: assigned,
    optimization_score: 0,
  };
}

function metricRows(metrics: PlanMetrics | null | undefined): Array<{ label: string; value: string; helper?: string }> {
  if (!metrics) return [];
  return [
    { label: "Event budget", value: metrics.event_budget ? formatMoney(metrics.event_budget) : "Not provided" },
    { label: "Planned resource cost", value: formatMoney(metrics.estimated_cost) },
    { label: "Resource cost vs budget", value: metrics.resource_cost_to_budget_ratio != null ? formatPercent(metrics.resource_cost_to_budget_ratio) : "No budget data" },
    { label: "Estimated duration", value: Number(metrics.estimated_duration_minutes) > 0 ? formatDurationMinutes(metrics.estimated_duration_minutes) : "Calculated in optimized run" },
    { label: "Delay risk", value: formatPercent(metrics.predicted_delay_risk) },
    { label: "Incident risk", value: formatPercent(metrics.predicted_incident_risk) },
    { label: "SLA breach risk", value: formatPercent(metrics.predicted_sla_breach_risk) },
    { label: "Requirement coverage", value: formatPercent(metrics.coverage_ratio), helper: "Share of required resource slots that are assigned." },
    { label: "Reliability score", value: formatPercent(metrics.reliability_score), helper: "Average reliability of the assigned resources based on operational history." },
    { label: "Backup coverage", value: formatPercent(metrics.backup_coverage_ratio), helper: "Share of slots with at least one alternative resource available." },
    { label: "Missing resources", value: formatNumber(metrics.missing_resource_count) },
    { label: "Assigned resources", value: formatNumber(metrics.assigned_resource_count) },
    { label: "Plan quality", value: Number(metrics.optimization_score) > 0 ? `${formatNumber(metrics.optimization_score, 1)} / 100` : "Baseline" },
  ];
}

function deltaRows(delta?: PlanMetricDelta | null): Array<{ label: string; value: string; goodWhen: "negative" | "positive" }> {
  if (!delta) return [];
  return [
    { label: "Cost", value: signedMoney(delta.estimated_cost), goodWhen: "negative" },
    { label: "Cost vs budget", value: delta.resource_cost_to_budget_ratio != null ? signedPercent(delta.resource_cost_to_budget_ratio) : "No data", goodWhen: "negative" },
    { label: "Duration", value: signedDuration(delta.estimated_duration_minutes), goodWhen: "negative" },
    { label: "Delay risk", value: signedPercent(delta.predicted_delay_risk), goodWhen: "negative" },
    { label: "Incident risk", value: signedPercent(delta.predicted_incident_risk), goodWhen: "negative" },
    { label: "Coverage", value: signedPercent(delta.coverage_ratio), goodWhen: "positive" },
    { label: "Reliability", value: signedPercent(delta.reliability_score), goodWhen: "positive" },
    { label: "Backup coverage", value: signedPercent(delta.backup_coverage_ratio), goodWhen: "positive" },
    { label: "Plan quality", value: signedNumber(delta.optimization_score), goodWhen: "positive" },
  ];
}

function signedNumber(value: string | number): string {
  const numeric = Number(value);
  if (Number.isNaN(numeric)) return "No data";
  return `${numeric > 0 ? "+" : ""}${formatNumber(numeric, 1)}`;
}

function signedMoney(value: string | number): string {
  const numeric = Number(value);
  if (Number.isNaN(numeric)) return "No data";
  return `${numeric > 0 ? "+" : ""}${formatMoney(numeric)}`;
}

function signedDuration(value: string | number): string {
  const numeric = Number(value);
  if (Number.isNaN(numeric)) return "No data";
  return `${numeric > 0 ? "+" : ""}${formatDurationMinutes(numeric)}`;
}

function signedPercent(value: string | number): string {
  const numeric = Number(value);
  if (Number.isNaN(numeric)) return "No data";
  const percent = Math.abs(numeric) <= 1 ? numeric * 100 : numeric;
  return `${percent > 0 ? "+" : ""}${formatNumber(percent, 1)} pp`;
}

function optimizationNarrative(candidate: PlanCandidate | undefined): string {
  if (!candidate) return "The optimized plan keeps the strongest feasible assignment returned by the planner.";
  const profile = candidateTitle(candidate.candidate_name).toLowerCase();
  if (profile.includes("low cost")) return "The optimizer reduced operating cost first while preserving enough coverage to run the event safely.";
  if (profile.includes("reliability")) return "The optimizer preferred resources and timing assumptions that reduce delay and incident risk.";
  if (profile.includes("coverage")) return "The optimizer prioritized filling every critical role and resource gap before cost tuning.";
  return "The optimizer selected a balanced plan because it offers the best mix of cost, coverage and risk for the current event data.";
}

function sameAssignments(baseline: GeneratedPlanResponse | null, optimized: GeneratedPlanResponse | null): boolean {
  if (!baseline || !optimized) return false;
  return JSON.stringify(baseline.assignments.map((item) => [...item.resource_ids].sort()).sort()) === JSON.stringify(optimized.assignments.map((item) => [...item.resource_ids].sort()).sort());
}

function resourceOptions(
  slot: AssignmentSlot,
  index: number,
  assignmentDraft: AssignmentSlot[],
  existingAssignments: EventAssignmentItem[],
): Array<{ id: string; label: string; score: number; cost: string | number; note: string }> {
  const usedInDraft = new Set(
    assignmentDraft.map((item, itemIndex) => itemIndex === index ? "" : item.selected_resource_id || "").filter(Boolean),
  );
  const usedInEvent = new Set(
    existingAssignments.map((item) => item.person_id || item.equipment_id || item.vehicle_id).filter(Boolean) as string[],
  );
  return (slot.candidate_options || [])
    .map((option) => ({
      id: option.resource_id,
      label: option.resource_name,
      score: Number(option.recommendation_score),
      cost: option.estimated_cost,
      note: option.why_recommended,
    }))
    .filter((row) => row.id === slot.selected_resource_id || (!usedInDraft.has(row.id) && !usedInEvent.has(row.id)))
    .sort((a, b) => b.score - a.score);
}

function fallbackSlotsFromAssignments(plan: GeneratedPlanResponse, resourceMap: Record<string, string>, labelByRequirement: Record<string, string>): AssignmentSlot[] {
  return plan.assignments.flatMap((assignment) => {
    const selected = assignment.resource_ids.length > 0 ? assignment.resource_ids : Array.from({ length: assignment.unassigned_count }, () => "");
    return selected.map((resourceId, index) => ({
      requirement_id: assignment.requirement_id,
      slot_index: index + 1,
      resource_type: assignment.resource_type,
      business_label: `${labelByRequirement[assignment.requirement_id] || humanize(assignment.resource_type)} ${index + 1}`,
      selected_resource_id: resourceId || null,
      selected_resource_name: resourceId ? resourceMap[resourceId] || "Unnamed resource" : null,
      estimated_cost: assignment.resource_ids.length > 0 ? Number(assignment.estimated_cost) / assignment.resource_ids.length : 0,
      candidate_options: resourceId ? [{
        resource_id: resourceId,
        resource_name: resourceMap[resourceId] || "Unnamed resource",
        recommendation_score: 100,
        estimated_cost: assignment.estimated_cost,
        availability_note: "Selected by planner.",
        why_recommended: "Selected by planner.",
      }] : [],
    }));
  });
}

function groupedAssignmentOverrides(slots: AssignmentSlot[]): Array<{ requirement_id: string; resource_type: string; resource_ids: string[] }> {
  const grouped = new Map<string, { requirement_id: string; resource_type: string; resource_ids: string[] }>();
  slots.forEach((slot) => {
    const current = grouped.get(slot.requirement_id) || { requirement_id: slot.requirement_id, resource_type: slot.resource_type, resource_ids: [] };
    if (slot.selected_resource_id) current.resource_ids.push(slot.selected_resource_id);
    grouped.set(slot.requirement_id, current);
  });
  return Array.from(grouped.values());
}

export function PlannerPage(): JSX.Element {
  const { api } = useAuth();
  const [eventId, setEventId] = useSessionState("cp05.planner.eventId", "");
  const [previewPlan, setPreviewPlan] = useSessionState<GeneratedPlanResponse | null>("cp05.planner.preview", null);
  const [recommendation, setRecommendation] = useSessionState<RecommendBestPlanResponse | null>("cp05.planner.recommendation", null);
  const [activeStep, setActiveStep] = useSessionState("cp05.planner.activeStep", 0);
  const [resourceMap, setResourceMap] = useSessionState<Record<string, string>>("cp06.planner.resourceMap", {});
  const [requirements, setRequirements] = useSessionState<EventRequirementItem[]>("cp08.planner.requirements", []);
  const [existingAssignments, setExistingAssignments] = useSessionState<EventAssignmentItem[]>("cp08.planner.assignments", []);
  const [equipmentTypeNames, setEquipmentTypeNames] = useSessionState<Record<string, string>>("cp08.planner.equipmentTypeNames", {});
  const [skillNames, setSkillNames] = useSessionState<Record<string, string>>("cp08.planner.skillNames", {});
  const [assignmentDraft, setAssignmentDraft] = useSessionState<AssignmentSlot[]>("cp11.planner.assignmentDraft", []);
  const [reviewAssignments, setReviewAssignments] = useSessionState("cp07.planner.reviewAssignments", false);
  const [showOptimized, setShowOptimized] = useSessionState("cp08.planner.showOptimized", true);
  const [success, setSuccess] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isWorking, setIsWorking] = useState(false);

  const labelByRequirement = useMemo(
    () => Object.fromEntries(requirements.map((item) => [item.requirement_id, requirementLabel(item, equipmentTypeNames, skillNames)])),
    [equipmentTypeNames, requirements, skillNames],
  );
  const chosenCandidate = selectedCandidate(recommendation);
  const planInView = showOptimized && recommendation ? recommendation.selected_plan : previewPlan;
  const baselinePlanMetrics = recommendation?.baseline_metrics || previewPlan?.metrics || fallbackMetrics(previewPlan);
  const optimizedPlanMetrics = recommendation?.optimized_metrics || recommendation?.selected_plan.metrics || fallbackMetrics(recommendation?.selected_plan || null);
  const metricsInView = showOptimized && recommendation ? optimizedPlanMetrics : baselinePlanMetrics;
  const reviewEstimate = assignmentDraft.reduce((sum, item) => sum + Number(item.estimated_cost || 0), 0);
  const assignmentsIdentical = sameAssignments(previewPlan, recommendation?.selected_plan || null);

  const clearPlanState = (): void => {
    setPreviewPlan(null);
    setRecommendation(null);
    setAssignmentDraft([]);
    setReviewAssignments(false);
    setShowOptimized(true);
    setActiveStep(0);
  };

  const handleEventChange = (nextEventId: string): void => {
    setEventId(nextEventId);
    setSuccess(null);
    setError(null);
    clearPlanState();
  };

  const resetFlow = (message?: string): void => {
    setEventId("");
    clearPlanState();
    setResourceMap({});
    setRequirements([]);
    setExistingAssignments([]);
    if (message) setSuccess(message);
  };

  const loadPlanningContext = async (): Promise<void> => {
    const [peopleData, equipmentData, vehiclesData, requirementsData, assignmentsData, equipmentTypesData, skillsData] = await Promise.all([
      api.request<ListResponse<PersonItem>>("GET", "/api/resources/people?limit=100"),
      api.request<ListResponse<EquipmentItem>>("GET", "/api/resources/equipment?limit=100"),
      api.request<ListResponse<VehicleItem>>("GET", "/api/resources/vehicles?limit=100"),
      api.request<ListResponse<EventRequirementItem>>("GET", `/api/events/${eventId}/requirements?limit=100`),
      api.request<ListResponse<EventAssignmentItem>>("GET", `/api/events/${eventId}/assignments?limit=200`),
      api.request<ListResponse<EquipmentTypeItem>>("GET", "/api/resources/equipment-types?limit=100"),
      api.request<ListResponse<SkillItem>>("GET", "/api/resources/skills?limit=100"),
    ]);
    setRequirements(requirementsData.items);
    setExistingAssignments(assignmentsData.items);
    setEquipmentTypeNames(Object.fromEntries(equipmentTypesData.items.map((item) => [item.equipment_type_id, item.type_name])));
    setSkillNames(Object.fromEntries(skillsData.items.map((item) => [item.skill_id, item.skill_name])));
    setResourceMap(buildResourceMap(peopleData.items, equipmentData.items, vehiclesData.items, equipmentTypesData.items));
  };

  const plan = async (): Promise<void> => {
    setError(null);
    setSuccess(null);
    setIsWorking(true);
    clearPlanState();
    try {
      setActiveStep(0);
      await loadPlanningContext();
      await api.request("POST", "/api/planner/validate-constraints", { event_id: eventId });
      const generated = await api.request<GeneratedPlanResponse>("POST", "/api/planner/generate-plan", { event_id: eventId, commit_to_assignments: false });
      setPreviewPlan(generated);
      setActiveStep(1);
      await new Promise((resolve) => setTimeout(resolve, 250));
      setActiveStep(2);
      await api.request("POST", "/api/ml/features/generate", { event_id: eventId, include_event_feature: true, include_resource_features: true });
      const recommended = await api.request<RecommendBestPlanResponse>("POST", "/api/planner/recommend-best-plan", { event_id: eventId, commit_to_assignments: false });
      setRecommendation(recommended);
      setAssignmentDraft(
        recommended.selected_plan.assignment_slots && recommended.selected_plan.assignment_slots.length > 0
          ? recommended.selected_plan.assignment_slots
          : fallbackSlotsFromAssignments(recommended.selected_plan, resourceMap, labelByRequirement),
      );
      setShowOptimized(true);
      setActiveStep(3);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not plan the event. Check resource availability and database readiness.");
    } finally {
      setIsWorking(false);
    }
  };

  const acceptPlan = async (): Promise<void> => {
    setError(null);
    setIsWorking(true);
    try {
      await api.request<RecommendBestPlanResponse>("POST", "/api/planner/recommend-best-plan", {
        event_id: eventId,
        commit_to_assignments: true,
        assignment_overrides: groupedAssignmentOverrides(assignmentDraft),
      });
      setActiveStep(4);
      resetFlow("The optimized plan and reviewed assignments were approved and saved.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not approve the plan.");
    } finally {
      setIsWorking(false);
    }
  };

  const beginAssignmentReview = (): void => {
    if (!recommendation) return;
    setReviewAssignments(true);
    setActiveStep(3);
  };

  const updateAssignmentResource = (index: number, resourceId: string): void => {
    setAssignmentDraft((current) => current.map((item, itemIndex) => {
      if (itemIndex !== index) return item;
      const selected = item.candidate_options.find((option) => option.resource_id === resourceId);
      return {
        ...item,
        selected_resource_id: resourceId || null,
        selected_resource_name: selected?.resource_name || null,
        estimated_cost: selected?.estimated_cost || 0,
      };
    }));
  };

  return (
    <Stack spacing={2.5}>
      <Typography variant="h4">Event planning</Typography>
      {success && <StatusBanner severity="success" title="Plan saved" message={success} />}
      {error && <Alert severity="error">{error}</Alert>}
      <EventSelect label="Event to plan" value={eventId} onChange={handleEventChange} scope="future" />
      {eventId && <EventDetailsCard eventId={eventId} title="Event and requirements before planning" />}
      <Box><Button variant="contained" disabled={!eventId || isWorking} onClick={() => void plan()}>Plan event</Button></Box>
      {(isWorking || previewPlan || recommendation) && <AnimatedPipeline title={isWorking ? "Planning in progress" : "Planning status"} steps={steps} activeStep={activeStep} />}

      {previewPlan && recommendation && !reviewAssignments && (
        <Stack spacing={2}>
          <Paper variant="outlined" sx={{ p: 3, borderRadius: 2, position: "relative", bgcolor: "rgba(15, 118, 110, 0.05)" }}>
            <Stack spacing={2}>
              <BackCornerButton onClick={clearPlanState} />
              <Stack direction={{ xs: "column", md: "row" }} justifyContent="space-between" alignItems={{ xs: "flex-start", md: "center" }} spacing={1.5}>
                <Stack spacing={0.5}>
                  <Typography variant="h6">{showOptimized ? "Optimized plan" : "Baseline ORM planner plan"}</Typography>
                  <Typography color="text.secondary">
                    {showOptimized ? optimizationNarrative(chosenCandidate) : "This is the first feasible plan produced by the ORM planner before ML ranking and profile optimization."}
                  </Typography>
                </Stack>
                <Stack direction="row" spacing={1} alignItems="center">
                  <Typography fontWeight={800}>Baseline</Typography>
                  <Switch checked={showOptimized} onChange={(event) => setShowOptimized(event.target.checked)} />
                  <Typography fontWeight={800}>Optimized</Typography>
                </Stack>
              </Stack>
              <Alert severity="info">
                The cost shown here is the planned resource assignment cost. It is compared with the event budget to show whether the operational plan is heavy or light relative to the full event value.
              </Alert>
              <Grid container spacing={1.5}>
                {metricRows(metricsInView).map((metric) => (
                  <Grid item xs={12} sm={6} md={4} key={metric.label}>
                    <Metric label={metric.label} value={metric.value} helper={metric.helper} />
                  </Grid>
                ))}
              </Grid>
              {recommendation.metric_deltas && (
                <Stack spacing={1}>
                  <Typography fontWeight={900}>Difference versus baseline</Typography>
                  <Grid container spacing={1}>
                    {deltaRows(recommendation.metric_deltas).map((metric) => (
                      <Grid item xs={12} sm={6} md={2} key={metric.label}>
                        <Chip label={`${metric.label}: ${metric.value}`} color={metric.value.startsWith("-") && metric.goodWhen === "negative" ? "success" : metric.value.startsWith("+") && metric.goodWhen === "positive" ? "success" : "default"} variant="outlined" />
                      </Grid>
                    ))}
                  </Grid>
                </Stack>
              )}
              <Stack spacing={0.75}>
                <Typography fontWeight={900}>{showOptimized ? "Optimized resource assignment" : "Baseline resource assignment"}</Typography>
                {planUsage(planInView, resourceMap, labelByRequirement).map((sentence) => <Typography key={sentence} color="text.secondary">{sentence}</Typography>)}
              </Stack>
              {assignmentsIdentical && showOptimized && (
                <Alert severity="info">Baseline was already optimal for the current data, so the optimizer kept the same resources and only recalculated the business risk and quality metrics.</Alert>
              )}
              <Alert severity="info" icon={<CompareArrowsIcon />}>
                Switch between baseline and optimized to compare cost, coverage, risk and assigned resources. Continue only after the optimized result is acceptable as a starting point.
              </Alert>
              <Accordion variant="outlined">
                <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                  <Typography fontWeight={800}>Technical details</Typography>
                </AccordionSummary>
                <AccordionDetails>
                  <Stack spacing={0.5}>
                    <Typography color="text.secondary">Baseline solver: {previewPlan.solver}</Typography>
                    <Typography color="text.secondary">Optimized profile: {candidateTitle(chosenCandidate?.candidate_name)}</Typography>
                    <Typography color="text.secondary">Optimized score: {formatNumber(recommendation.selected_plan_score, 1)} / 100</Typography>
                  </Stack>
                </AccordionDetails>
              </Accordion>
            </Stack>
          </Paper>
          <Stack direction="row" spacing={1}>
            <Button variant="contained" color="success" onClick={beginAssignmentReview} startIcon={<AutoFixHighIcon />}>Next: review resources</Button>
            <Button variant="text" color="warning" onClick={() => resetFlow("Planning was rejected and the view was reset.")}>Reject</Button>
          </Stack>
        </Stack>
      )}

      {recommendation && reviewAssignments && (
        <Paper variant="outlined" sx={{ p: 3, borderRadius: 2, position: "relative" }}>
          <Stack spacing={2}>
            <BackCornerButton onClick={() => setReviewAssignments(false)} />
            <Stack spacing={0.5}>
              <Typography variant="h6">Review resource assignments before final approval</Typography>
              <Typography color="text.secondary">
                Options are sorted by recommendation score. A resource already selected elsewhere in this plan, or already assigned to the event, is removed from other rows to avoid double-booking.
              </Typography>
            </Stack>
            <Alert severity="info">Current review estimate: {formatMoney(reviewEstimate)}. This estimate updates when you change resources.</Alert>
            {assignmentDraft.map((slot, index) => {
              const options = resourceOptions(slot, index, assignmentDraft, existingAssignments);
              return (
                <Paper key={`${slot.requirement_id}-${slot.slot_index}-${index}`} variant="outlined" sx={{ p: 2, borderRadius: 2 }}>
                  <Grid container spacing={2} alignItems="center">
                    <Grid item xs={12} md={3}>
                      <Typography variant="caption" color="text.secondary">Resource slot</Typography>
                      <Typography fontWeight={800}>{slot.business_label || `${labelByRequirement[slot.requirement_id] || humanize(slot.resource_type)} ${slot.slot_index}`}</Typography>
                    </Grid>
                    <Grid item xs={12} md={6}>
                      <TextField select label="Assigned resource" value={slot.selected_resource_id || ""} onChange={(event) => updateAssignmentResource(index, event.target.value)} fullWidth>
                        <MenuItem value="">No resource assigned yet</MenuItem>
                        {options.map((option) => <MenuItem key={option.id} value={option.id}>{option.label} - recommendation {formatNumber(option.score, 0)}% - {formatMoney(option.cost)}</MenuItem>)}
                      </TextField>
                      {slot.selected_resource_id && <Typography variant="caption" color="text.secondary">{options.find((option) => option.id === slot.selected_resource_id)?.note}</Typography>}
                    </Grid>
                    <Grid item xs={12} md={3}>
                      <Typography variant="caption" color="text.secondary">Estimated cost impact</Typography>
                      <Typography fontWeight={800}>{formatMoney(slot.estimated_cost)}</Typography>
                    </Grid>
                  </Grid>
                </Paper>
              );
            })}
            <Stack direction="row" spacing={1}>
              <Button variant="contained" color="success" disabled={isWorking} onClick={() => void acceptPlan()}>Approve final plan</Button>
              <Button variant="outlined" color="warning" onClick={() => resetFlow("Planning was rejected and the view was reset.")}>Reject</Button>
            </Stack>
          </Stack>
        </Paper>
      )}
    </Stack>
  );
}
