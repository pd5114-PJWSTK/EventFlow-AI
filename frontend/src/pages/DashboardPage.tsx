import { useEffect, useMemo, useState } from "react";
import AccessTimeIcon from "@mui/icons-material/AccessTime";
import { Box, Chip, Grid, Paper, Stack, Typography } from "@mui/material";

import { navItems } from "../app/navigation";
import { useAuth } from "../lib/useAuth";
import { daysUntil, formatDateTime } from "../lib/format";
import type { EventItem, ListResponse, LocationItem } from "../types/api";

const descriptions: Record<string, string> = {
  Dashboard: "A quick overview of modules and upcoming operations.",
  "New event": "Turn event notes into an AI-assisted sheet, review gaps, and save to the database.",
  "Event planning": "Generate plan variants, optimize them, choose the best option, and approve the plan.",
  "Live replanning": "Log a live incident, run replanning, and approve or reject the recommended change.",
  "Post-event log": "Parse the post-event summary, review the sheet, and close the event with validated data.",
  Data: "Read-only operational tables for events, venues, people, equipment, vehicles, and skills.",
  Users: "Create user accounts and review system users.",
  "My account": "Review your session, roles, LLM status, and admin model retraining tools.",
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
  const live = useMemo(
    () =>
      events
        .filter((event) => event.status === "in_progress" || event.status === "confirmed")
        .sort((a, b) => new Date(a.planned_end).getTime() - new Date(b.planned_end).getTime())
        .slice(0, 6),
    [events],
  );
  const upcoming = useMemo(
    () =>
      events
        .filter((event) => ["draft", "submitted", "validated", "planned"].includes(event.status) && new Date(event.planned_start).getTime() >= Date.now())
        .sort((a, b) => new Date(a.planned_start).getTime() - new Date(b.planned_start).getTime())
        .slice(0, 8),
    [events],
  );

  return (
    <Stack spacing={3}>
      <Typography variant="h4">Dashboard</Typography>
      <Grid container spacing={3} alignItems="stretch">
        <Grid item xs={12} lg={4}>
          <Paper variant="outlined" sx={{ p: 3, borderRadius: 1, height: "100%" }}>
            <Typography variant="h6" sx={{ mb: 2 }}>Console modules</Typography>
            <Stack spacing={1.5}>
              {navItems.map((item) => (
                <Box key={item.path} sx={{ display: "grid", gridTemplateColumns: "34px 1fr", gap: 1.5 }}>
                  <Box sx={{ color: "primary.main", pt: 0.25 }}>{item.icon}</Box>
                  <Box>
                    <Typography fontWeight={800}>{item.label}</Typography>
                    <Typography variant="body2" color="text.secondary">{descriptions[item.label]}</Typography>
                  </Box>
                </Box>
              ))}
            </Stack>
          </Paper>
        </Grid>
        <Grid item xs={12} lg={4}>
          <Paper variant="outlined" sx={{ p: 3, borderRadius: 1, height: "100%" }}>
            <Typography variant="h6" sx={{ mb: 2 }}>Live events</Typography>
            <Stack spacing={1.5}>
              {live.length === 0 ? (
                <Typography color="text.secondary">No event is currently live or confirmed for execution.</Typography>
              ) : (
                live.map((event) => {
                  const location = locationById.get(event.location_id);
                  return (
                    <Box key={event.event_id} sx={{ borderBottom: "1px solid", borderColor: "divider", pb: 1.5 }}>
                      <Stack direction="row" justifyContent="space-between" spacing={1} alignItems="center">
                        <Box>
                          <Typography fontWeight={800}>{event.event_name}</Typography>
                          <Typography variant="body2" color="text.secondary">
                            {(location?.name || location?.city || "Venue missing") + " - ends " + formatDateTime(event.planned_end)}
                          </Typography>
                        </Box>
                        <Chip label={event.status.replace(/_/g, " ")} color="success" variant="outlined" />
                      </Stack>
                    </Box>
                  );
                })
              )}
            </Stack>
          </Paper>
        </Grid>
        <Grid item xs={12} lg={4}>
          <Paper variant="outlined" sx={{ p: 3, borderRadius: 1, height: "100%" }}>
            <Typography variant="h6" sx={{ mb: 2 }}>Upcoming events</Typography>
            <Stack spacing={1.5}>
              {upcoming.length === 0 ? (
                <Typography color="text.secondary">No upcoming planned events.</Typography>
              ) : (
                upcoming.map((event) => {
                  const location = locationById.get(event.location_id);
                  return (
                    <Box key={event.event_id} sx={{ display: "grid", gridTemplateColumns: "1fr auto", gap: 2, alignItems: "center", borderBottom: "1px solid", borderColor: "divider", pb: 1.5 }}>
                      <Box>
                        <Typography fontWeight={800}>{event.event_name}</Typography>
                        <Typography variant="body2" color="text.secondary">
                          {(location?.name || location?.city || "Venue missing") + " - " + formatDateTime(event.planned_start)}
                        </Typography>
                      </Box>
                      <Stack direction="row" spacing={0.75} alignItems="center" color="primary.main">
                        <AccessTimeIcon fontSize="small" />
                        <Typography fontWeight={800}>{daysUntil(event.planned_start)} days</Typography>
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
