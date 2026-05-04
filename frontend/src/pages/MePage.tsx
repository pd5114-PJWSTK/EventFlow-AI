import { useCallback, useEffect, useMemo, useState } from "react";
import { Alert, Box, Button, Chip, Dialog, DialogContent, DialogTitle, Grid, Paper, Stack, Tab, Tabs, Typography } from "@mui/material";

import { AnimatedPipeline } from "../components/AnimatedPipeline";
import { BusinessTable } from "../components/BusinessTable";
import { StatusBanner } from "../components/StatusBanner";
import { useAuth } from "../lib/auth";
import { formatDateTime, formatNumber } from "../lib/format";
import type { ListResponse, LlmStatus, ModelRegistryItem, UserMe } from "../types/api";

const metricLabels: Record<string, string> = {
  mae_minutes: "Mean absolute error",
  rmse_minutes: "RMSE",
  r2: "R-squared",
  samples: "Training samples",
  train_samples: "Train samples",
  test_samples: "Test samples",
  backend: "Backend",
  algorithm: "Algorithm",
};

function titleCaseMetric(key: string): string {
  return key
    .replace(/_/g, " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

function metricValue(key: string, value: unknown): string {
  if (typeof value !== "number") return String(value ?? "No data");
  if (key.includes("r2")) return formatNumber(value, 3);
  if (key.includes("minutes")) return `${formatNumber(value, 1)} min`;
  return formatNumber(value, Number.isInteger(value) ? 0 : 1);
}

function metricRows(metrics: Record<string, unknown>): Array<{ label: string; value: string }> {
  const entries = Object.entries(metrics || {});
  if (entries.length === 0) return [{ label: "Metrics", value: "No metrics" }];
  return entries.map(([key, value]) => ({ label: metricLabels[key] ?? titleCaseMetric(key), value: metricValue(key, value) }));
}

function pickDisplayedModel(models: ModelRegistryItem[]): ModelRegistryItem | undefined {
  return [...models].sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())[0];
}

function llmStatusMessage(status: LlmStatus): string {
  if (status.mode === "llm") return "LLM is enabled and configured for intake and parser flows.";
  if (!status.enabled) return "LLM is disabled; the application is using fallback parsers.";
  return "LLM is enabled, but Azure OpenAI configuration is incomplete.";
}

export function MePage(): JSX.Element {
  const { api, me: contextMe } = useAuth();
  const [activeTab, setActiveTab] = useState(0);
  const [me, setMe] = useState<UserMe | null>(contextMe);
  const [models, setModels] = useState<ModelRegistryItem[]>([]);
  const [llmStatus, setLlmStatus] = useState<LlmStatus | null>(null);
  const [training, setTraining] = useState(false);
  const [metricsDialogModel, setMetricsDialogModel] = useState<ModelRegistryItem | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const isAdmin = Boolean(me?.roles.includes("admin") || me?.is_superadmin);
  const displayedModel = useMemo(() => pickDisplayedModel(models), [models]);

  const load = useCallback(async (): Promise<void> => {
    const meData = await api.request<UserMe>("GET", "/auth/me");
    setMe(meData);
    if (meData.roles.includes("admin") || meData.is_superadmin) {
      const [modelsData, statusData] = await Promise.all([
        api.request<ListResponse<ModelRegistryItem>>("GET", "/api/ml/models?limit=20"),
        api.request<LlmStatus>("GET", "/api/ai-agents/llm-status"),
      ]);
      setModels(modelsData.items);
      setLlmStatus(statusData);
    }
  }, [api]);

  useEffect(() => {
    void load().catch((err) => setError(err instanceof Error ? err.message : "Could not load account data."));
  }, [load]);

  const trainModel = async (): Promise<void> => {
    setTraining(true);
    setError(null);
    setSuccess(null);
    try {
      await api.request("POST", "/api/ml/models/retrain-duration", {
        model_name: displayedModel?.model_name || "event_duration_baseline",
      });
      await load();
      setSuccess("The model was retrained and the model data was refreshed.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not start model training.");
    } finally {
      setTraining(false);
    }
  };

  return (
    <Stack spacing={2.5}>
      <Typography variant="h4">My account</Typography>
      {success && <StatusBanner severity="success" title="Done" message={success} />}
      {error && <Alert severity="error">{error}</Alert>}

      <Box sx={{ borderBottom: 1, borderColor: "divider" }}>
        <Tabs value={activeTab} onChange={(_event, value: number) => setActiveTab(value)}>
          <Tab label="Profile" />
          {isAdmin && <Tab label="ML model" />}
        </Tabs>
      </Box>

      {activeTab === 0 && (
        <Paper variant="outlined" sx={{ p: 3, borderRadius: 2 }}>
          <Grid container spacing={2}>
            <Grid item xs={12} md={4}>
              <Typography color="text.secondary">User</Typography>
              <Typography variant="h6">{me?.username || "No data"}</Typography>
            </Grid>
            <Grid item xs={12} md={4}>
              <Typography color="text.secondary">Roles</Typography>
              <Stack direction="row" spacing={0.5} flexWrap="wrap" useFlexGap>
                {me?.roles.map((role) => <Chip key={role} label={role} />)}
              </Stack>
            </Grid>
            <Grid item xs={12} md={4}>
              <Typography color="text.secondary">Admin access</Typography>
              <Typography variant="h6">{isAdmin ? "Yes" : "No"}</Typography>
            </Grid>
          </Grid>
          <Button sx={{ mt: 3 }} variant="outlined" color="warning" onClick={() => void api.logoutAll()}>
            Log out all sessions
          </Button>
        </Paper>
      )}

      {activeTab === 1 && isAdmin && (
        <Stack spacing={2}>
          {llmStatus && (
            <StatusBanner
              severity={llmStatus.mode === "llm" ? "success" : "warning"}
              title={llmStatus.mode === "llm" ? "LLM active" : "LLM fallback mode"}
              message={llmStatusMessage(llmStatus)}
              source={llmStatus.deployment ? `Deployment: ${llmStatus.deployment}` : undefined}
            />
          )}

          <Paper variant="outlined" sx={{ p: 3, borderRadius: 2 }}>
            <Stack spacing={2}>
              <Box>
                <Typography variant="h6">Operational model</Typography>
                <Typography color="text.secondary">Current duration model used by planning and retraining decisions.</Typography>
              </Box>
            {displayedModel ? (
              <Grid container spacing={2}>
                <Grid item xs={12} md={4}>
                  <Typography color="text.secondary">Name</Typography>
                  <Typography fontWeight={800}>{displayedModel.model_name}</Typography>
                </Grid>
                <Grid item xs={12} md={2}>
                  <Typography color="text.secondary">Version</Typography>
                  <Typography fontWeight={800}>{displayedModel.model_version}</Typography>
                </Grid>
                <Grid item xs={12} md={2}>
                  <Typography color="text.secondary">Status</Typography>
                  <Typography fontWeight={800}>{displayedModel.status}</Typography>
                </Grid>
                <Grid item xs={12} md={4}>
                  <Typography color="text.secondary">Trained at</Typography>
                  <Typography fontWeight={800}>{formatDateTime(displayedModel.created_at)}</Typography>
                </Grid>
                {metricRows(displayedModel.metrics).slice(0, 3).map((metric) => <Grid item xs={12} md={4} key={metric.label}><Paper variant="outlined" sx={{ p: 1.5 }}><Typography variant="caption" color="text.secondary">{metric.label}</Typography><Typography fontWeight={800}>{metric.value}</Typography></Paper></Grid>)}
              </Grid>
            ) : (
              <Typography color="text.secondary">No registered model.</Typography>
            )}
            <Stack direction="row" spacing={1}>
            <Button variant="contained" disabled={training} onClick={() => void trainModel()}>
              Train model
            </Button>
            {displayedModel && <Button variant="outlined" onClick={() => setMetricsDialogModel(displayedModel)}>View metrics</Button>}
            </Stack>
            </Stack>
          </Paper>

          {training && <AnimatedPipeline title="Model training" steps={["Load logs", "Train", "Test", "Update model"]} activeStep={1} />}

          <BusinessTable
            title="Active models"
            rows={models}
            columns={[
              { key: "name", label: "Model", render: (item) => item.model_name },
              { key: "version", label: "Version", render: (item) => item.model_version },
              { key: "type", label: "Prediction type", render: (item) => item.prediction_type },
              { key: "status", label: "Status", render: (item) => item.status },
              { key: "trained", label: "Trained at", render: (item) => formatDateTime(item.created_at) },
              { key: "from", label: "Data from", render: (item) => item.training_data_from ? formatDateTime(item.training_data_from) : "None" },
              { key: "to", label: "Data to", render: (item) => item.training_data_to ? formatDateTime(item.training_data_to) : "None" },
              {
                key: "metrics",
                label: "Metrics",
                render: (item) => <Button size="small" variant="outlined" onClick={() => setMetricsDialogModel(item)}>View details</Button>,
              },
            ]}
          />
          <Dialog open={Boolean(metricsDialogModel)} onClose={() => setMetricsDialogModel(null)} maxWidth="md" fullWidth>
            <DialogTitle>{metricsDialogModel ? `${metricsDialogModel.model_name} metrics` : "Model metrics"}</DialogTitle>
            <DialogContent>
              <Grid container spacing={1.5} sx={{ pt: 1 }}>
                {metricsDialogModel && metricRows(metricsDialogModel.metrics).map((metric) => (
                  <Grid item xs={12} md={4} key={metric.label}>
                    <Paper variant="outlined" sx={{ p: 1.5, height: "100%" }}>
                      <Typography variant="caption" color="text.secondary">{metric.label}</Typography>
                      <Typography fontWeight={800}>{metric.value}</Typography>
                    </Paper>
                  </Grid>
                ))}
              </Grid>
            </DialogContent>
          </Dialog>
        </Stack>
      )}
    </Stack>
  );
}
