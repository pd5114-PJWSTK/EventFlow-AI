import { useEffect, useMemo, useState } from "react";
import { Alert, Chip, CircularProgress, ListSubheader, MenuItem, Stack, TextField } from "@mui/material";

import { useAuth } from "../lib/auth";
import { formatDateTime } from "../lib/format";
import type { EventItem, ListResponse, LocationItem } from "../types/api";

type EventScope = "future" | "runtime" | "post-event";

interface EventSelectProps {
  value: string;
  onChange: (eventId: string) => void;
  label: string;
  scope?: EventScope;
  error?: boolean;
  helperText?: string;
}

const LIVE_STATUSES = new Set(["confirmed", "in_progress"]);
const FUTURE_STATUSES = new Set(["draft", "submitted", "validated", "planned"]);
const POST_EVENT_STATUSES = new Set(["completed"]);

function canUseEvent(event: EventItem, scope: EventScope): boolean {
  if (scope === "post-event") return POST_EVENT_STATUSES.has(event.status);
  if (scope === "runtime") return LIVE_STATUSES.has(event.status) || (FUTURE_STATUSES.has(event.status) && new Date(event.planned_end).getTime() >= Date.now());
  return FUTURE_STATUSES.has(event.status) && new Date(event.planned_start).getTime() >= Date.now();
}

function sectionFor(event: EventItem, scope: EventScope): string {
  if (scope === "post-event") return "Completed events";
  if (scope === "runtime" && LIVE_STATUSES.has(event.status)) return "Live now";
  if (scope === "runtime") return "Upcoming incidents";
  return "Future events";
}

function chipColor(status: string): "success" | "primary" | "default" {
  if (status === "in_progress" || status === "confirmed") return "success";
  if (status === "completed") return "default";
  return "primary";
}

export function EventSelect({ value, onChange, label, scope = "future", error, helperText }: EventSelectProps): JSX.Element {
  const { api } = useAuth();
  const [events, setEvents] = useState<EventItem[]>([]);
  const [locations, setLocations] = useState<LocationItem[]>([]);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    const load = async (): Promise<void> => {
      setIsLoading(true);
      setLoadError(null);
      try {
        const [eventData, locationData] = await Promise.all([
          api.request<ListResponse<EventItem>>("GET", "/api/events?limit=100"),
          api.request<ListResponse<LocationItem>>("GET", "/api/locations?limit=100"),
        ]);
        setEvents(eventData.items);
        setLocations(locationData.items);
      } catch (err) {
        setLoadError(err instanceof Error ? err.message : "Could not load the event list.");
      } finally {
        setIsLoading(false);
      }
    };
    void load();
  }, [api]);

  const locationById = useMemo(() => new Map(locations.map((location) => [location.location_id, location])), [locations]);
  const selectableEvents = useMemo(
    () => events.filter((event) => canUseEvent(event, scope)).sort((a, b) => new Date(a.planned_start).getTime() - new Date(b.planned_start).getTime()),
    [events, scope],
  );
  const groupedEvents = useMemo(() => {
    const groups = new Map<string, EventItem[]>();
    selectableEvents.forEach((event) => {
      const section = sectionFor(event, scope);
      groups.set(section, [...(groups.get(section) || []), event]);
    });
    return Array.from(groups.entries());
  }, [scope, selectableEvents]);

  return (
    <Stack spacing={1}>
      {loadError && <Alert severity="error">{loadError}</Alert>}
      <TextField
        select
        label={label}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        fullWidth
        error={error}
        helperText={helperText || (isLoading ? "Loading events..." : undefined)}
        InputProps={{ endAdornment: isLoading ? <CircularProgress size={18} sx={{ mr: 2 }} /> : undefined }}
      >
        {selectableEvents.length === 0 && <MenuItem disabled value="">No matching events</MenuItem>}
        {groupedEvents.flatMap(([section, sectionEvents]) => [
          <ListSubheader key={section}>{section}</ListSubheader>,
          ...sectionEvents.map((event) => {
            const location = locationById.get(event.location_id);
            const place = location?.name || location?.city || "venue missing";
            return (
              <MenuItem key={event.event_id} value={event.event_id}>
                <Stack direction="row" spacing={1} alignItems="center" justifyContent="space-between" sx={{ width: "100%" }}>
                  <span>{event.event_name} ({place}, {formatDateTime(event.planned_start)})</span>
                  <Chip size="small" label={event.status.replace(/_/g, " ")} color={chipColor(event.status)} variant="outlined" />
                </Stack>
              </MenuItem>
            );
          }),
        ])}
      </TextField>
    </Stack>
  );
}
