import { useState } from "react";
import CheckCircleIcon from "@mui/icons-material/CheckCircle";
import { Alert, Box, Button, Card, CardActionArea, CardContent, Chip, Grid, Stack, Typography } from "@mui/material";

import { AnimatedPipeline } from "../components/AnimatedPipeline";
import { EventSelect } from "../components/EventSelect";
import { StatusBanner } from "../components/StatusBanner";
import { useAuth } from "../lib/auth";
import { formatDurationMinutes, formatMoney, formatNumber, formatPercent } from "../lib/format";
import { useSessionState } from "../lib/useSessionState";
import type { GeneratedPlanResponse, PlanCandidate, RecommendBestPlanResponse } from "../types/api";

const steps = ["Planning in progress", "Plan preview", "Optimization", "Plan selection", "Approval"];

function candidateTitle(candidate: PlanCandidate): string {
  return candidate.candidate_name.replace(/_/g, " ").replace(/\b\w/g, (char) => char.toUpperCase());
}

function Metric({ label, value }: { label: string; value: string }): JSX.Element {
  return <Stack spacing={0.25}><Typography variant="caption" color="text.secondary" fontWeight={700}>{label}</Typography><Typography fontWeight={800}>{value}</Typography></Stack>;
}

export function PlannerPage(): JSX.Element {
  const { api } = useAuth();
  const [eventId, setEventId] = useSessionState("cp05.planner.eventId", "");
  const [previewPlan, setPreviewPlan] = useSessionState<GeneratedPlanResponse | null>("cp05.planner.preview", null);
  const [recommendation, setRecommendation] = useSessionState<RecommendBestPlanResponse | null>("cp05.planner.recommendation", null);
  const [selectedCandidate, setSelectedCandidate] = useSessionState<string>("cp05.planner.selected", "");
  const [activeStep, setActiveStep] = useSessionState("cp05.planner.activeStep", 0);
  const [success, setSuccess] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isWorking, setIsWorking] = useState(false);

  const resetFlow = (message?: string): void => {
    setEventId("");
    setPreviewPlan(null);
    setRecommendation(null);
    setSelectedCandidate("");
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
      await api.request<RecommendBestPlanResponse>("POST", "/api/planner/recommend-best-plan", { event_id: eventId, commit_to_assignments: true });
      setActiveStep(4);
      resetFlow("The event plan was approved and saved. The planner view has been reset for the next event.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not approve the plan.");
    } finally {
      setIsWorking(false);
    }
  };

  return (
    <Stack spacing={2.5}>
      <Typography variant="h4">Event planning</Typography>
      {success && <StatusBanner severity="success" title="Plan saved" message={success} />}
      {error && <Alert severity="error">{error}</Alert>}
      <EventSelect label="Event to plan" value={eventId} onChange={setEventId} scope="future" />
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
        </Stack></CardContent></Card>
      )}
      {recommendation && (
        <Stack spacing={2}>
          <StatusBanner severity="info" title="Recommended plan" message={recommendation.selected_explanation || "The system selected the plan with the strongest combined score."} />
          <Grid container spacing={2}>
            {recommendation.candidates.map((candidate) => {
              const isBest = candidate.candidate_name === recommendation.selected_candidate_name;
              const isSelected = candidate.candidate_name === selectedCandidate;
              return (
                <Grid item xs={12} md={4} key={candidate.candidate_name}>
                  <Card variant="outlined" sx={{ height: "100%", borderRadius: 2, borderColor: isSelected ? "primary.main" : isBest ? "success.main" : "divider", bgcolor: isSelected ? "rgba(15, 118, 110, 0.08)" : "background.paper" }}>
                    <CardActionArea onClick={() => setSelectedCandidate(candidate.candidate_name)} sx={{ height: "100%" }}>
                      <CardContent><Stack spacing={1.25}>
                        <Stack direction="row" spacing={1} alignItems="center"><Typography variant="h6">{candidateTitle(candidate)}</Typography>{isBest && <Chip size="small" color="success" icon={<CheckCircleIcon />} label="Best" />}</Stack>
                        <Grid container spacing={1.5}>
                          <Grid item xs={6}><Metric label="Cost" value={formatMoney(candidate.estimated_cost)} /></Grid>
                          <Grid item xs={6}><Metric label="Duration" value={formatDurationMinutes(candidate.estimated_duration_minutes)} /></Grid>
                          <Grid item xs={6}><Metric label="Delay risk" value={formatPercent(candidate.predicted_delay_risk)} /></Grid>
                          <Grid item xs={6}><Metric label="Requirement coverage" value={formatPercent(candidate.coverage_ratio)} /></Grid>
                          <Grid item xs={6}><Metric label="Plan score" value={formatNumber(candidate.plan_score, 1)} /></Grid>
                        </Grid>
                        <Typography>{candidate.selection_explanation}</Typography>
                      </Stack></CardContent>
                    </CardActionArea>
                  </Card>
                </Grid>
              );
            })}
          </Grid>
          <Stack direction="row" spacing={1}>
            <Button variant="contained" color="success" disabled={!selectedCandidate || isWorking} onClick={() => void acceptPlan()}>Select plan</Button>
            <Button variant="outlined" onClick={() => setRecommendation(null)}>Back</Button>
            <Button variant="text" color="warning" onClick={() => resetFlow("Planning was rejected and the view was reset.")}>Reject</Button>
          </Stack>
        </Stack>
      )}
    </Stack>
  );
}
