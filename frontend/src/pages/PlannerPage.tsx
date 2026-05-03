import { useEffect, useMemo, useState } from "react";
import CheckCircleIcon from "@mui/icons-material/CheckCircle";
import { Alert, Box, Button, Card, CardActionArea, CardContent, Chip, Grid, MenuItem, Stack, TextField, Typography } from "@mui/material";

import { AnimatedPipeline } from "../components/AnimatedPipeline";
import { StatusBanner } from "../components/StatusBanner";
import { useAuth } from "../lib/auth";
import { formatDateTime, formatMoney } from "../lib/format";
import type { EventItem, GeneratedPlanResponse, ListResponse, LocationItem, PlanCandidate, RecommendBestPlanResponse } from "../types/api";

const steps = ["Planowanie w toku", "Podgląd planów", "Optymalizacja", "Wybór planu", "Zatwierdzenie"];

function candidateTitle(candidate: PlanCandidate): string {
  return candidate.candidate_name.replace(/_/g, " ");
}

export function PlannerPage(): JSX.Element {
  const { api } = useAuth();
  const [events, setEvents] = useState<EventItem[]>([]);
  const [locations, setLocations] = useState<LocationItem[]>([]);
  const [eventId, setEventId] = useState("");
  const [previewPlan, setPreviewPlan] = useState<GeneratedPlanResponse | null>(null);
  const [recommendation, setRecommendation] = useState<RecommendBestPlanResponse | null>(null);
  const [selectedCandidate, setSelectedCandidate] = useState<string>("");
  const [success, setSuccess] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [activeStep, setActiveStep] = useState(0);
  const [isWorking, setIsWorking] = useState(false);

  useEffect(() => {
    const load = async (): Promise<void> => {
      const [eventData, locationData] = await Promise.all([
        api.request<ListResponse<EventItem>>("GET", "/api/events?limit=100"),
        api.request<ListResponse<LocationItem>>("GET", "/api/locations?limit=100"),
      ]);
      setEvents(eventData.items);
      setLocations(locationData.items);
    };
    void load().catch((err) => setError(err instanceof Error ? err.message : "Nie udało się pobrać eventów."));
  }, [api]);

  const locationById = useMemo(() => new Map(locations.map((location) => [location.location_id, location])), [locations]);
  const futureEvents = useMemo(
    () => events.filter((event) => new Date(event.planned_start).getTime() >= Date.now() && event.status !== "completed"),
    [events],
  );

  const plan = async (): Promise<void> => {
    setError(null);
    setSuccess(null);
    setIsWorking(true);
    setPreviewPlan(null);
    setRecommendation(null);
    setSelectedCandidate("");
    try {
      setActiveStep(0);
      const generated = await api.request<GeneratedPlanResponse>("POST", "/api/planner/generate-plan", {
        event_id: eventId,
        commit_to_assignments: false,
      });
      setPreviewPlan(generated);
      setActiveStep(1);
      await new Promise((resolve) => setTimeout(resolve, 250));
      setActiveStep(2);
      const recommended = await api.request<RecommendBestPlanResponse>("POST", "/api/planner/recommend-best-plan", {
        event_id: eventId,
        commit_to_assignments: false,
      });
      setRecommendation(recommended);
      setSelectedCandidate(recommended.selected_candidate_name);
      setActiveStep(3);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Nie udało się zaplanować eventu.");
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
      });
      setActiveStep(4);
      setSuccess("Event został pozytywnie zaplanowany i zapisany w bazie.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Nie udało się zatwierdzić planu.");
    } finally {
      setIsWorking(false);
    }
  };

  return (
    <Stack spacing={2.5}>
      <Typography variant="h4">Planowanie eventów</Typography>
      {success && <StatusBanner severity="success" title="Plan zapisany" message={success} />}
      {error && <Alert severity="error">{error}</Alert>}
      <TextField
        select
        label="Event do zaplanowania"
        value={eventId}
        onChange={(event) => setEventId(event.target.value)}
        fullWidth
      >
        {futureEvents.map((event) => {
          const location = locationById.get(event.location_id);
          return (
            <MenuItem key={event.event_id} value={event.event_id}>
              {event.event_name} ({location?.name || location?.city || "miejsce nieuzupełnione"}, {formatDateTime(event.planned_start)})
            </MenuItem>
          );
        })}
      </TextField>
      <Box>
        <Button variant="contained" disabled={!eventId || isWorking} onClick={() => void plan()}>
          Zaplanuj
        </Button>
      </Box>
      {(isWorking || previewPlan || recommendation) && (
        <AnimatedPipeline title={isWorking ? "Planowanie w toku" : "Status planowania"} steps={steps} activeStep={activeStep} />
      )}
      {previewPlan && (
        <Card variant="outlined" sx={{ borderRadius: 2 }}>
          <CardContent>
            <Typography variant="h6">Podgląd planu</Typography>
            <Typography color="text.secondary">
              Solver {previewPlan.solver} przygotował plan za {formatMoney(previewPlan.estimated_cost)}. Pokrycie wymagań: {previewPlan.is_fully_assigned ? "pełne" : "częściowe"}.
            </Typography>
          </CardContent>
        </Card>
      )}
      {recommendation && (
        <Stack spacing={2}>
          <StatusBanner
            severity="info"
            title="Najlepszy plan"
            message={recommendation.selected_explanation || "System wybrał plan o najlepszym wyniku łącznym."}
          />
          <Grid container spacing={2}>
            {recommendation.candidates.map((candidate) => {
              const isBest = candidate.candidate_name === recommendation.selected_candidate_name;
              const isSelected = candidate.candidate_name === selectedCandidate;
              return (
                <Grid item xs={12} md={4} key={candidate.candidate_name}>
                  <Card
                    variant="outlined"
                    sx={{
                      height: "100%",
                      borderRadius: 2,
                      borderColor: isSelected ? "primary.main" : isBest ? "success.main" : "divider",
                      bgcolor: isSelected ? "rgba(15, 118, 110, 0.08)" : "background.paper",
                    }}
                  >
                    <CardActionArea onClick={() => setSelectedCandidate(candidate.candidate_name)} sx={{ height: "100%" }}>
                      <CardContent>
                        <Stack spacing={1}>
                          <Stack direction="row" spacing={1} alignItems="center">
                            <Typography variant="h6">{candidateTitle(candidate)}</Typography>
                            {isBest && <Chip size="small" color="success" icon={<CheckCircleIcon />} label="Najlepszy" />}
                          </Stack>
                          <Typography variant="body2" color="text.secondary">Koszt: {formatMoney(candidate.estimated_cost)}</Typography>
                          <Typography variant="body2" color="text.secondary">Czas: {candidate.estimated_duration_minutes} min</Typography>
                          <Typography variant="body2" color="text.secondary">Ryzyko opóźnienia: {candidate.predicted_delay_risk}</Typography>
                          <Typography>{candidate.selection_explanation}</Typography>
                        </Stack>
                      </CardContent>
                    </CardActionArea>
                  </Card>
                </Grid>
              );
            })}
          </Grid>
          <Box>
            <Button variant="contained" color="success" disabled={!selectedCandidate || isWorking} onClick={() => void acceptPlan()}>
              Wybierz
            </Button>
          </Box>
        </Stack>
      )}
    </Stack>
  );
}
