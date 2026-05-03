import { useState } from "react";
import { Alert, Button, Stack, TextField, Typography } from "@mui/material";

import { ActionResult } from "../components/ActionResult";
import { useAuth } from "../lib/auth";
import type { JsonObject } from "../types/api";

export function MLPage(): JSX.Element {
  const { api } = useAuth();
  const [modelName, setModelName] = useState("event_duration_baseline_ui");
  const [result, setResult] = useState<unknown>(null);
  const [error, setError] = useState<string | null>(null);

  const loadRegistry = async (): Promise<void> => {
    setError(null);
    try {
      setResult(await api.request<JsonObject>("GET", "/api/ml/models"));
    } catch (err) {
      setError(err instanceof Error ? err.message : "B³¹d pobierania modeli.");
    }
  };

  const trainBaseline = async (): Promise<void> => {
    setError(null);
    try {
      setResult(
        await api.request<JsonObject>("POST", "/api/ml/models/train-baseline", {
          model_name: modelName,
        }),
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "B³¹d trenowania modelu.");
    }
  };

  return (
    <Stack spacing={2}>
      <Typography variant="h4">ML Console</Typography>
      {error && <Alert severity="error">{error}</Alert>}
      <TextField label="Nazwa modelu" value={modelName} onChange={(e) => setModelName(e.target.value)} />
      <Stack direction="row" spacing={1}>
        <Button variant="outlined" onClick={() => void loadRegistry()}>
          Pobierz rejestr
        </Button>
        <Button variant="contained" onClick={() => void trainBaseline()}>
          Trenuj baseline
        </Button>
      </Stack>
      <ActionResult title="Wynik ML" result={result ?? { info: "Brak wyniku" }} error={error} />
    </Stack>
  );
}