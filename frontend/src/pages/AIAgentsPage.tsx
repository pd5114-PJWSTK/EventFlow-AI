import { useState } from "react";
import { Alert, Button, Stack, TextField, Typography } from "@mui/material";

import { ActionResult } from "../components/ActionResult";
import { useAuth } from "../lib/auth";
import type { JsonObject } from "../types/api";

export function AIAgentsPage(): JSX.Element {
  const { api } = useAuth();
  const [rawInput, setRawInput] = useState("Potrzebujemy lepszego planu dla eventu nocnego.");
  const [snapshot, setSnapshot] = useState("{}");
  const [result, setResult] = useState<unknown>(null);
  const [error, setError] = useState<string | null>(null);

  const run = async (mode: "optimize" | "evaluate"): Promise<void> => {
    setError(null);
    try {
      const path = mode === "optimize" ? "/api/ai-agents/optimize" : "/api/ai-agents/evaluate";
      const payload =
        mode === "optimize"
          ? { raw_input: rawInput, planner_snapshot: snapshot, prefer_langgraph: true }
          : {
              raw_input: rawInput,
              planner_snapshot: snapshot,
              plan_summary: "Wariant A ma ni¿szy koszt ale wy¿sze ryzyko opóŸnienia.",
              prefer_langgraph: true,
            };
      const data = await api.request<JsonObject>("POST", path, payload);
      setResult(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "B³¹d AI agenta.");
    }
  };

  return (
    <Stack spacing={2}>
      <Typography variant="h4">AI Agents</Typography>
      {error && <Alert severity="error">{error}</Alert>}
      <TextField label="Raw input" multiline minRows={4} value={rawInput} onChange={(e) => setRawInput(e.target.value)} />
      <TextField label="Planner snapshot" multiline minRows={5} value={snapshot} onChange={(e) => setSnapshot(e.target.value)} />
      <Stack direction="row" spacing={1}>
        <Button variant="contained" onClick={() => void run("optimize")}>Optimize</Button>
        <Button variant="outlined" onClick={() => void run("evaluate")}>Evaluate</Button>
      </Stack>
      <ActionResult title="Wynik AI" result={result ?? { info: "Brak wyniku" }} error={error} />
    </Stack>
  );
}