import { useCallback, useEffect, useMemo, useState } from "react";
import { Alert, Box, Button, Chip, Grid, Paper, Stack, Tab, Tabs, Typography } from "@mui/material";

import { AnimatedPipeline } from "../components/AnimatedPipeline";
import { BusinessTable } from "../components/BusinessTable";
import { StatusBanner } from "../components/StatusBanner";
import { useAuth } from "../lib/auth";
import { formatDateTime } from "../lib/format";
import type { ListResponse, LlmStatus, ModelRegistryItem, UserMe } from "../types/api";

function metricText(metrics: Record<string, unknown>): string {
  const entries = Object.entries(metrics || {});
  if (entries.length === 0) return "Brak metryk";
  return entries.map(([key, value]) => `${key}: ${String(value)}`).join(", ");
}

function pickDisplayedModel(models: ModelRegistryItem[]): ModelRegistryItem | undefined {
  const active = models.filter((model) => model.status === "active");
  const pool = active.length > 0 ? active : models;
  return [...pool].sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())[0];
}

export function MePage(): JSX.Element {
  const { api, me: contextMe } = useAuth();
  const [me, setMe] = useState<UserMe | null>(contextMe);
  const [models, setModels] = useState<ModelRegistryItem[]>([]);
  const [llmStatus, setLlmStatus] = useState<LlmStatus | null>(null);
  const [activeTab, setActiveTab] = useState(0);
  const [success, setSuccess] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [training, setTraining] = useState(false);

  const isAdmin = me?.roles.includes("admin") || me?.is_superadmin;
  const displayedModel = useMemo(() => pickDisplayedModel(models), [models]);
  const activeModels = useMemo(() => models.filter((model) => model.status === "active"), [models]);

  const load = useCallback(async (): Promise<void> => {
    const meData = await api.request<UserMe>("GET", "/auth/me");
    setMe(meData);
    if (meData.roles.includes("admin") || meData.is_superadmin) {
      const [modelData, llmData] = await Promise.all([
        api.request<ListResponse<ModelRegistryItem>>("GET", "/api/ml/models?limit=100"),
        api.request<LlmStatus>("GET", "/api/ai-agents/llm-status"),
      ]);
      setModels(modelData.items);
      setLlmStatus(llmData);
    }
  }, [api]);

  useEffect(() => {
    void load().catch((err) => setError(err instanceof Error ? err.message : "Nie udało się pobrać danych konta."));
  }, [load]);

  const trainModel = async (): Promise<void> => {
    setError(null);
    setSuccess(null);
    setTraining(true);
    try {
      await api.request("POST", "/api/ml/models/retrain-duration", {
        model_name: displayedModel?.model_name || "event_duration_baseline",
      });
      await load();
      setSuccess("Model został przetrenowany, a dane modelu odświeżone.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Nie udało się uruchomić treningu modelu.");
    } finally {
      setTraining(false);
    }
  };

  return (
    <Stack spacing={2.5}>
      <Typography variant="h4">Moje konto</Typography>
      {success && <StatusBanner severity="success" title="Gotowe" message={success} />}
      {error && <Alert severity="error">{error}</Alert>}
      <Box sx={{ borderBottom: 1, borderColor: "divider" }}>
        <Tabs value={activeTab} onChange={(_event, value: number) => setActiveTab(value)}>
          <Tab label="Profil" />
          {isAdmin && <Tab label="Model ML" />}
        </Tabs>
      </Box>
      {activeTab === 0 && (
        <Paper variant="outlined" sx={{ p: 3, borderRadius: 2 }}>
          <Grid container spacing={2}>
            <Grid item xs={12} md={4}><Typography color="text.secondary">Użytkownik</Typography><Typography variant="h6">{me?.username || "Brak danych"}</Typography></Grid>
            <Grid item xs={12} md={4}><Typography color="text.secondary">Role</Typography><Stack direction="row" spacing={0.5} flexWrap="wrap" useFlexGap>{me?.roles.map((role) => <Chip key={role} label={role} />)}</Stack></Grid>
            <Grid item xs={12} md={4}><Typography color="text.secondary">Uprawnienia admina</Typography><Typography variant="h6">{isAdmin ? "Tak" : "Nie"}</Typography></Grid>
          </Grid>
          <Button sx={{ mt: 3 }} variant="outlined" color="warning" onClick={() => void api.logoutAll()}>
            Wyloguj wszystkie sesje
          </Button>
        </Paper>
      )}
      {activeTab === 1 && isAdmin && (
        <Stack spacing={2}>
          {llmStatus && (
            <StatusBanner
              severity={llmStatus.mode === "llm" ? "success" : "warning"}
              title={llmStatus.mode === "llm" ? "LLM aktywny" : "LLM w trybie awaryjnym"}
              message={llmStatus.message}
              source={llmStatus.deployment ? `Deployment: ${llmStatus.deployment}` : undefined}
            />
          )}
          <Paper variant="outlined" sx={{ p: 3, borderRadius: 2 }}>
            <Typography variant="h6">Model używany operacyjnie</Typography>
            {displayedModel ? (
              <Grid container spacing={2} sx={{ mt: 0.5 }}>
                <Grid item xs={12} md={3}><Typography color="text.secondary">Nazwa</Typography><Typography fontWeight={800}>{displayedModel.model_name}</Typography></Grid>
                <Grid item xs={12} md={3}><Typography color="text.secondary">Wersja</Typography><Typography fontWeight={800}>{displayedModel.model_version}</Typography></Grid>
                <Grid item xs={12} md={3}><Typography color="text.secondary">Status</Typography><Typography fontWeight={800}>{displayedModel.status}</Typography></Grid>
                <Grid item xs={12} md={3}><Typography color="text.secondary">Trenowany</Typography><Typography fontWeight={800}>{formatDateTime(displayedModel.created_at)}</Typography></Grid>
                <Grid item xs={12}><Typography color="text.secondary">Wyniki</Typography><Typography>{metricText(displayedModel.metrics)}</Typography></Grid>
              </Grid>
            ) : (
              <Typography color="text.secondary">Brak zarejestrowanego modelu.</Typography>
            )}
            <Button sx={{ mt: 3 }} variant="contained" disabled={training} onClick={() => void trainModel()}>
              Trenuj model
            </Button>
          </Paper>
          {training && <AnimatedPipeline title="Trenowanie modelu" steps={["Pobranie logów", "Trening", "Testy", "Aktualizacja modelu"]} activeStep={1} />}
          <BusinessTable
            title="Aktywne modele"
            rows={activeModels.length > 0 ? activeModels : models}
            columns={[
              { key: "name", label: "Model", render: (item) => item.model_name },
              { key: "version", label: "Wersja", render: (item) => item.model_version },
              { key: "type", label: "Typ predykcji", render: (item) => item.prediction_type },
              { key: "status", label: "Status", render: (item) => item.status },
              { key: "trained", label: "Trenowany", render: (item) => formatDateTime(item.created_at) },
              { key: "from", label: "Dane od", render: (item) => item.training_data_from ? formatDateTime(item.training_data_from) : "Brak" },
              { key: "to", label: "Dane do", render: (item) => item.training_data_to ? formatDateTime(item.training_data_to) : "Brak" },
              { key: "metrics", label: "Metryki", render: (item) => metricText(item.metrics) },
            ]}
          />
        </Stack>
      )}
    </Stack>
  );
}
