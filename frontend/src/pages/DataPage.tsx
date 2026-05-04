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

const tabs = ["Eventy", "Lokalizacje", "Ludzie", "Sprzęt", "Typy sprzętu", "Pojazdy", "Umiejętności"];

function text(value: unknown): string {
  if (value === undefined || value === null || value === "") return "Brak";
  if (typeof value === "boolean") return value ? "Tak" : "Nie";
  return String(value);
}

function date(value?: string | null): string {
  return value ? formatDateTime(value) : "Brak";
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
        setError(err instanceof Error ? err.message : "Nie udało się pobrać danych.");
      }
    };
    void load();
  }, [api]);

  return (
    <Stack spacing={2}>
      <Typography variant="h4">Dane</Typography>
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
            { key: "event_id", label: "ID eventu", render: (item) => item.event_id },
            { key: "client_id", label: "ID klienta", render: (item) => item.client_id },
            { key: "location_id", label: "ID lokalizacji", render: (item) => item.location_id },
            { key: "name", label: "Nazwa", render: (item) => item.event_name },
            { key: "type", label: "Typ", render: (item) => item.event_type },
            { key: "subtype", label: "Podtyp", render: (item) => text(item.event_subtype) },
            { key: "description", label: "Opis", render: (item) => text(item.description) },
            { key: "attendees", label: "Uczestnicy", render: (item) => text(item.attendee_count) },
            { key: "start", label: "Start", render: (item) => formatDateTime(item.planned_start) },
            { key: "end", label: "Koniec", render: (item) => formatDateTime(item.planned_end) },
            { key: "priority", label: "Priorytet", render: (item) => translateStatus(item.priority) },
            { key: "status", label: "Status", render: (item) => translateStatus(item.status) },
            { key: "budget", label: "Budżet", render: (item) => formatMoney(item.budget_estimate) },
            { key: "currency", label: "Waluta", render: (item) => text(item.currency_code) },
            { key: "source", label: "Źródło", render: (item) => text(item.source_channel) },
            { key: "transport", label: "Transport", render: (item) => text(item.requires_transport) },
            { key: "setup", label: "Setup", render: (item) => text(item.requires_setup) },
            { key: "teardown", label: "Demontaż", render: (item) => text(item.requires_teardown) },
            { key: "notes", label: "Notatki", render: (item) => text(item.notes) },
            { key: "created_by", label: "Utworzył", render: (item) => text(item.created_by) },
            { key: "created_by_user", label: "ID autora", render: (item) => text(item.created_by_user_id) },
            { key: "created", label: "Utworzono", render: (item) => date(item.created_at) },
            { key: "updated", label: "Zaktualizowano", render: (item) => date(item.updated_at) },
          ]}
        />
      )}
      {activeTab === 1 && (
        <BusinessTable
          rows={locations}
          columns={[
            { key: "location_id", label: "ID lokalizacji", render: (item) => item.location_id },
            { key: "name", label: "Miejsce", render: (item) => item.name || item.city },
            { key: "city", label: "Miasto", render: (item) => item.city },
            { key: "address", label: "Adres", render: (item) => text(item.address_line) },
            { key: "postal", label: "Kod pocztowy", render: (item) => text(item.postal_code) },
            { key: "country", label: "Kraj", render: (item) => text(item.country_code) },
            { key: "lat", label: "Szerokość", render: (item) => text(item.latitude) },
            { key: "lon", label: "Długość", render: (item) => text(item.longitude) },
            { key: "type", label: "Typ", render: (item) => item.location_type },
            { key: "parking", label: "Parking", render: (item) => item.parking_difficulty },
            { key: "access", label: "Dostęp", render: (item) => item.access_difficulty },
            { key: "setup", label: "Złożoność setupu", render: (item) => item.setup_complexity_score },
            { key: "notes", label: "Notatki", render: (item) => text(item.notes) },
            { key: "created", label: "Utworzono", render: (item) => date(item.created_at) },
          ]}
        />
      )}
      {activeTab === 2 && (
        <BusinessTable
          rows={people}
          columns={[
            { key: "person_id", label: "ID osoby", render: (item) => item.person_id },
            { key: "name", label: "Imię i nazwisko", render: (item) => item.full_name },
            { key: "role", label: "Rola", render: (item) => item.role },
            { key: "employment", label: "Forma współpracy", render: (item) => item.employment_type },
            { key: "home", label: "Baza", render: (item) => text(item.home_base_location_id) },
            { key: "status", label: "Dostępność", render: (item) => translateStatus(item.availability_status) },
            { key: "day", label: "Limit dzienny", render: (item) => `${item.max_daily_hours} h` },
            { key: "week", label: "Limit tygodniowy", render: (item) => `${item.max_weekly_hours} h` },
            { key: "cost", label: "Koszt/h", render: (item) => formatMoney(item.cost_per_hour) },
            { key: "notes", label: "Notatki niezawodności", render: (item) => text(item.reliability_notes) },
            { key: "active", label: "Aktywny", render: (item) => text(item.active) },
            { key: "created", label: "Utworzono", render: (item) => date(item.created_at) },
            { key: "updated", label: "Zaktualizowano", render: (item) => date(item.updated_at) },
          ]}
        />
      )}
      {activeTab === 3 && (
        <BusinessTable
          rows={equipment}
          columns={[
            { key: "equipment_id", label: "ID sprzętu", render: (item) => item.equipment_id },
            { key: "type_id", label: "ID typu", render: (item) => item.equipment_type_id },
            { key: "tag", label: "Oznaczenie", render: (item) => text(item.asset_tag) },
            { key: "serial", label: "Numer seryjny", render: (item) => text(item.serial_number) },
            { key: "status", label: "Status", render: (item) => translateStatus(item.status) },
            { key: "warehouse", label: "Magazyn", render: (item) => text(item.warehouse_location_id) },
            { key: "transport", label: "Wymagania transportu", render: (item) => text(item.transport_requirements) },
            { key: "replacement", label: "Zastępstwo", render: (item) => text(item.replacement_available) },
            { key: "cost", label: "Koszt/h", render: (item) => formatMoney(item.hourly_cost_estimate) },
            { key: "purchase", label: "Data zakupu", render: (item) => text(item.purchase_date) },
            { key: "notes", label: "Notatki", render: (item) => text(item.notes) },
            { key: "active", label: "Aktywny", render: (item) => text(item.active) },
            { key: "created", label: "Utworzono", render: (item) => date(item.created_at) },
            { key: "updated", label: "Zaktualizowano", render: (item) => date(item.updated_at) },
          ]}
        />
      )}
      {activeTab === 4 && (
        <BusinessTable
          rows={equipmentTypes}
          columns={[
            { key: "type_id", label: "ID typu", render: (item) => item.equipment_type_id },
            { key: "name", label: "Typ", render: (item) => item.type_name },
            { key: "category", label: "Kategoria", render: (item) => text(item.category) },
            { key: "description", label: "Opis", render: (item) => text(item.description) },
            { key: "setup", label: "Setup", render: (item) => `${item.default_setup_minutes ?? 0} min` },
            { key: "teardown", label: "Demontaż", render: (item) => `${item.default_teardown_minutes ?? 0} min` },
          ]}
        />
      )}
      {activeTab === 5 && (
        <BusinessTable
          rows={vehicles}
          columns={[
            { key: "vehicle_id", label: "ID pojazdu", render: (item) => item.vehicle_id },
            { key: "name", label: "Pojazd", render: (item) => item.vehicle_name },
            { key: "type", label: "Typ", render: (item) => item.vehicle_type },
            { key: "registration", label: "Rejestracja", render: (item) => text(item.registration_number) },
            { key: "capacity", label: "Ładowność / opis", render: (item) => text(item.capacity_notes) },
            { key: "status", label: "Status", render: (item) => translateStatus(item.status) },
            { key: "home", label: "Baza", render: (item) => text(item.home_location_id) },
            { key: "km", label: "Koszt/km", render: (item) => formatMoney(item.cost_per_km) },
            { key: "hour", label: "Koszt/h", render: (item) => formatMoney(item.cost_per_hour) },
            { key: "active", label: "Aktywny", render: (item) => text(item.active) },
            { key: "created", label: "Utworzono", render: (item) => date(item.created_at) },
            { key: "updated", label: "Zaktualizowano", render: (item) => date(item.updated_at) },
          ]}
        />
      )}
      {activeTab === 6 && (
        <BusinessTable
          rows={skills}
          columns={[
            { key: "skill_id", label: "ID umiejętności", render: (item) => item.skill_id },
            { key: "name", label: "Umiejętność", render: (item) => item.skill_name },
            { key: "category", label: "Kategoria", render: (item) => text(item.skill_category) },
            { key: "description", label: "Opis", render: (item) => text(item.description) },
          ]}
        />
      )}
    </Stack>
  );
}
