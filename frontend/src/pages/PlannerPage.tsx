import { type ReactNode, useMemo, useState } from "react";
import AutoFixHighIcon from "@mui/icons-material/AutoFixHigh";
import CompareArrowsIcon from "@mui/icons-material/CompareArrows";
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import InfoOutlinedIcon from "@mui/icons-material/InfoOutlined";
import TimelineIcon from "@mui/icons-material/Timeline";
import { Accordion, AccordionDetails, AccordionSummary, Alert, Box, Button, Chip, Divider, Grid, IconButton, MenuItem, Paper, Stack, Switch, TextField, Tooltip, Typography } from "@mui/material";

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
  GeneratedPlanResponse,
  ListResponse,
  MetricExplanation,
  PersonItem,
  PlanBusinessExplanation,
  PlanCandidate,
  PlanMetricDelta,
  PlanMetrics,
  PlanStageBreakdown,
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

function InfoTip({ title, body, drivers, source }: { title: string; body?: string; drivers?: string[]; source?: PlanBusinessExplanation["source"] }): JSX.Element | null {
  if (!body && (!drivers || drivers.length === 0)) return null;
  return (
    <Tooltip
      arrow
      placement="top"
      title={(
        <Box sx={{ maxWidth: 360, p: 0.5 }}>
          <Typography fontWeight={900} sx={{ mb: 0.75 }}>{title}</Typography>
          {body && <Typography variant="body2" sx={{ lineHeight: 1.55 }}>{body}</Typography>}
          {drivers && drivers.length > 0 && (
            <>
              <Divider sx={{ my: 1, borderColor: "rgba(255,255,255,0.22)" }} />
              <Stack spacing={0.5}>
                {drivers.map((driver) => (
                  <Typography key={driver} variant="caption" sx={{ display: "block", lineHeight: 1.45 }}>- {driver}</Typography>
                ))}
              </Stack>
            </>
          )}
          {source && (
            <Typography variant="caption" sx={{ display: "block", mt: 1, opacity: 0.78 }}>
              {explanationSourceLabel(source)}
            </Typography>
          )}
        </Box>
      )}
      componentsProps={{
        tooltip: {
          sx: {
            bgcolor: "#10201d",
            color: "#f8fffc",
            borderRadius: 1,
            boxShadow: "0 18px 48px rgba(15, 23, 42, 0.28)",
            p: 1.25,
          },
        },
        arrow: { sx: { color: "#10201d" } },
      }}
    >
      <IconButton size="small" aria-label={`${title} explanation`} sx={{ p: 0.35, color: "primary.main", bgcolor: "rgba(13, 148, 136, 0.10)", border: "1px solid rgba(13, 148, 136, 0.18)", "&:hover": { bgcolor: "rgba(13, 148, 136, 0.18)" } }}>
        <InfoOutlinedIcon fontSize="inherit" />
      </IconButton>
    </Tooltip>
  );
}

function Metric({ label, value, explanation, direction, source }: { label: string; value: string; explanation?: MetricExplanation; direction?: "better" | "worse" | "neutral"; source?: PlanBusinessExplanation["source"] }): JSX.Element {
  return (
    <Paper variant="outlined" sx={{ p: 2, borderRadius: 1, height: "100%", minHeight: 132, display: "flex", flexDirection: "column", justifyContent: "space-between", alignItems: "stretch" }}>
      <Stack direction="row" alignItems="center" justifyContent="space-between" spacing={1}>
        <Typography variant="caption" color="text.secondary" fontWeight={800}>{label}</Typography>
        <InfoTip title={label} body={explanation?.summary} drivers={explanation?.drivers} source={source} />
      </Stack>
      <Typography fontWeight={950} variant="h6" sx={{ letterSpacing: -0.2 }}>{value}</Typography>
      {direction && direction !== "neutral" && <Chip size="small" color={direction === "better" ? "success" : "warning"} variant="outlined" label={direction === "better" ? "Improved" : "Watch"} sx={{ alignSelf: "flex-start" }} />}
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

function metricRows(metrics: PlanMetrics | null | undefined): Array<{ key: string; label: string; value: string; helper?: string }> {
  if (!metrics) return [];
  return [
    { key: "event_budget", label: "Event budget", value: metrics.event_budget ? formatMoney(metrics.event_budget) : "Not provided" },
    { key: "estimated_cost", label: "Planned resource cost", value: formatMoney(metrics.estimated_cost) },
    { key: "resource_cost_to_budget_ratio", label: "Resource cost vs budget", value: metrics.resource_cost_to_budget_ratio != null ? formatPercent(metrics.resource_cost_to_budget_ratio) : "No budget data" },
    { key: "estimated_duration_minutes", label: "Estimated duration", value: Number(metrics.estimated_duration_minutes) > 0 ? formatDurationMinutes(metrics.estimated_duration_minutes) : "Calculated in optimized run" },
    { key: "predicted_delay_risk", label: "Delay risk", value: formatPercent(metrics.predicted_delay_risk) },
    { key: "predicted_incident_risk", label: "Incident risk", value: formatPercent(metrics.predicted_incident_risk) },
    { key: "predicted_sla_breach_risk", label: "SLA breach risk", value: formatPercent(metrics.predicted_sla_breach_risk) },
    { key: "coverage_ratio", label: "Requirement coverage", value: formatPercent(metrics.coverage_ratio), helper: "Share of required resource slots that are assigned." },
    { key: "reliability_score", label: "Reliability score", value: formatPercent(metrics.reliability_score), helper: "Average reliability of the assigned resources based on operational history." },
    { key: "backup_coverage_ratio", label: "Backup coverage", value: formatPercent(metrics.backup_coverage_ratio), helper: "Share of slots with at least one alternative resource available." },
    { key: "missing_resource_count", label: "Missing resources", value: formatNumber(metrics.missing_resource_count) },
    { key: "assigned_resource_count", label: "Assigned resources", value: formatNumber(metrics.assigned_resource_count) },
    { key: "optimization_score", label: "Plan quality", value: Number(metrics.optimization_score) > 0 ? `${formatNumber(metrics.optimization_score, 1)} / 100` : "Baseline" },
  ];
}

function explanationMap(explanations?: MetricExplanation[]): Record<string, MetricExplanation> {
  return Object.fromEntries((explanations || []).map((item) => [item.metric_key, item]));
}

function deltaRows(delta?: PlanMetricDelta | null): Array<{ label: string; value: string; goodWhen: "negative" | "positive" }> {
  if (!delta) return [];
  return [
    { label: "Cost", value: signedMoney(delta.estimated_cost), goodWhen: "negative" },
    { label: "Cost vs budget", value: delta.resource_cost_to_budget_ratio != null ? signedPercent(delta.resource_cost_to_budget_ratio) : "No data", goodWhen: "negative" },
    { label: "Duration", value: signedDuration(delta.estimated_duration_minutes), goodWhen: "negative" },
    { label: "Delay risk", value: signedPercent(delta.predicted_delay_risk), goodWhen: "negative" },
    { label: "Incident risk", value: signedPercent(delta.predicted_incident_risk), goodWhen: "negative" },
    { label: "SLA breach risk", value: signedPercent(delta.predicted_sla_breach_risk), goodWhen: "negative" },
    { label: "Coverage", value: signedPercent(delta.coverage_ratio), goodWhen: "positive" },
    { label: "Reliability", value: signedPercent(delta.reliability_score), goodWhen: "positive" },
    { label: "Backup coverage", value: signedPercent(delta.backup_coverage_ratio), goodWhen: "positive" },
    { label: "Plan quality", value: signedNumber(delta.optimization_score), goodWhen: "positive" },
  ];
}

function deltaExplanation(label: string, goodWhen: "negative" | "positive"): string {
  if (goodWhen === "negative") {
    return `${label} is better when the optimized value is lower than baseline. The card shows the optimized change versus the first feasible plan.`;
  }
  return `${label} is better when the optimized value is higher than baseline. The card shows the optimized change versus the first feasible plan.`;
}

function DeltaCard({ label, value, goodWhen, source }: { label: string; value: string; goodWhen: "negative" | "positive"; source?: PlanBusinessExplanation["source"] }): JSX.Element {
  const improved = (value.startsWith("-") && goodWhen === "negative") || (value.startsWith("+") && goodWhen === "positive");
  return (
    <Paper variant="outlined" sx={{ p: 1.5, borderRadius: 1, minHeight: 92, borderColor: improved ? "success.light" : "divider", bgcolor: improved ? "rgba(22, 163, 74, 0.06)" : "background.paper" }}>
      <Stack direction="row" justifyContent="space-between" alignItems="center" spacing={1}>
        <Typography variant="caption" color="text.secondary" fontWeight={800}>{label}</Typography>
        <InfoTip title={`${label} delta`} body={deltaExplanation(label, goodWhen)} source={source} />
      </Stack>
      <Typography fontWeight={950} sx={{ mt: 0.5 }}>{value}</Typography>
      <Typography variant="caption" color={improved ? "success.main" : "text.secondary"}>{improved ? "Improves plan" : "Monitor change"}</Typography>
    </Paper>
  );
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

function explanationSourceLabel(source?: PlanBusinessExplanation["source"]): string {
  return source === "llm" ? "LLM-written explanation" : "Static fallback description";
}

function stageDurationLabel(stage: PlanStageBreakdown): string {
  return formatDurationMinutes(stage.duration_minutes);
}

function optionLogisticsLabel(option: { distance?: string | number | null; travelMinutes?: number | null; logisticsCost: string | number }): string {
  const distance = formatDistance(option.distance);
  const travel = option.travelMinutes != null ? `${formatNumber(option.travelMinutes, 0)} min travel` : "travel time unknown";
  const logistics = Number(option.logisticsCost || 0) > 0 ? `travel and handling ${formatMoney(option.logisticsCost)}` : "no extra travel and handling cost";
  return `${distance}, ${travel}, ${logistics}`;
}

function formatDistance(value?: string | number | null): string {
  if (value === undefined || value === null) return "distance unknown";
  const numeric = Number(value);
  if (Number.isNaN(numeric)) return "distance unknown";
  if (numeric <= 0) return "on-site";
  if (numeric < 1) return `${formatNumber(numeric * 1000, 0)} m`;
  return `${formatNumber(numeric, 1)} km`;
}

function BusinessExplanationPanel({ explanation }: { explanation: PlanBusinessExplanation }): JSX.Element {
  return (
    <Paper variant="outlined" sx={{ p: 2.5, borderRadius: 1, background: "linear-gradient(135deg, rgba(13, 148, 136, 0.08), rgba(14, 165, 233, 0.05))" }}>
      <Stack spacing={1.5}>
        <Stack direction={{ xs: "column", md: "row" }} justifyContent="space-between" alignItems={{ xs: "flex-start", md: "center" }} spacing={1}>
          <Stack spacing={0.4}>
            <Typography variant="overline" color="primary" fontWeight={900}>Planning explanation</Typography>
            <Typography variant="h6" fontWeight={950}>Why optimized is different</Typography>
          </Stack>
          <Chip size="small" variant="outlined" color={explanation.source === "llm" ? "success" : "warning"} label={explanationSourceLabel(explanation.source)} />
        </Stack>
        <Typography color="text.secondary" sx={{ maxWidth: 980 }}>{explanation.summary}</Typography>
        <Typography color="text.secondary" sx={{ maxWidth: 980 }}>{explanation.baseline_vs_optimized}</Typography>
        {explanation.drivers.length > 0 && (
          <Box component="ul" sx={{ m: 0, pl: 2.5 }}>
            {explanation.drivers.map((driver) => (
              <Typography component="li" key={driver} sx={{ mb: 0.5 }} color="text.secondary">
                {driver}
              </Typography>
            ))}
          </Box>
        )}
      </Stack>
    </Paper>
  );
}

function DifferencePanel({ delta, source }: { delta?: PlanMetricDelta | null; source?: PlanBusinessExplanation["source"] }): JSX.Element | null {
  if (!delta) return null;
  return (
    <Paper variant="outlined" sx={{ p: 2, borderRadius: 1 }}>
      <Stack spacing={1.25}>
        <Typography fontWeight={900}>Difference versus baseline</Typography>
        <Box sx={{ display: "grid", gap: 1.25, gridTemplateColumns: { xs: "1fr", sm: "repeat(2, minmax(0, 1fr))", md: "repeat(5, minmax(0, 1fr))" } }}>
          {deltaRows(delta).map((metric) => (
            <DeltaCard key={metric.label} label={metric.label} value={metric.value} goodWhen={metric.goodWhen} source={source} />
          ))}
        </Box>
      </Stack>
    </Paper>
  );
}

function PlanSwitch({ checked, onChange }: { checked: boolean; onChange: (checked: boolean) => void }): JSX.Element {
  return (
    <Stack direction="row" spacing={1} alignItems="center">
      <Typography variant="caption" fontWeight={900}>Baseline</Typography>
      <Switch size="small" checked={checked} onChange={(event) => onChange(event.target.checked)} />
      <Typography variant="caption" fontWeight={900}>Optimized</Typography>
    </Stack>
  );
}

function PlanSection({ title, checked, onChange, children }: { title: string; checked: boolean; onChange: (checked: boolean) => void; children: ReactNode }): JSX.Element {
  return (
    <Paper variant="outlined" sx={{ p: 2, borderRadius: 1 }}>
      <Stack spacing={1.5}>
        <Stack direction={{ xs: "column", sm: "row" }} justifyContent="space-between" alignItems={{ xs: "flex-start", sm: "center" }} spacing={1}>
          <Typography fontWeight={950}>{title}</Typography>
          <PlanSwitch checked={checked} onChange={onChange} />
        </Stack>
        {children}
      </Stack>
    </Paper>
  );
}

function ResourceAssignmentPanel({ plan, source }: { plan: GeneratedPlanResponse | null; source?: PlanBusinessExplanation["source"] }): JSX.Element {
  const slots = plan?.assignment_slots || [];
  const groups = [
    { key: "person", title: "People" },
    { key: "equipment", title: "Equipment" },
    { key: "vehicle", title: "Vehicles" },
  ];
  if (!plan || slots.length === 0) {
    return <Typography color="text.secondary">No resource assignments were generated yet.</Typography>;
  }
  return (
    <Grid container spacing={1.25}>
      {groups.map((group) => {
        const groupSlots = slots.filter((slot) => slot.resource_type === group.key);
        return (
          <Grid item xs={12} md={4} key={group.key}>
            <Paper variant="outlined" sx={{ p: 1.5, borderRadius: 1, height: "100%" }}>
              <Stack spacing={1}>
                <Typography variant="caption" color="text.secondary" fontWeight={900}>{group.title}</Typography>
                {groupSlots.length === 0 && <Typography color="text.secondary">No {group.title.toLowerCase()} assigned.</Typography>}
                {groupSlots.map((slot) => {
                  const selected = slot.candidate_options.find((option) => option.resource_id === slot.selected_resource_id);
                  return (
                    <Paper key={`${slot.requirement_id}-${slot.slot_index}`} variant="outlined" sx={{ p: 1.25, borderRadius: 1 }}>
                      <Stack spacing={0.8}>
                        <Stack direction="row" justifyContent="space-between" alignItems="flex-start" spacing={1}>
                          <Stack spacing={0.25}>
                            <Typography fontWeight={900}>{slot.selected_resource_name || "No resource selected"}</Typography>
                            <Typography variant="caption" color="text.secondary">{slot.business_label}</Typography>
                          </Stack>
                          {selected && <InfoTip title={selected.resource_name} body={selected.why_recommended} drivers={[selected.location_note || optionLogisticsLabel({ distance: selected.distance_to_event_km, travelMinutes: selected.travel_time_minutes, logisticsCost: selected.logistics_cost })]} source={source} />}
                        </Stack>
                        <Grid container spacing={0.75}>
                          <Grid item xs={6}><Typography variant="caption" color="text.secondary">Cost</Typography><Typography fontWeight={800}>{formatMoney(slot.estimated_cost)}</Typography></Grid>
                          <Grid item xs={6}><Typography variant="caption" color="text.secondary">Fit</Typography><Typography fontWeight={800}>{selected ? `${formatNumber(selected.recommendation_score, 0)}%` : "No data"}</Typography></Grid>
                          <Grid item xs={6}><Typography variant="caption" color="text.secondary">Distance</Typography><Typography fontWeight={800}>{selected ? formatDistance(selected.distance_to_event_km) : "No data"}</Typography></Grid>
                          <Grid item xs={6}><Typography variant="caption" color="text.secondary">Travel</Typography><Typography fontWeight={800}>{selected?.travel_time_minutes != null ? `${formatNumber(selected.travel_time_minutes)} min` : "No data"}</Typography></Grid>
                        </Grid>
                      </Stack>
                    </Paper>
                  );
                })}
              </Stack>
            </Paper>
          </Grid>
        );
      })}
    </Grid>
  );
}

function TimelineRail({ stages, source }: { stages: PlanStageBreakdown[]; source?: PlanBusinessExplanation["source"] }): JSX.Element {
  return (
    <Paper variant="outlined" sx={{ p: 2.5, borderRadius: 1 }}>
      <Stack spacing={2}>
        <Stack direction="row" spacing={1} alignItems="center">
          <TimelineIcon color="primary" />
          <Typography fontWeight={950}>Timeline</Typography>
        </Stack>
        <Box sx={{ display: { xs: "none", md: "flex" }, alignItems: "flex-start", width: "100%" }}>
          {stages.map((stage, index) => (
            <Box key={stage.stage_key} sx={{ display: "flex", alignItems: "flex-start", flex: index === stages.length - 1 ? "0 0 auto" : 1, minWidth: 0 }}>
              <Stack alignItems="center" spacing={0.75} sx={{ width: 126, flexShrink: 0 }}>
                <Box sx={{ width: 18, height: 18, borderRadius: "50%", bgcolor: "primary.main", boxShadow: "0 0 0 6px rgba(13, 148, 136, 0.12)" }} />
                <Stack direction="row" spacing={0.5} alignItems="center" justifyContent="center">
                  <Typography fontWeight={900} textAlign="center">{stage.label}</Typography>
                  <InfoTip title={stage.label} body={stage.description} drivers={stage.drivers} source={source} />
                </Stack>
                <Typography variant="caption" color="text.secondary" fontWeight={800}>{stageDurationLabel(stage)}</Typography>
              </Stack>
              {index < stages.length - 1 && (
                <Box sx={{ flex: 1, minWidth: 90, pt: "8px" }}>
                  <Box sx={{ height: 2, bgcolor: "rgba(13, 148, 136, 0.35)", position: "relative" }}>
                    <Box sx={{ position: "absolute", left: "50%", top: -18, transform: "translateX(-50%)", px: 1.1, py: 0.35, borderRadius: 1, bgcolor: "background.paper", border: "1px solid", borderColor: "divider", boxShadow: "0 6px 18px rgba(15, 23, 42, 0.08)", whiteSpace: "nowrap" }}>
                      <Typography variant="caption" fontWeight={900}>{stageDurationLabel(stage)}</Typography>
                    </Box>
                  </Box>
                </Box>
              )}
            </Box>
          ))}
        </Box>
        <Stack spacing={1.25} sx={{ display: { xs: "flex", md: "none" } }}>
          {stages.map((stage) => (
            <Paper key={stage.stage_key} variant="outlined" sx={{ p: 1.5, borderRadius: 1 }}>
              <Stack direction="row" justifyContent="space-between" alignItems="center" spacing={1}>
                <Stack>
                  <Typography fontWeight={900}>{stage.label}</Typography>
                  <Typography variant="caption" color="text.secondary">{stageDurationLabel(stage)}</Typography>
                </Stack>
                <InfoTip title={stage.label} body={stage.description} drivers={stage.drivers} source={source} />
              </Stack>
            </Paper>
          ))}
        </Stack>
      </Stack>
    </Paper>
  );
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
): Array<{ id: string; label: string; score: number; cost: string | number; note: string; distance?: string | number | null; travelMinutes?: number | null; logisticsCost: string | number; locationNote?: string | null }> {
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
      distance: option.distance_to_event_km,
      travelMinutes: option.travel_time_minutes,
      logisticsCost: option.logistics_cost,
      locationNote: option.location_note,
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
        distance_to_event_km: null,
        travel_time_minutes: null,
        logistics_cost: 0,
        location_match_score: 1,
        location_note: "No travel and handling data available for this fallback slot.",
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
  const metricExplanations = explanationMap(recommendation?.business_explanation?.metric_explanations);
  const stagesInView = (showOptimized && recommendation ? recommendation.selected_plan.stage_breakdown : previewPlan?.stage_breakdown) || [];
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
          {recommendation.business_explanation && <BusinessExplanationPanel explanation={recommendation.business_explanation} />}
          <DifferencePanel delta={recommendation.metric_deltas} source={recommendation.business_explanation?.source} />
          <Paper variant="outlined" sx={{ p: 2, borderRadius: 1, position: "relative", bgcolor: "rgba(15, 118, 110, 0.04)" }}>
            <Stack spacing={2}>
              <BackCornerButton onClick={clearPlanState} />
              <Stack spacing={0.5}>
                <Typography variant="h6">{showOptimized ? "Optimized plan" : "Baseline planning draft"}</Typography>
                <Typography color="text.secondary">
                  {showOptimized ? optimizationNarrative(chosenCandidate) : "This is the first feasible plan before resource ranking, risk tuning and travel-aware improvements."}
                </Typography>
              </Stack>
              <Alert severity="info">
                The cost shown here is the planned resource assignment cost. It is compared with the event budget to show whether the operational plan is heavy or light relative to the full event value.
              </Alert>
              <PlanSection title="Core metrics" checked={showOptimized} onChange={setShowOptimized}>
                <Grid container spacing={1.25}>
                  {metricRows(metricsInView).map((metric) => (
                    <Grid item xs={12} sm={6} md={3} key={metric.label}>
                      <Metric
                        label={metric.label}
                        value={metric.value}
                        explanation={metricExplanations[metric.key] || (metric.helper ? { metric_key: metric.key, label: metric.label, summary: metric.helper, drivers: [], delta_direction: "neutral" } : undefined)}
                        direction={metricExplanations[metric.key]?.delta_direction}
                        source={recommendation.business_explanation?.source}
                      />
                    </Grid>
                  ))}
                </Grid>
              </PlanSection>
              <PlanSection title="Timeline" checked={showOptimized} onChange={setShowOptimized}>
                {stagesInView.length > 0 ? <TimelineRail stages={stagesInView} source={recommendation.business_explanation?.source} /> : <Typography color="text.secondary">No timeline available.</Typography>}
              </PlanSection>
              <PlanSection title="Resource assignment" checked={showOptimized} onChange={setShowOptimized}>
                <ResourceAssignmentPanel plan={planInView} source={recommendation.business_explanation?.source} />
              </PlanSection>
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
        <Paper variant="outlined" sx={{ p: 3, borderRadius: 1, position: "relative" }}>
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
              const selectedOption = options.find((option) => option.id === slot.selected_resource_id);
              return (
                <Paper key={`${slot.requirement_id}-${slot.slot_index}-${index}`} variant="outlined" sx={{ p: 2, borderRadius: 1 }}>
                  <Stack spacing={1.25}>
                    <Grid container spacing={2} alignItems="flex-start">
                      <Grid item xs={12} md={4}>
                        <Typography variant="caption" color="text.secondary">Resource slot</Typography>
                        <Typography fontWeight={800}>{slot.business_label || `${labelByRequirement[slot.requirement_id] || humanize(slot.resource_type)} ${slot.slot_index}`}</Typography>
                      </Grid>
                      <Grid item xs={12} md={8}>
                        <TextField select label="Assigned resource" value={slot.selected_resource_id || ""} onChange={(event) => updateAssignmentResource(index, event.target.value)} fullWidth>
                          <MenuItem value="">No resource assigned yet</MenuItem>
                          {options.map((option) => (
                            <MenuItem key={option.id} value={option.id}>
                              {option.label} - {formatNumber(option.score, 0)}% fit - {formatMoney(option.cost)}
                            </MenuItem>
                          ))}
                        </TextField>
                      </Grid>
                    </Grid>
                    <Grid container spacing={1}>
                      <Grid item xs={12} sm={6} md={3}>
                        <Paper variant="outlined" sx={{ p: 1, borderRadius: 1 }}>
                          <Typography variant="caption" color="text.secondary">Fit</Typography>
                          <Typography fontWeight={900}>{selectedOption ? `${formatNumber(selectedOption.score, 0)}%` : "No data"}</Typography>
                        </Paper>
                      </Grid>
                      <Grid item xs={12} sm={6} md={3}>
                        <Paper variant="outlined" sx={{ p: 1, borderRadius: 1 }}>
                          <Typography variant="caption" color="text.secondary">Assignment cost</Typography>
                          <Typography fontWeight={900}>{formatMoney(slot.estimated_cost)}</Typography>
                        </Paper>
                      </Grid>
                      <Grid item xs={12} sm={6} md={3}>
                        <Paper variant="outlined" sx={{ p: 1, borderRadius: 1 }}>
                          <Typography variant="caption" color="text.secondary">Travel</Typography>
                          <Typography fontWeight={900}>{selectedOption?.travelMinutes != null ? `${formatNumber(selectedOption.travelMinutes)} min` : "No data"}</Typography>
                          <Typography variant="caption" color="text.secondary">{selectedOption ? formatDistance(selectedOption.distance) : "Distance unknown"}</Typography>
                        </Paper>
                      </Grid>
                      <Grid item xs={12} sm={6} md={3}>
                        <Paper variant="outlined" sx={{ p: 1, borderRadius: 1 }}>
                          <Stack direction="row" justifyContent="space-between" alignItems="center" spacing={0.5}>
                            <Typography variant="caption" color="text.secondary">Travel & handling</Typography>
                            {selectedOption && <InfoTip title={selectedOption.label} body={selectedOption.note} drivers={[selectedOption.locationNote || optionLogisticsLabel(selectedOption)]} source={recommendation.business_explanation?.source} />}
                          </Stack>
                          <Typography fontWeight={900}>{selectedOption ? formatMoney(selectedOption.logisticsCost) : "No data"}</Typography>
                        </Paper>
                      </Grid>
                    </Grid>
                  </Stack>
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
