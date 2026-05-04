import { useState } from "react";
import { Alert, Box, Button, Chip, Grid, Paper, Stack, TextField, Typography } from "@mui/material";

import { AnimatedPipeline } from "../components/AnimatedPipeline";
import { EventSelect } from "../components/EventSelect";
import { StatusBanner } from "../components/StatusBanner";
import { useAuth } from "../lib/auth";
import { formatMoney, parserSourceLabel } from "../lib/format";
import { validateBusinessText, validateNonNegativeNumber } from "../lib/validation";
import type { ReplanResponse, RuntimeIncidentParseResponse } from "../types/api";

const replanSteps = ["Analiza zgłoszenia", "Replanowanie", "Porównanie wpływu", "Decyzja", "Akceptacja"];

interface IncidentSheet {
  incident_id?: string;
  incident_type: string;
  severity: string;
  description: string;
  root_cause: string;
  reported_by: string;
  cost_impact: string;
  sla_impact: boolean;
  parser_mode?: string;
  parse_confidence?: number;
}

export function RuntimePage(): JSX.Element {
  const { api } = useAuth();
  const [eventId, setEventId] = useState("");
  const [incidentText, setIncidentText] = useState("Awaria nagłośnienia na sali głównej, opóźnienie około 30 minut, zgłasza Jan.");
  const [sheet, setSheet] = useState<IncidentSheet | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [replanResult, setReplanResult] = useState<ReplanResponse | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [activeStep, setActiveStep] = useState(0);
  const [isWorking, setIsWorking] = useState(false);

  const validateSheet = (): boolean => {
    const next: Record<string, string> = {};
    if (!eventId.trim()) next.eventId = "Wybierz event.";
    if (sheet) {
      const typeError = validateBusinessText(sheet.incident_type, "Typ incydentu");
      if (typeError) next.incident_type = typeError;
      const descriptionError = validateBusinessText(sheet.description, "Opis incydentu");
      if (descriptionError) next.description = descriptionError;
      const reporterError = sheet.reported_by ? validateBusinessText(sheet.reported_by, "Zgłaszający") : null;
      if (reporterError) next.reported_by = reporterError;
      const costError = validateNonNegativeNumber(sheet.cost_impact, "Wpływ kosztowy");
      if (costError) next.cost_impact = costError;
    }
    setFieldErrors(next);
    return Object.keys(next).length === 0;
  };

  const parseIncident = async (): Promise<void> => {
    setError(null);
    setSuccess(null);
    setReplanResult(null);
    if (!eventId.trim()) {
      setFieldErrors({ eventId: "Wybierz event." });
      return;
    }
    setIsWorking(true);
    try {
      const data = await api.request<RuntimeIncidentParseResponse>("POST", `/api/runtime/events/${eventId}/incident/parse`, {
        raw_log: incidentText,
        prefer_llm: true,
        idempotency_key: `incident-${Date.now()}`,
      });
      setSheet({
        incident_id: data.incident_id,
        incident_type: data.incident_type,
        severity: data.severity,
        description: data.description,
        root_cause: data.root_cause || "",
        reported_by: data.reported_by || "",
        cost_impact: data.cost_impact ? String(data.cost_impact) : "",
        sla_impact: data.sla_impact,
        parser_mode: data.parser_mode,
        parse_confidence: data.parse_confidence,
      });
      setFieldErrors({});
    } catch (err) {
      setError(err instanceof Error ? err.message : "Nie udało się przetworzyć incydentu.");
    } finally {
      setIsWorking(false);
    }
  };

  const acceptIncidentAndReplan = async (): Promise<void> => {
    if (!validateSheet() || !sheet) return;
    setError(null);
    setSuccess("Zgłoszenie przyjęte. Uruchamiam replanowanie.");
    setIsWorking(true);
    try {
      setActiveStep(1);
      const data = await api.request<ReplanResponse>("POST", `/api/planner/replan/${eventId}`, {
        incident_id: sheet.incident_id,
        incident_summary: sheet.description,
        commit_to_assignments: false,
        idempotency_key: `replan-${Date.now()}`,
      });
      setReplanResult(data);
      setActiveStep(3);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Nie udało się wykonać replanowania.");
    } finally {
      setIsWorking(false);
    }
  };

  const acceptReplan = async (): Promise<void> => {
    if (!sheet) return;
    setError(null);
    setIsWorking(true);
    try {
      await api.request<ReplanResponse>("POST", `/api/planner/replan/${eventId}`, {
        incident_id: sheet.incident_id,
        incident_summary: sheet.description,
        commit_to_assignments: true,
        idempotency_key: `replan-accept-${Date.now()}`,
      });
      setActiveStep(4);
      setSuccess("Replan został zaakceptowany i zapisany.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Nie udało się zaakceptować replanu.");
    } finally {
      setIsWorking(false);
    }
  };

  return (
    <Stack spacing={2.5}>
      <Typography variant="h4">Replanowanie live</Typography>
      {success && <StatusBanner severity="success" title="Status" message={success} />}
      {error && <Alert severity="error">{error}</Alert>}
      {!sheet && (
        <Paper variant="outlined" sx={{ p: 3, borderRadius: 2 }}>
          <Stack spacing={2}>
            <EventSelect label="Event dla incydentu" value={eventId} onChange={setEventId} scope="runtime" error={Boolean(fieldErrors.eventId)} helperText={fieldErrors.eventId} />
            <TextField label="Opis incydentu" multiline minRows={7} value={incidentText} onChange={(event) => setIncidentText(event.target.value)} fullWidth />
            <Box>
              <Button variant="contained" disabled={!eventId || isWorking} onClick={() => void parseIncident()}>
                Wprowadź
              </Button>
            </Box>
          </Stack>
        </Paper>
      )}
      {sheet && !replanResult && (
        <Paper variant="outlined" sx={{ p: 3, borderRadius: 2 }}>
          <Stack spacing={2}>
            <Stack direction="row" spacing={1} alignItems="center">
              <Typography variant="h6">Arkusz incydentu</Typography>
              <Chip label={parserSourceLabel(sheet.parser_mode)} variant="outlined" color={sheet.parser_mode === "llm" ? "success" : "warning"} />
            </Stack>
            <Grid container spacing={2}>
              <Grid item xs={12} md={4}><TextField label="Typ" value={sheet.incident_type} onChange={(event) => setSheet({ ...sheet, incident_type: event.target.value })} error={Boolean(fieldErrors.incident_type)} helperText={fieldErrors.incident_type} fullWidth /></Grid>
              <Grid item xs={12} md={4}><TextField label="Waga" value={sheet.severity} onChange={(event) => setSheet({ ...sheet, severity: event.target.value })} fullWidth /></Grid>
              <Grid item xs={12} md={4}><TextField label="Zgłaszający" value={sheet.reported_by} onChange={(event) => setSheet({ ...sheet, reported_by: event.target.value })} error={Boolean(fieldErrors.reported_by)} helperText={fieldErrors.reported_by} fullWidth /></Grid>
              <Grid item xs={12}><TextField label="Opis" multiline minRows={4} value={sheet.description} onChange={(event) => setSheet({ ...sheet, description: event.target.value })} error={Boolean(fieldErrors.description)} helperText={fieldErrors.description} fullWidth /></Grid>
              <Grid item xs={12} md={6}><TextField label="Przyczyna" value={sheet.root_cause} onChange={(event) => setSheet({ ...sheet, root_cause: event.target.value })} fullWidth /></Grid>
              <Grid item xs={12} md={6}><TextField label="Wpływ kosztowy" value={sheet.cost_impact} onChange={(event) => setSheet({ ...sheet, cost_impact: event.target.value })} error={Boolean(fieldErrors.cost_impact)} helperText={fieldErrors.cost_impact} fullWidth /></Grid>
            </Grid>
            <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
              <Button variant="outlined" onClick={validateSheet}>Sprawdź</Button>
              <Button variant="contained" color="success" disabled={isWorking || Object.keys(fieldErrors).length > 0} onClick={() => void acceptIncidentAndReplan()}>Przyjmij zgłoszenie</Button>
              <Button variant="text" color="warning" onClick={() => { setSheet(null); setFieldErrors({}); }}>Odrzuć</Button>
            </Stack>
          </Stack>
        </Paper>
      )}
      {(isWorking || replanResult) && <AnimatedPipeline title={isWorking ? "Replanowanie w toku" : "Decyzja replanu"} steps={replanSteps} activeStep={activeStep} />}
      {replanResult && (
        <Paper variant="outlined" sx={{ p: 3, borderRadius: 2 }}>
          <Stack spacing={2}>
            <Typography variant="h6">Rekomendacja replanu</Typography>
            <Typography>{replanResult.comparison.decision_note}</Typography>
            <Typography color="text.secondary">Nowy koszt: {formatMoney(replanResult.comparison.new_cost)}. Zmiana kosztu: {replanResult.comparison.cost_delta ?? "brak danych"}.</Typography>
            <Stack direction="row" spacing={1}>
              <Button variant="contained" color="success" disabled={isWorking} onClick={() => void acceptReplan()}>Akceptuj</Button>
              <Button variant="outlined" color="warning" onClick={() => { setReplanResult(null); setSheet(null); setSuccess("Replan odrzucony przez użytkownika."); }}>Odrzuć</Button>
            </Stack>
          </Stack>
        </Paper>
      )}
    </Stack>
  );
}
