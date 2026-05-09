import { useMemo, useState } from "react";
import AutoFixHighIcon from "@mui/icons-material/AutoFixHigh";
import CompareArrowsIcon from "@mui/icons-material/CompareArrows";
import { Alert, Box, Button, Grid, MenuItem, Paper, Stack, Switch, TextField, Typography } from "@mui/material";

import { AnimatedPipeline } from "../components/AnimatedPipeline";
import { BackCornerButton } from "../components/BackCornerButton";
import { EventDetailsCard } from "../components/EventDetailsCard";
import { EventSelect } from "../components/EventSelect";
import { StatusBanner } from "../components/StatusBanner";
import { useAuth } from "../lib/auth";
import { formatDurationMinutes, formatMoney, formatNumber, formatPercent } from "../lib/format";
import { useSessionState } from "../lib/useSessionState";
import type {
  EquipmentItem,
  EquipmentTypeItem,
  EventAssignmentItem,
  EventRequirementItem,
  GeneratedPlanAssignment,
  GeneratedPlanResponse,
  ListResponse,
  PersonItem,
  PlanCandidate,
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

function Metric({ label, value }: { label: string; value: string }): JSX.Element {
  return (
    <Paper variant="outlined" sx={{ p: 1.5, borderRadius: 999, height: "100%" }}>
      <Typography variant="caption" color="text.secondary" fontWeight={800}>{label}</Typography>
      <Typography fontWeight={900}>{value}</Typography>
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

function baselineMetrics(plan: GeneratedPlanResponse | null): Array<{ label: string; value: string }> {
  if (!plan) return [];
  return [
    { label: "Cost", value: formatMoney(plan.estimated_cost) },
    { label: "Coverage", value: plan.is_fully_assigned ? "Full" : "Partial" },
    { label: "Assignments", value: formatNumber(plan.assignments.reduce((sum, item) => sum + item.resource_ids.length, 0)) },
    { label: "Solver", value: plan.solver },
  ];
}

function optimizedMetrics(candidate: PlanCandidate | undefined, plan: GeneratedPlanResponse | null): Array<{ label: string; value: string }> {
  if (!candidate || !plan) return baselineMetrics(plan);
  return [
    { label: "Profile", value: candidateTitle(candidate.candidate_name) },
    { label: "Cost", value: formatMoney(candidate.estimated_cost) },
    { label: "Duration", value: formatDurationMinutes(candidate.estimated_duration_minutes) },
    { label: "Delay risk", value: formatPercent(candidate.predicted_delay_risk) },
    { label: "Coverage", value: formatPercent(candidate.coverage_ratio) },
    { label: "Score", value: formatNumber(candidate.plan_score, 1) },
  ];
}

function optimizationNarrative(candidate: PlanCandidate | undefined): string {
  if (!candidate) return "The optimized plan keeps the strongest feasible assignment returned by the planner.";
  const profile = candidateTitle(candidate.candidate_name).toLowerCase();
  if (profile.includes("low cost")) return "The optimizer reduced operating cost first while preserving enough coverage to run the event safely.";
  if (profile.includes("reliability")) return "The optimizer preferred resources and timing assumptions that reduce delay and incident risk.";
  if (profile.includes("coverage")) return "The optimizer prioritized filling every critical role and resource gap before cost tuning.";
  return "The optimizer selected a balanced plan because it offers the best mix of cost, coverage and risk for the current event data.";
}

function resourceCost(resourceType: string, resourceId: string, people: PersonItem[], equipment: EquipmentItem[], vehicles: VehicleItem[]): number {
  if (resourceType === "person") return Number(people.find((person) => person.person_id === resourceId)?.cost_per_hour || 0) * 8;
  if (resourceType === "equipment") return Number(equipment.find((item) => item.equipment_id === resourceId)?.hourly_cost_estimate || 0) * 8;
  return Number(vehicles.find((vehicle) => vehicle.vehicle_id === resourceId)?.cost_per_hour || 0) * 4;
}

function resourceOptions(
  assignment: GeneratedPlanAssignment,
  index: number,
  assignmentDraft: GeneratedPlanAssignment[],
  existingAssignments: EventAssignmentItem[],
  people: PersonItem[],
  equipment: EquipmentItem[],
  vehicles: VehicleItem[],
  resourceMap: Record<string, string>,
): Array<{ id: string; label: string; score: number }> {
  const usedInDraft = new Set(
    assignmentDraft.flatMap((item, itemIndex) => itemIndex === index ? [] : item.resource_ids),
  );
  const usedInEvent = new Set(
    existingAssignments.map((item) => item.person_id || item.equipment_id || item.vehicle_id).filter(Boolean) as string[],
  );
  const current = new Set(assignment.resource_ids);
  const baseScore = (position: number, id: string, available = true): number => {
    const selectedBoost = current.has(id) ? 18 : 0;
    const availabilityPenalty = available ? 0 : 25;
    return Math.max(35, 96 - position * 3 + selectedBoost - availabilityPenalty);
  };
  let rows: Array<{ id: string; label: string; score: number; available?: boolean }> = [];
  if (assignment.resource_type === "person") {
    rows = people.map((person, index) => ({
      id: person.person_id,
      label: resourceMap[person.person_id] || person.full_name,
      score: baseScore(index, person.person_id, person.active && person.availability_status === "available"),
    }));
  } else if (assignment.resource_type === "equipment") {
    rows = equipment.map((item, index) => ({
      id: item.equipment_id,
      label: resourceMap[item.equipment_id] || item.asset_tag || "Equipment",
      score: baseScore(index, item.equipment_id, item.active && item.status === "available"),
    }));
  } else {
    rows = vehicles.map((vehicle, index) => ({
      id: vehicle.vehicle_id,
      label: resourceMap[vehicle.vehicle_id] || vehicle.vehicle_name,
      score: baseScore(index, vehicle.vehicle_id, vehicle.active && vehicle.status === "available"),
    }));
  }
  return rows
    .filter((row) => current.has(row.id) || (!usedInDraft.has(row.id) && !usedInEvent.has(row.id)))
    .sort((a, b) => b.score - a.score);
}

export function PlannerPage(): JSX.Element {
  const { api } = useAuth();
  const [eventId, setEventId] = useSessionState("cp05.planner.eventId", "");
  const [previewPlan, setPreviewPlan] = useSessionState<GeneratedPlanResponse | null>("cp05.planner.preview", null);
  const [recommendation, setRecommendation] = useSessionState<RecommendBestPlanResponse | null>("cp05.planner.recommendation", null);
  const [activeStep, setActiveStep] = useSessionState("cp05.planner.activeStep", 0);
  const [resourceMap, setResourceMap] = useSessionState<Record<string, string>>("cp06.planner.resourceMap", {});
  const [people, setPeople] = useSessionState<PersonItem[]>("cp07.planner.people", []);
  const [equipment, setEquipment] = useSessionState<EquipmentItem[]>("cp07.planner.equipment", []);
  const [vehicles, setVehicles] = useSessionState<VehicleItem[]>("cp07.planner.vehicles", []);
  const [requirements, setRequirements] = useSessionState<EventRequirementItem[]>("cp08.planner.requirements", []);
  const [existingAssignments, setExistingAssignments] = useSessionState<EventAssignmentItem[]>("cp08.planner.assignments", []);
  const [equipmentTypeNames, setEquipmentTypeNames] = useSessionState<Record<string, string>>("cp08.planner.equipmentTypeNames", {});
  const [skillNames, setSkillNames] = useSessionState<Record<string, string>>("cp08.planner.skillNames", {});
  const [assignmentDraft, setAssignmentDraft] = useSessionState<GeneratedPlanAssignment[]>("cp07.planner.assignmentDraft", []);
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
  const metricsInView = showOptimized && recommendation ? optimizedMetrics(chosenCandidate, recommendation.selected_plan) : baselineMetrics(previewPlan);
  const reviewEstimate = assignmentDraft.reduce((sum, item) => {
    const selectedCost = item.resource_ids.reduce((resourceSum, resourceId) => resourceSum + resourceCost(item.resource_type, resourceId, people, equipment, vehicles), 0);
    return sum + (selectedCost || Number(item.estimated_cost || 0));
  }, 0);

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
    setPeople(peopleData.items);
    setEquipment(equipmentData.items);
    setVehicles(vehiclesData.items);
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
      setAssignmentDraft(recommended.selected_plan.assignments);
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
        assignment_overrides: assignmentDraft.map((assignment) => ({
          requirement_id: assignment.requirement_id,
          resource_type: assignment.resource_type,
          resource_ids: assignment.resource_ids,
        })),
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
    setAssignmentDraft((current) => current.map((item, itemIndex) => itemIndex === index ? { ...item, resource_ids: resourceId ? [resourceId] : [], estimated_cost: resourceId ? resourceCost(item.resource_type, resourceId, people, equipment, vehicles) : item.estimated_cost } : item));
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
              <Grid container spacing={1.5}>
                {metricsInView.map((metric) => <Grid item xs={12} sm={6} md={3} key={metric.label}><Metric label={metric.label} value={metric.value} /></Grid>)}
              </Grid>
              <Stack spacing={0.75}>
                <Typography fontWeight={900}>{showOptimized ? "Optimized resource assignment" : "Baseline resource assignment"}</Typography>
                {planUsage(planInView, resourceMap, labelByRequirement).map((sentence) => <Typography key={sentence} color="text.secondary">{sentence}</Typography>)}
              </Stack>
              <Alert severity="info" icon={<CompareArrowsIcon />}>
                Switch between baseline and optimized to compare cost, coverage, risk and assigned resources. Continue only after the optimized result is acceptable as a starting point.
              </Alert>
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
            {assignmentDraft.map((assignment, index) => {
              const options = resourceOptions(assignment, index, assignmentDraft, existingAssignments, people, equipment, vehicles, resourceMap);
              const selectedCost = assignment.resource_ids.reduce((sum, resourceId) => sum + resourceCost(assignment.resource_type, resourceId, people, equipment, vehicles), 0);
              return (
                <Paper key={`${assignment.requirement_id}-${index}`} variant="outlined" sx={{ p: 2, borderRadius: 2 }}>
                  <Grid container spacing={2} alignItems="center">
                    <Grid item xs={12} md={3}>
                      <Typography variant="caption" color="text.secondary">Requirement</Typography>
                      <Typography fontWeight={800}>{labelByRequirement[assignment.requirement_id] || humanize(assignment.resource_type)}</Typography>
                    </Grid>
                    <Grid item xs={12} md={6}>
                      <TextField select label="Assigned resource" value={assignment.resource_ids[0] || ""} onChange={(event) => updateAssignmentResource(index, event.target.value)} fullWidth>
                        <MenuItem value="">No resource assigned yet</MenuItem>
                        {options.map((option) => <MenuItem key={option.id} value={option.id}>{option.label} - recommendation {formatNumber(option.score, 0)}%</MenuItem>)}
                      </TextField>
                    </Grid>
                    <Grid item xs={12} md={3}>
                      <Typography variant="caption" color="text.secondary">Estimated cost impact</Typography>
                      <Typography fontWeight={800}>{formatMoney(selectedCost || assignment.estimated_cost)}</Typography>
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
