import { useMemo, useState } from "react";
import { Alert, Button, Grid, Stack, TextField, Typography } from "@mui/material";

import { ActionResult } from "../components/ActionResult";
import { AnimatedPipeline } from "../components/AnimatedPipeline";
import { JsonEditor } from "../components/JsonEditor";
import { useAuth } from "../lib/auth";
import type { JsonObject } from "../types/api";

const runtimeSteps = ["Rejestracja incydentu", "Parse", "Analiza wp³ywu", "Replan", "Publikacja"];

export function RuntimePage(): JSX.Element {
  const { api } = useAuth();
  const [eventId, setEventId] = useState("");
  const [incidentText, setIncidentText] = useState("Sprzêt audio uleg³ awarii, opóŸnienie 30 min, zg³osi³: Jan.");
  const [replanJson, setReplanJson] = useState('{"incident_summary":"Awaria sprzêtu audio","commit_to_assignments":true}');
  const [result, setResult] = useState<unknown>(null);
  const [error, setError] = useState<string | null>(null);
  const [activeStep, setActiveStep] = useState(0);

  const parseIncident = async (): Promise<void> => {
    setError(null);
    setActiveStep(1);
    try {
      const data = await api.request<JsonObject>("POST", `/api/runtime/events/${eventId}/incident/parse`, {
        raw_log: incidentText,
        prefer_llm: true,
        idempotency_key: `inc-parse-${Date.now()}`,
      });
      setResult(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "B³¹d parse incydentu.");
    }
  };

  const replan = async (): Promise<void> => {
    setError(null);
    setActiveStep(3);
    try {
      const payload = JSON.parse(replanJson) as JsonObject;
      const data = await api.request<JsonObject>("POST", `/api/planner/replan/${eventId}`, {
        ...payload,
        idempotency_key: `replan-${Date.now()}`,
      });
      setResult(data);
      setActiveStep(4);
    } catch (err) {
      setError(err instanceof Error ? err.message : "B³¹d replanowania.");
    }
  };

  return (
    <Stack spacing={2}>
      <Typography variant="h4">Modu³ 3: Runtime + Replan</Typography>
      <Typography color="text.secondary">Osobne okno incydentu live z animacj¹ procesu replanowania.</Typography>
      {error && <Alert severity="error">{error}</Alert>}
      <TextField label="Event ID" value={eventId} onChange={(e) => setEventId(e.target.value)} />
      <AnimatedPipeline title="Przep³yw incydentu i replanu" steps={runtimeSteps} activeStep={activeStep} />
      <Grid container spacing={2}>
        <Grid item xs={12} md={6}>
          <TextField
            label="Opis incydentu"
            multiline
            minRows={6}
            value={incidentText}
            onChange={(e) => setIncidentText(e.target.value)}
            fullWidth
          />
          <Stack direction="row" spacing={1} sx={{ mt: 1 }}>
            <Button variant="outlined" onClick={() => void parseIncident()}>
              Parse incydentu (LLM)
            </Button>
          </Stack>
        </Grid>
        <Grid item xs={12} md={6}>
          <JsonEditor title="Payload replanu" value={replanJson} onChange={setReplanJson} minHeight={220} />
          <Button variant="contained" sx={{ mt: 1 }} onClick={() => void replan()}>
            Uruchom replan
          </Button>
        </Grid>
      </Grid>
      <ActionResult title="Wynik runtime" result={useMemo(() => result ?? { info: "Brak wyniku" }, [result])} error={error} />
    </Stack>
  );
}