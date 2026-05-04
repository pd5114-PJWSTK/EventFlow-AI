import { useEffect, useMemo, useState } from "react";
import { Alert, CircularProgress, MenuItem, Stack, TextField } from "@mui/material";

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

const CLOSED_STATUSES = new Set(["completed", "cancelled"]);
const POST_EVENT_STATUSES = new Set(["planned", "confirmed", "in_progress"]);

function canUseEvent(event: EventItem, scope: EventScope): boolean {
  if (CLOSED_STATUSES.has(event.status)) {
    return false;
  }
  if (scope === "post-event") {
    return POST_EVENT_STATUSES.has(event.status);
  }
  if (scope === "runtime") {
    return new Date(event.planned_end).getTime() >= Date.now() - 86_400_000;
  }
  return new Date(event.planned_start).getTime() >= Date.now();
}

export function EventSelect({
  value,
  onChange,
  label,
  scope = "future",
  error,
  helperText,
}: EventSelectProps): JSX.Element {
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
        setLoadError(err instanceof Error ? err.message : "Nie udało się pobrać listy eventów.");
      } finally {
        setIsLoading(false);
      }
    };
    void load();
  }, [api]);

  const locationById = useMemo(() => new Map(locations.map((location) => [location.location_id, location])), [locations]);
  const selectableEvents = useMemo(
    () =>
      events
        .filter((event) => canUseEvent(event, scope))
        .sort((a, b) => new Date(a.planned_start).getTime() - new Date(b.planned_start).getTime()),
    [events, scope],
  );

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
        helperText={helperText || (isLoading ? "Ładowanie eventów..." : undefined)}
        InputProps={{
          endAdornment: isLoading ? <CircularProgress size={18} sx={{ mr: 2 }} /> : undefined,
        }}
      >
        {selectableEvents.length === 0 && (
          <MenuItem disabled value="">
            Brak eventów spełniających warunki
          </MenuItem>
        )}
        {selectableEvents.map((event) => {
          const location = locationById.get(event.location_id);
          const place = location?.name || location?.city || "miejsce nieuzupełnione";
          return (
            <MenuItem key={event.event_id} value={event.event_id}>
              {event.event_name} ({place}, {formatDateTime(event.planned_start)})
            </MenuItem>
          );
        })}
      </TextField>
    </Stack>
  );
}
