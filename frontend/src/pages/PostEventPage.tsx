import { useMemo, useState } from "react";
import { Alert, Button, Grid, Stack, TextField, Typography } from "@mui/material";

import { ActionResult } from "../components/ActionResult";
import { JsonEditor } from "../components/JsonEditor";
import { useAuth } from "../lib/auth";
import type { JsonObject } from "../types/api";

export function PostEventPage(): JSX.Element {
  const { api } = useAuth();
  const [eventId, setEventId] = useState("");
  const [summaryText, setSummaryText] = useState("Event zakoñczony na czas, koszt 22000 PLN, brak SLA breach.");
  const [sheetJson, setSheetJson] = useState("{}");
  const [result, setResult] = useState<unknown>(null);
  const [error, setError] = useState<string | null>(null);

  const parseSummary = async (): Promise<void> => {
    setError(null);
    try {
      const data = await api.request<JsonObject>("POST", `/api/runtime/events/${eventId}/post-event/parse`, {
        raw_summary: summaryText,
        prefer_llm: true,
        idempotency_key: `post-parse-${Date.now()}`,
      });
      setSheetJson(JSON.stringify((data as JsonObject).draft_complete ?? {}, null, 2));
      setResult(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "B³¹d parse post-event.");
    }
  };

  const commitSummary = async (): Promise<void> => {
    setError(null);
    try {
      const completion = JSON.parse(sheetJson) as JsonObject;
      const data = await api.request<JsonObject>("POST", `/api/runtime/events/${eventId}/post-event/commit`, {
        completion,
        source_mode: "sheet_review",
        idempotency_key: `post-commit-${Date.now()}`,
      });
      setResult(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "B³¹d commit post-event.");
    }
  };

  return (
    <Stack spacing={2}>
      <Typography variant="h4">Modu³ 4: Logowanie po evencie</Typography>
      <Typography color="text.secondary">Podsumowanie tekstowe -&gt; parse LLM -&gt; arkusz korekty -&gt; commit finalizacji.</Typography>
      {error && <Alert severity="error">{error}</Alert>}
      <TextField label="Event ID" value={eventId} onChange={(e) => setEventId(e.target.value)} />
      <Grid container spacing={2}>
        <Grid item xs={12} md={6}>
          <TextField
            label="Opis podsumowania"
            multiline
            minRows={7}
            value={summaryText}
            onChange={(e) => setSummaryText(e.target.value)}
            fullWidth
          />
          <Button sx={{ mt: 1 }} variant="outlined" onClick={() => void parseSummary()}>
            Parse podsumowania
          </Button>
        </Grid>
        <Grid item xs={12} md={6}>
          <JsonEditor title="Arkusz completion" value={sheetJson} onChange={setSheetJson} minHeight={260} />
          <Button sx={{ mt: 1 }} variant="contained" onClick={() => void commitSummary()}>
            ZatwierdŸ finalizacjê
          </Button>
        </Grid>
      </Grid>
      <ActionResult title="Wynik post-event" result={useMemo(() => result ?? { info: "Brak wyniku" }, [result])} error={error} />
    </Stack>
  );
}