import { useState } from "react";
import { Alert, Button, Grid, Stack, TextField, Typography } from "@mui/material";

import { ActionResult } from "../components/ActionResult";
import { JsonEditor } from "../components/JsonEditor";
import { useAuth } from "../lib/auth";
import type { JsonObject } from "../types/api";

interface CrudPageProps {
  title: string;
  description: string;
  endpoint: string;
  createTemplate: JsonObject;
}

export function CrudPage({ title, description, endpoint, createTemplate }: CrudPageProps): JSX.Element {
  const { api } = useAuth();
  const [resourceId, setResourceId] = useState("");
  const [payloadJson, setPayloadJson] = useState(JSON.stringify(createTemplate, null, 2));
  const [result, setResult] = useState<unknown>(null);
  const [error, setError] = useState<string | null>(null);

  const call = async (method: "GET" | "POST" | "PATCH" | "DELETE"): Promise<void> => {
    setError(null);
    try {
      const body = method === "GET" || method === "DELETE" ? undefined : JSON.parse(payloadJson);
      const path = resourceId ? `${endpoint}/${resourceId}` : endpoint;
      const data = await api.request<JsonObject>(method, path, body);
      setResult(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "B³¹d operacji CRUD.");
    }
  };

  return (
    <Stack spacing={2}>
      <Typography variant="h4">{title}</Typography>
      <Typography color="text.secondary">{description}</Typography>
      {error && <Alert severity="error">{error}</Alert>}
      <TextField label="ID (opcjonalnie dla GET/PATCH/DELETE)" value={resourceId} onChange={(e) => setResourceId(e.target.value)} />
      <Grid container spacing={2}>
        <Grid item xs={12} md={7}>
          <JsonEditor title="Payload" value={payloadJson} onChange={setPayloadJson} minHeight={260} />
        </Grid>
        <Grid item xs={12} md={5}>
          <Stack spacing={1}>
            <Button variant="outlined" onClick={() => void call("GET")}>GET</Button>
            <Button variant="contained" onClick={() => void call("POST")}>POST</Button>
            <Button variant="outlined" color="secondary" onClick={() => void call("PATCH")}>PATCH</Button>
            <Button variant="outlined" color="error" onClick={() => void call("DELETE")}>DELETE</Button>
          </Stack>
        </Grid>
      </Grid>
      <ActionResult title="Wynik" result={result ?? { info: "Brak wyniku" }} error={error} />
    </Stack>
  );
}