import { useState } from "react";
import CheckCircleIcon from "@mui/icons-material/CheckCircle";
import { Alert, Box, Button, Card, CardActionArea, CardContent, Chip, Grid, MenuItem, Paper, Stack, TextField, Typography } from "@mui/material";

import { AnimatedPipeline } from "../components/AnimatedPipeline";
import { BackCornerButton } from "../components/BackCornerButton";
import { EventDetailsCard } from "../components/EventDetailsCard";
import { EventSelect } from "../components/EventSelect";
import { StatusBanner } from "../components/StatusBanner";
import { useAuth } from "../lib/auth";
import { formatDurationMinutes, formatMoney, formatNumber, formatPercent } from "../lib/format";
import { useSessionState } from "../lib/useSessionState";
import type { EquipmentItem, GeneratedPlanAssignment, GeneratedPlanResponse, ListResponse, PersonItem, PlanCandidate, RecommendBestPlanResponse, VehicleItem } from "../types/api";

const steps = ["Planning in progress", "Plan preview", "Optimization", "Plan selection", "Approval"];

function candidateTitle(candidate: PlanCandidate): string {
  return candidate.candidate_name.replace(/_/g, " ").replace(/\b\w/g, (char) => char.toUpperCase());
}

function Metric({ label, value }: { label: string; value: string }): JSX.Element {
  return <Stack spacing={0.25}><Typography variant="caption" color="text.secondary" fontWeight={700}>{label}</Typography><Typography fontWeight={800}>{value}</Typography></Stack>;
}

function metricCards(candidate: PlanCandidate): Array<{ label: string; value: string }> {
  return [
    { label: "Cost", value: formatMoney(candidate.estimated_cost) },
    { label: "Duration", value: formatDurationMinutes(candidate.estimated_duration_minutes) },
    { label: "Delay risk", value: formatPercent(candidate.predicted_delay_risk) },
    { label: "Coverage", value: formatPercent(candidate.coverage_ratio) },
    { label: "Open gaps", value: formatNumber(candidate.unassigned_count ?? 0) },
    { label: "Score", value: formatNumber(candidate.plan_score, 1) },
  ];
}

function buildResourceMap(people: PersonItem[], equipment: EquipmentItem[], vehicles: VehicleItem[]): Record<string, string> {
  const map: Record<string, string> = {};
  people.forEach((person) => { map[person.person_id] = `${person.full_name} (${person.role.replace(/_/g, " ")})`; });
  equipment.forEach((item) => { map[item.equipment_id] = item.asset_tag ? `${item.asset_tag}` : `Equipment ${item.equipment_id.slice(0, 8)}`; });
  vehicles.forEach((vehicle) => { map[vehicle.vehicle_id] = `${vehicle.vehicle_name}${vehicle.registration_number ? ` (${vehicle.registration_number})` : ""}`; });
  return map;
}

function assignmentSentence(assignment: GeneratedPlanAssignment, resourceMap: Record<string, string>): string {
  const names = assignment.resource_ids.map((id) => resourceMap[id] || `${assignment.resource_type} ${id.slice(0, 8)}`);
  if (names.length === 0) return `No ${assignment.resource_type.replace(/_/g, " ")} assigned yet; ${assignment.unassigned_count} still open.`;
  const role = assignment.resource_type.replace(/_/g, " ");
  return `${names.join(", ")} will cover the ${role} requirement.`;
}

function planUsage(plan: GeneratedPlanResponse | null, resourceMap: Record<string, string>): string[] {
  if (!plan || plan.assignments.length === 0) return ["No resource assignments were generated yet."];
  return plan.assignments.slice(0, 4).map((assignment) => assignmentSentence(assignment, resourceMap));
}

function planDifference(candidate: PlanCandidate): string {
  const name = candidateTitle(candidate).toLowerCase();
  const cost = formatMoney(candidate.estimated_cost);
  const duration = formatDurationMinutes(candidate.estimated_duration_minutes);
  const risk = formatPercent(candidate.predicted_delay_risk);
  if (name.includes("low cost")) return `This option protects the budget first. It is estimated at ${cost}, but it accepts a longer operating window of ${duration} and a delay risk near ${risk}.`;
  if (name.includes("reliability")) return `This option prioritizes operational reliability. It usually costs more, but it reduces delay and SLA risk when the event has complex logistics.`;
  if (name.includes("coverage")) return `This option focuses on filling every required role and resource before optimizing cost. It is useful when missing assignments would create execution risk.`;
  return `This is the balanced option: it keeps cost, resource coverage and timing risk in the middle, with ${cost}, ${duration} and delay risk around ${risk}.`;
}

function resourceOptions(assignment: GeneratedPlanAssignment, people: PersonItem[], equipment: EquipmentItem[], vehicles: VehicleItem[]): Array<{ id: string; label: string; score: number }> {
  const used = new Set(assignment.resource_ids);
  if (assignment.resource_type === "person") {
    return people.map((person, index) => ({ id: person.person_id, label: `${person.full_name} (${person.role.replace(/_/g, " ")})`, score: used.has(person.person_id) ? 98 : Math.max(62, 92 - index) }));
  }
  if (assignment.resource_type === "equipment") {
    return equipment.map((item, index) => ({ id: item.equipment_id, label: `${item.asset_tag || item.equipment_id.slice(0, 8)} (${item.status.replace(/_/g, " ")})`, score: used.has(item.equipment_id) ? 96 : Math.max(58, 88 - index) }));
  }
  return vehicles.map((vehicle, index) => ({ id: vehicle.vehicle_id, label: `${vehicle.vehicle_name}${vehicle.registration_number ? ` (${vehicle.registration_number})` : ""}`, score: used.has(vehicle.vehicle_id) ? 95 : Math.max(60, 86 - index) }));
}

export function PlannerPage(): JSX.Element {
  const { api } = useAuth();
  const [eventId, setEventId] = useSessionState("cp05.planner.eventId", "");
  const [previewPlan, setPreviewPlan] = useSessionState<GeneratedPlanResponse | null>("cp05.planner.preview", null);
  const [recommendation, setRecommendation] = useSessionState<RecommendBestPlanResponse | null>("cp05.planner.recommendation", null);
  const [selectedCandidate, setSelectedCandidate] = useSessionState<string>("cp05.planner.selected", "");
  const [activeStep, setActiveStep] = useSessionState("cp05.planner.activeStep", 0);
  const [resourceMap, setResourceMap] = useSessionState<Record<string, string>>("cp06.planner.resourceMap", {});
  const [people, setPeople] = useSessionState<PersonItem[]>("cp07.planner.people", []);
  const [equipment, setEquipment] = useSessionState<EquipmentItem[]>("cp07.planner.equipment", []);
  const [vehicles, setVehicles] = useSessionState<VehicleItem[]>("cp07.planner.vehicles", []);
  const [assignmentDraft, setAssignmentDraft] = useSessionState<GeneratedPlanAssignment[]>("cp07.planner.assignmentDraft", []);
  const [reviewAssignments, setReviewAssignments] = useSessionState("cp07.planner.reviewAssignments", false);
  const [success, setSuccess] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isWorking, setIsWorking] = useState(false);

  const resetFlow = (message?: string): void => {
    setEventId("");
    setPreviewPlan(null);
    setRecommendation(null);
    setSelectedCandidate("");
    setResourceMap({});
    setAssignmentDraft([]);
    setReviewAssignments(false);
    setActiveStep(0);
    if (message) setSuccess(message);
  };

  const plan = async (): Promise<void> => {
    setError(null);
    setSuccess(null);
    setIsWorking(true);
    setPreviewPlan(null);
    setRecommendation(null);
    setSelectedCandidate("");
    try {
      setActiveStep(0);
      await api.request("POST", "/api/planner/validate-constraints", { event_id: eventId });
      const generated = await api.request<GeneratedPlanResponse>("POST", "/api/planner/generate-plan", { event_id: eventId, commit_to_assignments: false });
      setPreviewPlan(generated);
      setActiveStep(1);
      await new Promise((resolve) => setTimeout(resolve, 250));
      setActiveStep(2);
      await api.request("POST", "/api/ml/features/generate", { event_id: eventId, include_event_feature: true, include_resource_features: true });
      const recommended = await api.request<RecommendBestPlanResponse>("POST", "/api/planner/recommend-best-plan", { event_id: eventId, commit_to_assignments: false });
      setRecommendation(recommended);
      setSelectedCandidate(recommended.selected_candidate_name);
      const [peopleData, equipmentData, vehiclesData] = await Promise.all([
        api.request<ListResponse<PersonItem>>("GET", "/api/resources/people?limit=100"),
        api.request<ListResponse<EquipmentItem>>("GET", "/api/resources/equipment?limit=100"),
        api.request<ListResponse<VehicleItem>>("GET", "/api/resources/vehicles?limit=100"),
      ]);
      setPeople(peopleData.items);
      setEquipment(equipmentData.items);
      setVehicles(vehiclesData.items);
      setResourceMap(buildResourceMap(peopleData.items, equipmentData.items, vehiclesData.items));
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
      await api.request<RecommendBestPlanResponse>("POST", "/api/planner/recommend-best-plan", { event_id: eventId, commit_to_assignments: true, assignment_overrides: assignmentDraft.map((assignment) => ({ requirement_id: assignment.requirement_id, resource_type: assignment.resource_type, resource_ids: assignment.resource_ids })) });
      setActiveStep(4);
      resetFlow("The event plan was approved and saved. The planner view has been reset for the next event.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not approve the plan.");
    } finally {
      setIsWorking(false);
    }
  };

  const beginAssignmentReview = (): void => {
    if (!recommendation) return;
    setAssignmentDraft(recommendation.selected_plan.assignments);
    setReviewAssignments(true);
    setActiveStep(4);
  };

  const updateAssignmentResource = (index: number, resourceId: string): void => {
    setAssignmentDraft((current) => current.map((item, itemIndex) => itemIndex === index ? { ...item, resource_ids: resourceId ? [resourceId] : [] } : item));
  };

  return (
    <Stack spacing={2.5}>
      <Typography variant="h4">Event planning</Typography>
      {success && <StatusBanner severity="success" title="Plan saved" message={success} />}
      {error && <Alert severity="error">{error}</Alert>}
      <EventSelect label="Event to plan" value={eventId} onChange={setEventId} scope="future" />
      {eventId && <EventDetailsCard eventId={eventId} title="Event and requirements before planning" />}
      <Box><Button variant="contained" disabled={!eventId || isWorking} onClick={() => void plan()}>Plan event</Button></Box>
      {(isWorking || previewPlan || recommendation) && <AnimatedPipeline title={isWorking ? "Planning in progress" : "Planning status"} steps={steps} activeStep={activeStep} />}
      {previewPlan && (
        <Card variant="outlined" sx={{ borderRadius: 2 }}><CardContent><Stack spacing={1.5}>
          <Typography variant="h6">Plan preview</Typography>
          <Grid container spacing={2}>
            <Grid item xs={12} md={3}><Metric label="Estimated cost" value={formatMoney(previewPlan.estimated_cost)} /></Grid>
            <Grid item xs={12} md={3}><Metric label="Coverage" value={previewPlan.is_fully_assigned ? "Full" : "Partial"} /></Grid>
            <Grid item xs={12} md={3}><Metric label="Solver" value={previewPlan.solver} /></Grid>
            <Grid item xs={12} md={3}><Metric label="Assignments" value={formatNumber(previewPlan.assignments.length)} /></Grid>
          </Grid>
          <Stack spacing={0.75}>
            <Typography variant="body2" fontWeight={800}>Initial resource assignment preview</Typography>
            {planUsage(previewPlan, resourceMap).map((sentence) => <Typography key={sentence} variant="body2" color="text.secondary">{sentence}</Typography>)}
          </Stack>
        </Stack></CardContent></Card>
      )}
      {recommendation && !reviewAssignments && (
        <Stack spacing={2}>
          <Paper variant="outlined" sx={{ p: 3, borderRadius: 2, position: "relative", bgcolor: "rgba(15, 118, 110, 0.05)" }}>
            <Stack spacing={2}>
              <BackCornerButton onClick={() => setRecommendation(null)} />
              <Stack spacing={0.5}>
                <Typography variant="h6">Recommended plan</Typography>
                <Typography>{recommendation.selected_explanation || "The system selected the plan with the strongest combined score."}</Typography>
                <Typography color="text.secondary">In business terms: this recommendation balances execution risk, expected cost, available coverage and predicted timing better than the other profiles.</Typography>
              </Stack>
              <Grid container spacing={2}>
                <Grid item xs={6} md={3}><Metric label="Selected profile" value={candidateTitle({ candidate_name: recommendation.selected_candidate_name } as PlanCandidate)} /></Grid>
                <Grid item xs={6} md={3}><Metric label="Estimated cost" value={formatMoney(recommendation.selected_plan.estimated_cost)} /></Grid>
                <Grid item xs={6} md={3}><Metric label="Coverage" value={recommendation.selected_plan.is_fully_assigned ? "Full" : "Partial"} /></Grid>
                <Grid item xs={6} md={3}><Metric label="Assigned resources" value={formatNumber(recommendation.selected_plan.assignments.reduce((sum, item) => sum + item.resource_ids.length, 0))} /></Grid>
              </Grid>
            </Stack>
          </Paper>
          <Grid container spacing={2}>
            {recommendation.candidates.map((candidate) => {
              const isBest = candidate.candidate_name === recommendation.selected_candidate_name;
              const isSelected = candidate.candidate_name === selectedCandidate;
              return (
                <Grid item xs={12} md={6} key={candidate.candidate_name}>
                  <Card variant="outlined" sx={{ height: "100%", borderRadius: 2, borderColor: isSelected ? "primary.main" : isBest ? "success.main" : "divider", bgcolor: isSelected ? "rgba(15, 118, 110, 0.08)" : "background.paper" }}>
                    <CardActionArea onClick={() => setSelectedCandidate(candidate.candidate_name)} sx={{ height: "100%" }}>
                      <CardContent><Stack spacing={1.25}>
                        <Stack direction="row" spacing={1} alignItems="center"><Typography variant="h6">{candidateTitle(candidate)}</Typography>{isBest && <Chip size="small" color="success" icon={<CheckCircleIcon />} label="Best" />}</Stack>
                        <Grid container spacing={1.5}>{metricCards(candidate).map((metric) => <Grid item xs={6} md={4} key={metric.label}><Metric label={metric.label} value={metric.value} /></Grid>)}</Grid>
                        <Typography>{planDifference(candidate)}</Typography>
                        <Stack spacing={0.75}>
                          <Typography variant="body2" fontWeight={800}>How resources will be used</Typography>
                          {planUsage(isBest ? recommendation.selected_plan : previewPlan, resourceMap).map((sentence) => <Typography key={sentence} variant="body2" color="text.secondary">{sentence}</Typography>)}
                        </Stack>
                      </Stack></CardContent>
                    </CardActionArea>
                  </Card>
                </Grid>
              );
            })}
          </Grid>
          <Stack direction="row" spacing={1}>
            <Button variant="contained" color="success" disabled={!selectedCandidate || isWorking} onClick={beginAssignmentReview}>Select plan</Button>
            <Button variant="text" color="warning" onClick={() => resetFlow("Planning was rejected and the view was reset.")}>Reject</Button>
          </Stack>
        </Stack>
      )}
      {recommendation && reviewAssignments && (
        <Paper variant="outlined" sx={{ p: 3, borderRadius: 2, position: "relative" }}>
          <Stack spacing={2}>
            <BackCornerButton onClick={() => setReviewAssignments(false)} />
            <Typography variant="h6">Review resource assignments before final approval</Typography>
            <Typography color="text.secondary">
              Replace missing or unsuitable resources before saving the plan. The recommendation percentage estimates fit using current plan output and resource ordering; higher values should be preferred when there is no operational reason to override them.
            </Typography>
            {assignmentDraft.map((assignment, index) => {
              const options = resourceOptions(assignment, people, equipment, vehicles);
              return (
                <Paper key={`${assignment.requirement_id}-${index}`} variant="outlined" sx={{ p: 2, borderRadius: 2 }}>
                  <Grid container spacing={2} alignItems="center">
                    <Grid item xs={12} md={3}>
                      <Typography variant="caption" color="text.secondary">Requirement</Typography>
                      <Typography fontWeight={800}>{assignment.resource_type.replace(/_/g, " ")} • {assignment.requirement_id.slice(0, 8)}</Typography>
                    </Grid>
                    <Grid item xs={12} md={6}>
                      <TextField select label="Assigned resource" value={assignment.resource_ids[0] || ""} onChange={(event) => updateAssignmentResource(index, event.target.value)} fullWidth>
                        <MenuItem value="">No resource assigned yet</MenuItem>
                        {options.map((option) => <MenuItem key={option.id} value={option.id}>{option.label} • recommendation {option.score}%</MenuItem>)}
                      </TextField>
                    </Grid>
                    <Grid item xs={12} md={3}>
                      <Typography variant="caption" color="text.secondary">Cost share</Typography>
                      <Typography fontWeight={800}>{formatMoney(assignment.estimated_cost)}</Typography>
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
