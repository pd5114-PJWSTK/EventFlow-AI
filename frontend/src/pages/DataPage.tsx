import { useEffect, useState } from "react";
import { Alert, Box, Stack, Tab, Tabs, Typography } from "@mui/material";

import { BusinessTable } from "../components/BusinessTable";
import { useAuth } from "../lib/auth";
import { formatDateTime, formatMoney, translateStatus } from "../lib/format";
import type {
  EquipmentItem,
  EquipmentTypeItem,
  EventItem,
  ListResponse,
  LocationItem,
  PersonItem,
  SkillItem,
  VehicleItem,
} from "../types/api";

const tabs = ["Events", "Locations", "People", "Equipment", "Equipment types", "Vehicles", "Skills"];

function text(value: unknown): string {
  if (value === undefined || value === null || value === "") return "None";
  if (typeof value === "boolean") return value ? "Yes" : "No";
  return String(value);
}

function date(value?: string | null): string {
  return value ? formatDateTime(value) : "None";
}

function ref(prefix: string, value?: string | null): string {
  if (!value) return "None";
  return `${prefix}-${value.slice(0, 8).toUpperCase()} (${value})`;
}

export function DataPage(): JSX.Element {
  const { api } = useAuth();
  const [activeTab, setActiveTab] = useState(0);
  const [events, setEvents] = useState<EventItem[]>([]);
  const [locations, setLocations] = useState<LocationItem[]>([]);
  const [people, setPeople] = useState<PersonItem[]>([]);
  const [equipment, setEquipment] = useState<EquipmentItem[]>([]);
  const [equipmentTypes, setEquipmentTypes] = useState<EquipmentTypeItem[]>([]);
  const [vehicles, setVehicles] = useState<VehicleItem[]>([]);
  const [skills, setSkills] = useState<SkillItem[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const load = async (): Promise<void> => {
      setError(null);
      try {
        const [eventsData, locationsData, peopleData, equipmentData, equipmentTypesData, vehiclesData, skillsData] =
          await Promise.all([
            api.request<ListResponse<EventItem>>("GET", "/api/events?limit=100"),
            api.request<ListResponse<LocationItem>>("GET", "/api/locations?limit=100"),
            api.request<ListResponse<PersonItem>>("GET", "/api/resources/people?limit=100"),
            api.request<ListResponse<EquipmentItem>>("GET", "/api/resources/equipment?limit=100"),
            api.request<ListResponse<EquipmentTypeItem>>("GET", "/api/resources/equipment-types?limit=100"),
            api.request<ListResponse<VehicleItem>>("GET", "/api/resources/vehicles?limit=100"),
            api.request<ListResponse<SkillItem>>("GET", "/api/resources/skills?limit=100"),
          ]);
        setEvents(eventsData.items);
        setLocations(locationsData.items);
        setPeople(peopleData.items);
        setEquipment(equipmentData.items);
        setEquipmentTypes(equipmentTypesData.items);
        setVehicles(vehiclesData.items);
        setSkills(skillsData.items);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Could not load data.");
      }
    };
    void load();
  }, [api]);

  return (
    <Stack spacing={2}>
      <Typography variant="h4">Data</Typography>
      {error && <Alert severity="error">{error}</Alert>}
      <Box sx={{ borderBottom: 1, borderColor: "divider" }}>
        <Tabs value={activeTab} onChange={(_event, value: number) => setActiveTab(value)} variant="scrollable">
          {tabs.map((tab) => (
            <Tab key={tab} label={tab} />
          ))}
        </Tabs>
      </Box>
      {activeTab === 0 && (
        <BusinessTable
          rows={events}
          columns={[
            { key: "event_id", label: "Event ID", render: (item) => ref("EVT", item.event_id) },
            { key: "client_id", label: "Client ID", render: (item) => ref("CLI", item.client_id) },
            { key: "location_id", label: "Location ID", render: (item) => ref("LOC", item.location_id) },
            { key: "name", label: "Name", render: (item) => item.event_name },
            { key: "type", label: "Type", render: (item) => item.event_type },
            { key: "subtype", label: "Subtype", render: (item) => text(item.event_subtype) },
            { key: "description", label: "Description", render: (item) => text(item.description) },
            { key: "attendees", label: "Attendees", render: (item) => text(item.attendee_count) },
            { key: "start", label: "Start", render: (item) => formatDateTime(item.planned_start) },
            { key: "end", label: "End", render: (item) => formatDateTime(item.planned_end) },
            { key: "priority", label: "Priority", render: (item) => translateStatus(item.priority) },
            { key: "status", label: "Status", render: (item) => translateStatus(item.status) },
            { key: "budget", label: "Budget", render: (item) => formatMoney(item.budget_estimate) },
            { key: "currency", label: "Currency", render: (item) => text(item.currency_code) },
            { key: "source", label: "Source", render: (item) => text(item.source_channel) },
            { key: "transport", label: "Transport", render: (item) => text(item.requires_transport) },
            { key: "setup", label: "Setup", render: (item) => text(item.requires_setup) },
            { key: "teardown", label: "Teardown", render: (item) => text(item.requires_teardown) },
            { key: "notes", label: "Notes", render: (item) => text(item.notes) },
            { key: "created_by", label: "Created by", render: (item) => text(item.created_by) },
            { key: "created_by_user", label: "Author ID", render: (item) => ref("USR", item.created_by_user_id) },
            { key: "created", label: "Created", render: (item) => date(item.created_at) },
            { key: "updated", label: "Updated", render: (item) => date(item.updated_at) },
          ]}
        />
      )}
      {activeTab === 1 && (
        <BusinessTable
          rows={locations}
          columns={[
            { key: "location_id", label: "Location ID", render: (item) => ref("LOC", item.location_id) },
            { key: "name", label: "Venue", render: (item) => item.name || item.city },
            { key: "city", label: "City", render: (item) => item.city },
            { key: "address", label: "Address", render: (item) => text(item.address_line) },
            { key: "postal", label: "Postal code", render: (item) => text(item.postal_code) },
            { key: "country", label: "Country", render: (item) => text(item.country_code) },
            { key: "lat", label: "Latitude", render: (item) => text(item.latitude) },
            { key: "lon", label: "Longitude", render: (item) => text(item.longitude) },
            { key: "type", label: "Type", render: (item) => item.location_type },
            { key: "parking", label: "Parking", render: (item) => item.parking_difficulty },
            { key: "access", label: "Access", render: (item) => item.access_difficulty },
            { key: "setup", label: "Setup complexity", render: (item) => item.setup_complexity_score },
            { key: "notes", label: "Notes", render: (item) => text(item.notes) },
            { key: "created", label: "Created", render: (item) => date(item.created_at) },
          ]}
        />
      )}
      {activeTab === 2 && (
        <BusinessTable
          rows={people}
          columns={[
            { key: "person_id", label: "Person ID", render: (item) => ref("PER", item.person_id) },
            { key: "name", label: "Full name", render: (item) => item.full_name },
            { key: "role", label: "Role", render: (item) => item.role },
            { key: "employment", label: "Employment type", render: (item) => item.employment_type },
            { key: "home", label: "Base", render: (item) => ref("LOC", item.home_base_location_id) },
            { key: "status", label: "Availability", render: (item) => translateStatus(item.availability_status) },
            { key: "day", label: "Daily limit", render: (item) => `${item.max_daily_hours} h` },
            { key: "week", label: "Weekly limit", render: (item) => `${item.max_weekly_hours} h` },
            { key: "cost", label: "Cost/h", render: (item) => formatMoney(item.cost_per_hour) },
            { key: "notes", label: "Notes reliability", render: (item) => text(item.reliability_notes) },
            { key: "active", label: "Active", render: (item) => text(item.active) },
            { key: "created", label: "Created", render: (item) => date(item.created_at) },
            { key: "updated", label: "Updated", render: (item) => date(item.updated_at) },
          ]}
        />
      )}
      {activeTab === 3 && (
        <BusinessTable
          rows={equipment}
          columns={[
            { key: "equipment_id", label: "Equipment ID", render: (item) => ref("EQP", item.equipment_id) },
            { key: "type_id", label: "Type ID", render: (item) => ref("ETY", item.equipment_type_id) },
            { key: "tag", label: "Asset tag", render: (item) => text(item.asset_tag) },
            { key: "serial", label: "Serial number", render: (item) => text(item.serial_number) },
            { key: "status", label: "Status", render: (item) => translateStatus(item.status) },
            { key: "warehouse", label: "Warehouse", render: (item) => ref("LOC", item.warehouse_location_id) },
            { key: "transport", label: "Transport requirements", render: (item) => text(item.transport_requirements) },
            { key: "replacement", label: "Replacement", render: (item) => text(item.replacement_available) },
            { key: "cost", label: "Cost/h", render: (item) => formatMoney(item.hourly_cost_estimate) },
            { key: "purchase", label: "Purchase date", render: (item) => text(item.purchase_date) },
            { key: "notes", label: "Notes", render: (item) => text(item.notes) },
            { key: "active", label: "Active", render: (item) => text(item.active) },
            { key: "created", label: "Created", render: (item) => date(item.created_at) },
            { key: "updated", label: "Updated", render: (item) => date(item.updated_at) },
          ]}
        />
      )}
      {activeTab === 4 && (
        <BusinessTable
          rows={equipmentTypes}
          columns={[
            { key: "type_id", label: "Type ID", render: (item) => ref("ETY", item.equipment_type_id) },
            { key: "name", label: "Type", render: (item) => item.type_name },
            { key: "category", label: "Category", render: (item) => text(item.category) },
            { key: "description", label: "Description", render: (item) => text(item.description) },
            { key: "setup", label: "Setup", render: (item) => `${item.default_setup_minutes ?? 0} min` },
            { key: "teardown", label: "Teardown", render: (item) => `${item.default_teardown_minutes ?? 0} min` },
          ]}
        />
      )}
      {activeTab === 5 && (
        <BusinessTable
          rows={vehicles}
          columns={[
            { key: "vehicle_id", label: "Vehicle ID", render: (item) => ref("VEH", item.vehicle_id) },
            { key: "name", label: "Vehicle", render: (item) => item.vehicle_name },
            { key: "type", label: "Type", render: (item) => item.vehicle_type },
            { key: "registration", label: "Registration", render: (item) => text(item.registration_number) },
            { key: "capacity", label: "Capacity / notes", render: (item) => text(item.capacity_notes) },
            { key: "status", label: "Status", render: (item) => translateStatus(item.status) },
            { key: "home", label: "Base", render: (item) => ref("LOC", item.home_location_id) },
            { key: "km", label: "Cost/km", render: (item) => formatMoney(item.cost_per_km) },
            { key: "hour", label: "Cost/h", render: (item) => formatMoney(item.cost_per_hour) },
            { key: "active", label: "Active", render: (item) => text(item.active) },
            { key: "created", label: "Created", render: (item) => date(item.created_at) },
            { key: "updated", label: "Updated", render: (item) => date(item.updated_at) },
          ]}
        />
      )}
      {activeTab === 6 && (
        <BusinessTable
          rows={skills}
          columns={[
            { key: "skill_id", label: "Skill ID", render: (item) => ref("SKL", item.skill_id) },
            { key: "name", label: "Skill", render: (item) => item.skill_name },
            { key: "category", label: "Category", render: (item) => text(item.skill_category) },
            { key: "description", label: "Description", render: (item) => text(item.description) },
          ]}
        />
      )}
    </Stack>
  );
}
