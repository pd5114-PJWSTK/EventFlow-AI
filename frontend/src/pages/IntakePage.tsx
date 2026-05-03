import { useMemo, useState } from "react";
import { Alert, Button, Grid, Stack, TextField, Typography } from "@mui/material";

import { ActionResult } from "../components/ActionResult";
import { JsonEditor } from "../components/JsonEditor";
import { useAuth } from "../lib/auth";
import type { JsonObject } from "../types/api";

const EMPTY_TEXT = `event_name: Gala Firmowa Q3\ncity: Warszawa\nplanned_start: 2026-06-12 10:00\nplanned_end: 2026-06-12 18:00\nrequirement_person_coordinator: 1\nrequirement_vehicle_van: 1`;

export function IntakePage(): JSX.Element {
  const { api } = useAuth();
  const [rawInput, setRawInput] = useState(EMPTY_TEXT);
  const [draftJson, setDraftJson] = useState("{}");
  const [metaJson, setMetaJson] = useState('{"assumptions":[],"parser_mode":"manual_commit","used_fallback":false}');
  const [result, setResult] = useState<unknown>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const prettyResult = useMemo(() => result ?? { info: "Brak wyniku" }, [result]);

  const preview = async (): Promise<void> => {
    setError(null);
    setIsLoading(true);
    try {
      const data = await api.request<JsonObject>("POST", "/api/ai-agents/ingest-event/preview", {
        raw_input: rawInput,
        prefer_langgraph: true,
      });
      setDraftJson(JSON.stringify((data as JsonObject).draft ?? {}, null, 2));
      setMetaJson(
        JSON.stringify(
          {
            assumptions: (data as JsonObject).assumptions ?? [],
            parser_mode: (data as JsonObject).parser_mode ?? "manual_commit",
            used_fallback: (data as JsonObject).used_fallback ?? false,
          },
          null,
          2,
        ),
      );
      setResult(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "B³¹d preview intake.");
    } finally {
      setIsLoading(false);
    }
  };

  const commit = async (): Promise<void> => {
    setError(null);
    setIsLoading(true);
    try {
      const draft = JSON.parse(draftJson) as JsonObject;
      const meta = JSON.parse(metaJson) as JsonObject;
      const data = await api.request<JsonObject>("POST", "/api/ai-agents/ingest-event/commit", {
        draft,
        assumptions: (meta.assumptions as unknown[]) ?? [],
        parser_mode: meta.parser_mode ?? "manual_commit",
        used_fallback: Boolean(meta.used_fallback),
      });
      setResult(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "B³¹d commit intake.");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <Stack spacing={2}>
      <Typography variant="h4">Modu³ 1: Event Intake AI</Typography>
      <Typography color="text.secondary">Tekst -&gt; parse -&gt; arkusz -&gt; commit do bazy.</Typography>
      {error && <Alert severity="error">{error}</Alert>}
      <TextField
        label="Opis eventu"
        multiline
        minRows={7}
        value={rawInput}
        onChange={(event) => setRawInput(event.target.value)}
      />
      <Stack direction="row" spacing={1}>
        <Button variant="contained" onClick={() => void preview()} disabled={isLoading}>
          Preview parse
        </Button>
        <Button variant="outlined" color="secondary" onClick={() => void commit()} disabled={isLoading}>
          Zapisz event
        </Button>
      </Stack>
      <Grid container spacing={2}>
        <Grid item xs={12} md={6}>
          <JsonEditor title="Arkusz draft eventu" value={draftJson} onChange={setDraftJson} minHeight={320} />
        </Grid>
        <Grid item xs={12} md={6}>
          <JsonEditor title="Meta parsera" value={metaJson} onChange={setMetaJson} minHeight={320} />
        </Grid>
      </Grid>
      <ActionResult title="Wynik operacji" result={prettyResult} error={error} />
    </Stack>
  );
}