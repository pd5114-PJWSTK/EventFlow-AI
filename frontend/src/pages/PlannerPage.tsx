import { useMemo, useState } from "react";
import { Alert, Button, Grid, Stack, TextField, Typography } from "@mui/material";

import { ActionResult } from "../components/ActionResult";
import { AnimatedPipeline } from "../components/AnimatedPipeline";
import { JsonEditor } from "../components/JsonEditor";
import { useAuth } from "../lib/auth";
import type { JsonObject } from "../types/api";

const steps = ["Walidacja", "Solver", "Ranking", "Wybór", "Zatwierdzenie"];

export function PlannerPage(): JSX.Element {
  const { api } = useAuth();
  const [eventId, setEventId] = useState("");
  const [resolveJson, setResolveJson] = useState(
    JSON.stringify(
      {
        strategy: "augment_resources",
        add_people: [
          {
            full_name: "Temp Coordinator",
            role: "coordinator",
            cost_per_hour: 120,
          },
        ],
      },
      null,
      2,
    ),
  );
  const [result, setResult] = useState<unknown>(null);
  const [error, setError] = useState<string | null>(null);
  const [activeStep, setActiveStep] = useState(0);

  const run = async (kind: "validate" | "generate" | "recommend" | "preview" | "resolve"): Promise<void> => {
    setError(null);
    try {
      let data: JsonObject;
      if (kind === "validate") {
        setActiveStep(0);
        data = await api.request<JsonObject>("POST", "/api/planner/validate-constraints", { event_id: eventId });
      } else if (kind === "generate") {
        setActiveStep(1);
        data = await api.request<JsonObject>("POST", "/api/planner/generate-plan", {
          event_id: eventId,
          commit_to_assignments: true,
        });
      } else if (kind === "recommend") {
        setActiveStep(3);
        data = await api.request<JsonObject>("POST", "/api/planner/recommend-best-plan", {
          event_id: eventId,
          commit_to_assignments: false,
        });
      } else if (kind === "preview") {
        setActiveStep(2);
        data = await api.request<JsonObject>("POST", `/api/planner/preview-gaps/${eventId}`, {});
      } else {
        setActiveStep(4);
        const payload = JSON.parse(resolveJson) as JsonObject;
        data = await api.request<JsonObject>("POST", `/api/planner/resolve-gaps/${eventId}`, {
          ...payload,
          idempotency_key: `resolve-${Date.now()}`,
        });
      }
      setResult(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "B³¹d plannera.");
    }
  };

  const prettyResult = useMemo(() => result ?? { info: "Brak wyniku" }, [result]);

  return (
    <Stack spacing={2}>
      <Typography variant="h4">Modu³ 2: Planner Studio</Typography>
      <Typography color="text.secondary">Animowany przep³yw generowania i wyboru planu z finalnym zatwierdzeniem.</Typography>
      {error && <Alert severity="error">{error}</Alert>}
      <TextField label="Event ID" value={eventId} onChange={(e) => setEventId(e.target.value)} fullWidth />
      <AnimatedPipeline title="Status procesu planowania" steps={steps} activeStep={activeStep} />
      <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
        <Button variant="outlined" onClick={() => void run("validate")}>Validate</Button>
        <Button variant="contained" onClick={() => void run("generate")}>Generate plan</Button>
        <Button variant="outlined" color="secondary" onClick={() => void run("recommend")}>Recommend best</Button>
        <Button variant="outlined" onClick={() => void run("preview")}>Preview gaps</Button>
      </Stack>
      <Grid container spacing={2}>
        <Grid item xs={12} md={6}>
          <JsonEditor title="Arkusz resolve gaps" value={resolveJson} onChange={setResolveJson} minHeight={260} />
        </Grid>
        <Grid item xs={12} md={6}>
          <Stack spacing={1}>
            <Button variant="contained" color="secondary" onClick={() => void run("resolve")}>
              ZatwierdŸ i resolve gaps
            </Button>
            <Typography color="text.secondary">
              Ten krok reprezentuje finalne zatwierdzenie operatora po analizie luk.
            </Typography>
          </Stack>
        </Grid>
      </Grid>
      <ActionResult title="Wynik Planner Studio" result={prettyResult} error={error} />
    </Stack>
  );
}