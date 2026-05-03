import { useEffect, useMemo, useState } from "react";
import AccessTimeIcon from "@mui/icons-material/AccessTime";
import { Box, Grid, Paper, Stack, Typography } from "@mui/material";

import { navItems } from "../app/navigation";
import { useAuth } from "../lib/auth";
import { daysUntil, formatDateTime } from "../lib/format";
import type { EventItem, ListResponse, LocationItem } from "../types/api";

const descriptions: Record<string, string> = {
  Dashboard: "Szybki przegląd modułów i najbliższych realizacji.",
  "Nowy event": "Wprowadzenie eventu z tekstu przez LLM, korekta arkusza i zapis do bazy.",
  "Planowanie eventów": "Generowanie wariantów planu, optymalizacja i akceptacja wybranego planu.",
  "Replanowanie live": "Obsługa incydentów w trakcie realizacji i decyzja o zmianie planu.",
  "Post-event log": "Podsumowanie po evencie, walidacja danych i finalizacja realizacji.",
  Dane: "Podgląd eventów, lokalizacji i zasobów w tabelach biznesowych.",
  Użytkownicy: "Dodawanie kont i przegląd użytkowników systemu.",
  "Moje konto": "Dane sesji, role oraz administracyjne trenowanie modelu.",
};

export function DashboardPage(): JSX.Element {
  const { api } = useAuth();
  const [events, setEvents] = useState<EventItem[]>([]);
  const [locations, setLocations] = useState<LocationItem[]>([]);

  useEffect(() => {
    const load = async (): Promise<void> => {
      const [eventData, locationData] = await Promise.all([
        api.request<ListResponse<EventItem>>("GET", "/api/events?limit=100"),
        api.request<ListResponse<LocationItem>>("GET", "/api/locations?limit=100"),
      ]);
      setEvents(eventData.items);
      setLocations(locationData.items);
    };
    void load().catch(() => undefined);
  }, [api]);

  const locationById = useMemo(() => new Map(locations.map((location) => [location.location_id, location])), [locations]);
  const upcoming = useMemo(
    () =>
      events
        .filter((event) => new Date(event.planned_start).getTime() >= Date.now())
        .sort((a, b) => new Date(a.planned_start).getTime() - new Date(b.planned_start).getTime())
        .slice(0, 8),
    [events],
  );

  return (
    <Stack spacing={3}>
      <Typography variant="h4">Dashboard</Typography>
      <Grid container spacing={3} alignItems="stretch">
        <Grid item xs={12} lg={6}>
          <Paper variant="outlined" sx={{ p: 3, borderRadius: 2, height: "100%" }}>
            <Typography variant="h6" sx={{ mb: 2 }}>
              Zakładki panelu
            </Typography>
            <Stack spacing={1.5}>
              {navItems.map((item) => (
                <Box key={item.path} sx={{ display: "grid", gridTemplateColumns: "34px 1fr", gap: 1.5 }}>
                  <Box sx={{ color: "primary.main", pt: 0.25 }}>{item.icon}</Box>
                  <Box>
                    <Typography fontWeight={800}>{item.label}</Typography>
                    <Typography variant="body2" color="text.secondary">
                      {descriptions[item.label]}
                    </Typography>
                  </Box>
                </Box>
              ))}
            </Stack>
          </Paper>
        </Grid>
        <Grid item xs={12} lg={6}>
          <Paper variant="outlined" sx={{ p: 3, borderRadius: 2, height: "100%" }}>
            <Typography variant="h6" sx={{ mb: 2 }}>
              Zbliżające się eventy
            </Typography>
            <Stack spacing={1.5}>
              {upcoming.length === 0 ? (
                <Typography color="text.secondary">Brak zaplanowanych przyszłych eventów.</Typography>
              ) : (
                upcoming.map((event) => {
                  const location = locationById.get(event.location_id);
                  return (
                    <Box
                      key={event.event_id}
                      sx={{
                        display: "grid",
                        gridTemplateColumns: "1fr auto",
                        gap: 2,
                        alignItems: "center",
                        borderBottom: "1px solid",
                        borderColor: "divider",
                        pb: 1.5,
                      }}
                    >
                      <Box>
                        <Typography fontWeight={800}>{event.event_name}</Typography>
                        <Typography variant="body2" color="text.secondary">
                          {(location?.name || location?.city || "Miejsce nieuzupełnione") + " · " + formatDateTime(event.planned_start)}
                        </Typography>
                      </Box>
                      <Stack direction="row" spacing={0.75} alignItems="center" color="primary.main">
                        <AccessTimeIcon fontSize="small" />
                        <Typography fontWeight={800}>{daysUntil(event.planned_start)} dni</Typography>
                      </Stack>
                    </Box>
                  );
                })
              )}
            </Stack>
          </Paper>
        </Grid>
      </Grid>
    </Stack>
  );
}
