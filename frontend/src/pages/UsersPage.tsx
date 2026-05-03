import { useState } from "react";
import { Alert, Button, Grid, Stack, TextField, Typography } from "@mui/material";

import { ActionResult } from "../components/ActionResult";
import { JsonEditor } from "../components/JsonEditor";
import { useAuth } from "../lib/auth";
import type { JsonObject } from "../types/api";

export function UsersPage(): JSX.Element {
  const { api } = useAuth();
  const [userId, setUserId] = useState("");
  const [createJson, setCreateJson] = useState(
    JSON.stringify(
      {
        username: "operator-ui",
        password: "StrongPass!234",
        roles: ["manager"],
        is_superadmin: false,
      },
      null,
      2,
    ),
  );
  const [updateJson, setUpdateJson] = useState(JSON.stringify({ roles: ["coordinator"], is_active: true }, null, 2));
  const [resetPassword, setResetPassword] = useState("StrongNewPass!234");
  const [result, setResult] = useState<unknown>(null);
  const [error, setError] = useState<string | null>(null);

  const createUser = async (): Promise<void> => {
    setError(null);
    try {
      const payload = JSON.parse(createJson) as JsonObject;
      const data = await api.request<JsonObject>("POST", "/admin/users", payload);
      setResult(data);
      if (typeof (data as JsonObject).user_id === "string") {
        setUserId((data as JsonObject).user_id as string);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "B³¹d tworzenia u¿ytkownika.");
    }
  };

  const updateUser = async (): Promise<void> => {
    setError(null);
    try {
      const payload = JSON.parse(updateJson) as JsonObject;
      setResult(await api.request<JsonObject>("PATCH", `/admin/users/${userId}`, payload));
    } catch (err) {
      setError(err instanceof Error ? err.message : "B³¹d aktualizacji u¿ytkownika.");
    }
  };

  const resetUser = async (): Promise<void> => {
    setError(null);
    try {
      setResult(
        await api.request<JsonObject>("POST", `/admin/users/${userId}/reset-password`, {
          password: resetPassword,
        }),
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "B³¹d resetu has³a.");
    }
  };

  return (
    <Stack spacing={2}>
      <Typography variant="h4">Administracja u¿ytkownikami</Typography>
      {error && <Alert severity="error">{error}</Alert>}
      <TextField label="User ID" value={userId} onChange={(e) => setUserId(e.target.value)} />
      <Grid container spacing={2}>
        <Grid item xs={12} md={6}>
          <JsonEditor title="Create user payload" value={createJson} onChange={setCreateJson} minHeight={220} />
          <Button sx={{ mt: 1 }} variant="contained" onClick={() => void createUser()}>
            Utwórz u¿ytkownika
          </Button>
        </Grid>
        <Grid item xs={12} md={6}>
          <JsonEditor title="Update user payload" value={updateJson} onChange={setUpdateJson} minHeight={220} />
          <Stack direction="row" spacing={1} sx={{ mt: 1 }}>
            <Button variant="outlined" onClick={() => void updateUser()}>
              Aktualizuj
            </Button>
            <TextField
              label="Nowe has³o"
              size="small"
              value={resetPassword}
              onChange={(e) => setResetPassword(e.target.value)}
            />
            <Button variant="outlined" color="secondary" onClick={() => void resetUser()}>
              Reset has³a
            </Button>
          </Stack>
        </Grid>
      </Grid>
      <ActionResult title="Wynik operacji" result={result ?? { info: "Brak wyniku" }} error={error} />
    </Stack>
  );
}