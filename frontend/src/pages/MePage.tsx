import { useEffect, useState } from "react";
import { Alert, Button, Paper, Stack, Typography } from "@mui/material";

import { useAuth } from "../lib/auth";
import type { UserMe } from "../types/api";

export function MePage(): JSX.Element {
  const { api } = useAuth();
  const [me, setMe] = useState<UserMe | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const load = async (): Promise<void> => {
      try {
        setMe(await api.request<UserMe>("GET", "/auth/me"));
      } catch (err) {
        setError(err instanceof Error ? err.message : "B³¹d pobierania konta.");
      }
    };
    void load();
  }, [api]);

  return (
    <Stack spacing={2}>
      <Typography variant="h4">Moje konto</Typography>
      {error && <Alert severity="error">{error}</Alert>}
      <Paper sx={{ p: 2 }}>
        <pre style={{ margin: 0 }}>{JSON.stringify(me, null, 2)}</pre>
      </Paper>
      <Button variant="outlined" color="warning" onClick={() => void api.logoutAll()}>
        Wyloguj wszystkie sesje
      </Button>
    </Stack>
  );
}