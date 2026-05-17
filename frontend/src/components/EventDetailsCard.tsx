import { useEffect, useMemo, useState } from "react";
import { Alert, Chip, Grid, Paper, Stack, Typography } from "@mui/material";

import { useAuth } from "../lib/useAuth";
import { formatDateTime, formatMoney, formatNumber, translateStatus } from "../lib/format";
import type {
  EquipmentTypeItem,
  EventAssignmentItem,
  EventItem,
  EventRequirementItem,
  ListResponse,
  LocationItem,
  SkillItem,
} from "../types/api";

interface EventDetailsCardProps {
  eventId: string;
  title?: string;
}

function humanize(value?: string | null): string {
  return value ? value.replace(/_/g, " ") : "Not specified";
}

function requirementText(
  requirement: EventRequirementItem,
  equipmentTypeNames: Record<string, string>,
  skillNames: Record<string, string>,
): string {
  const quantity = formatNumber(requirement.quantity);
  if (requirement.requirement_type === "person_role") return `${quantity} x ${humanize(requirement.role_required)}`;
  if (requirement.requirement_type === "equipment_type") return `${quantity} x ${equipmentTypeNames[requirement.equipment_type_id || ""] || "equipment"}`;
  if (requirement.requirement_type === "vehicle_type") return `${quantity} x ${humanize(requirement.vehicle_type_required)} vehicle`;
  if (requirement.requirement_type === "person_skill") return `${quantity} x ${skillNames[requirement.skill_id || ""] || "skill"}`;
  return `${quantity} x ${humanize(requirement.requirement_type)}`;
}

function assignmentText(assignment: EventAssignmentItem): string {
  const label = assignment.person_name || assignment.equipment_name || assignment.vehicle_name || "Resource not named";
  const role = assignment.assignment_role ? ` - ${humanize(assignment.assignment_role)}` : "";
  const status = assignment.is_consumed_in_execution ? "done" : translateStatus(assignment.status);
  return `${label}${role} (${status})`;
}

export function EventDetailsCard({ eventId, title = "Selected event" }: EventDetailsCardProps): JSX.Element | null {
  const { api } = useAuth();
  const [event, setEvent] = useState<EventItem | null>(null);
  const [location, setLocation] = useState<LocationItem | null>(null);
  const [requirements, setRequirements] = useState<EventRequirementItem[]>([]);
  const [assignments, setAssignments] = useState<EventAssignmentItem[]>([]);
  const [equipmentTypeNames, setEquipmentTypeNames] = useState<Record<string, string>>({});
  const [skillNames, setSkillNames] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!eventId) {
      setEvent(null);
      setLocation(null);
      setRequirements([]);
      setAssignments([]);
      return;
    }
    const load = async (): Promise<void> => {
      setError(null);
      const eventData = await api.request<EventItem>("GET", `/api/events/${eventId}`);
      const [locationData, requirementData, assignmentData, equipmentTypesData, skillsData] = await Promise.all([
        api.request<LocationItem>("GET", `/api/locations/${eventData.location_id}`),
        api.request<ListResponse<EventRequirementItem>>("GET", `/api/events/${eventId}/requirements?limit=100`),
        api.request<ListResponse<EventAssignmentItem>>("GET", `/api/events/${eventId}/assignments?limit=200`),
        api.request<ListResponse<EquipmentTypeItem>>("GET", "/api/resources/equipment-types?limit=100"),
        api.request<ListResponse<SkillItem>>("GET", "/api/resources/skills?limit=100"),
      ]);
      setEvent(eventData);
      setLocation(locationData);
      setRequirements(requirementData.items);
      setAssignments(assignmentData.items);
      setEquipmentTypeNames(Object.fromEntries(equipmentTypesData.items.map((item) => [item.equipment_type_id, item.type_name])));
      setSkillNames(Object.fromEntries(skillsData.items.map((item) => [item.skill_id, item.skill_name])));
    };
    void load().catch((err) => setError(err instanceof Error ? err.message : "Could not load event details."));
  }, [api, eventId]);

  const requirementSummary = useMemo(
    () => requirements.map((requirement) => requirementText(requirement, equipmentTypeNames, skillNames)),
    [equipmentTypeNames, requirements, skillNames],
  );
  const assignmentSummary = useMemo(() => assignments.map(assignmentText), [assignments]);
  const showAssignments = event ? ["planned", "confirmed", "in_progress", "completed"].includes(event.status) : false;

  if (!eventId) return null;

  return (
    <Paper variant="outlined" sx={{ p: 2.5, borderRadius: 1, bgcolor: "rgba(15, 118, 110, 0.04)" }}>
      <Stack spacing={1.5}>
        <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" useFlexGap>
          <Typography variant="h6">{title}</Typography>
          {event && <Chip label={translateStatus(event.status)} color={event.status === "in_progress" ? "success" : event.status === "completed" ? "default" : "primary"} variant="outlined" />}
        </Stack>
        {error && <Alert severity="warning">{error}</Alert>}
        {event && (
          <>
            <Stack spacing={0.5}>
              <Typography fontWeight={900}>{event.event_name}</Typography>
              <Typography color="text.secondary">
                {location?.name || "Venue not specified"} in {location?.city || "unknown city"} - {formatDateTime(event.planned_start)} to {formatDateTime(event.planned_end)}
              </Typography>
              <Typography>{event.description || event.notes || "No narrative description has been saved for this event yet."}</Typography>
            </Stack>
            <Grid container spacing={1.5}>
              <Grid item xs={6} md={3}><Typography variant="caption" color="text.secondary">Type</Typography><Typography fontWeight={800}>{humanize(event.event_type)}</Typography></Grid>
              <Grid item xs={6} md={3}><Typography variant="caption" color="text.secondary">Priority</Typography><Typography fontWeight={800}>{translateStatus(event.priority)}</Typography></Grid>
              <Grid item xs={6} md={3}><Typography variant="caption" color="text.secondary">Guests</Typography><Typography fontWeight={800}>{formatNumber(event.attendee_count)}</Typography></Grid>
              <Grid item xs={6} md={3}><Typography variant="caption" color="text.secondary">Budget</Typography><Typography fontWeight={800}>{formatMoney(event.budget_estimate)}</Typography></Grid>
            </Grid>
            <Stack spacing={0.75}>
              <Typography fontWeight={800}>{showAssignments ? "Assigned resources" : "Requirements"}</Typography>
              {(showAssignments ? assignmentSummary : requirementSummary).length === 0 ? (
                <Typography color="text.secondary">{showAssignments ? "No assignments saved for this event." : "No requirements saved for this event."}</Typography>
              ) : (
                <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
                  {(showAssignments ? assignmentSummary : requirementSummary).map((item) => <Chip key={item} label={item} />)}
                </Stack>
              )}
            </Stack>
          </>
        )}
      </Stack>
    </Paper>
  );
}
