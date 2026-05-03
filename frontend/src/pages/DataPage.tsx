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
            { key: "name", label: "Nazwa", render: (item) => item.event_name },
            { key: "type", label: "Typ", render: (item) => item.event_type },
            { key: "start", label: "Start", render: (item) => formatDateTime(item.planned_start) },
            { key: "status", label: "Status", render: (item) => translateStatus(item.status) },
            { key: "budget", label: "Budżet", render: (item) => formatMoney(item.budget_estimate) },
          ]}
        />
      )}
      {activeTab === 1 && (
        <BusinessTable
          rows={locations}
          columns={[
            { key: "name", label: "Miejsce", render: (item) => item.name || item.city },
            { key: "city", label: "Miasto", render: (item) => item.city },
            { key: "address", label: "Adres", render: (item) => item.address_line || "Brak" },
            { key: "type", label: "Typ", render: (item) => item.location_type },
            { key: "setup", label: "Złożoność setupu", render: (item) => item.setup_complexity_score },
          ]}
        />
      )}
      {activeTab === 2 && (
        <BusinessTable
          rows={people}
          columns={[
            { key: "name", label: "Imię i nazwisko", render: (item) => item.full_name },
            { key: "role", label: "Rola", render: (item) => item.role },
            { key: "status", label: "Dostępność", render: (item) => translateStatus(item.availability_status) },
            { key: "hours", label: "Limit dzienny", render: (item) => `${item.max_daily_hours} h` },
            { key: "cost", label: "Koszt/h", render: (item) => formatMoney(item.cost_per_hour) },
          ]}
        />
      )}
      {activeTab === 3 && (
        <BusinessTable
          rows={equipment}
          columns={[
            { key: "tag", label: "Oznaczenie", render: (item) => item.asset_tag || "Bez oznaczenia" },
            { key: "serial", label: "Numer seryjny", render: (item) => item.serial_number || "Brak" },
            { key: "status", label: "Status", render: (item) => translateStatus(item.status) },
            { key: "replacement", label: "Zastępstwo", render: (item) => (item.replacement_available ? "Tak" : "Nie") },
            { key: "cost", label: "Koszt/h", render: (item) => formatMoney(item.hourly_cost_estimate) },
          ]}
        />
      )}
      {activeTab === 4 && (
        <BusinessTable
          rows={equipmentTypes}
          columns={[
            { key: "name", label: "Typ", render: (item) => item.type_name },
            { key: "category", label: "Kategoria", render: (item) => item.category || "Brak" },
            { key: "setup", label: "Setup", render: (item) => `${item.default_setup_minutes ?? 0} min` },
            { key: "teardown", label: "Demontaż", render: (item) => `${item.default_teardown_minutes ?? 0} min` },
          ]}
        />
      )}
      {activeTab === 5 && (
        <BusinessTable
          rows={vehicles}
          columns={[
            { key: "name", label: "Pojazd", render: (item) => item.vehicle_name },
            { key: "type", label: "Typ", render: (item) => item.vehicle_type },
            { key: "registration", label: "Rejestracja", render: (item) => item.registration_number || "Brak" },
            { key: "status", label: "Status", render: (item) => translateStatus(item.status) },
            { key: "cost", label: "Koszt/h", render: (item) => formatMoney(item.cost_per_hour) },
          ]}
        />
      )}
      {activeTab === 6 && (
        <BusinessTable
          rows={skills}
          columns={[
            { key: "name", label: "Umiejętność", render: (item) => item.skill_name },
            { key: "category", label: "Kategoria", render: (item) => item.skill_category || "Brak" },
          ]}
        />
      )}
    </Stack>
  );
}
