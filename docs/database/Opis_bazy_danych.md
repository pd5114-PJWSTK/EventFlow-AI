# Baza Danych EventFlow AI

Baza danych jest podzielona logicznie na 3 schematy PostgreSQL: `core`, `ops`, `ai`.

## 1) Schemat `core` - planowanie i zasoby
Odpowiada za dane operacyjne potrzebne do wygenerowania i utrzymania planu.

### Glówne tabele
- `clients` - klienci i SLA/priorytety.
- `locations` - lokalizacje eventów i cechy logistyczne.
- `events` - eventy wraz z oknem czasowym i statusem.
- `event_requirements` - wymagania eventu (role, skill, equipment, vehicle).
- `resources_people` - personel.
- `equipment`, `equipment_types` - sprzet i typy sprzetu.
- `vehicles` - pojazdy.
- `people_availability`, `equipment_availability`, `vehicle_availability` - dostepnosc zasobów.
- `assignments` - przypisania zasobów do eventu.
- `transport_legs` - etapy transportowe.

### Krytyczne relacje
- `events.client_id -> clients.client_id`
- `events.location_id -> locations.location_id`
- `event_requirements.event_id -> events.event_id`
- `assignments.event_id -> events.event_id`
- `transport_legs.event_id -> events.event_id`

## 2) Schemat `ops` - runtime i historia wykonania
Rejestruje rzeczywisty przebieg eventu i incydenty.

### Glówne tabele
- `event_execution_logs` - dziennik runtime.
- `actual_timings` - planowane vs rzeczywiste czasy faz.
- `incidents` - incydenty operacyjne.
- `resource_checkpoints` - checkpointy zasobów.
- `event_outcomes` - wynik eventu (SLA, koszt, jakosc).
- `idempotency_records` - idempotency kluczowych operacji API.

## 3) Schemat `ai` - plan runs i ML
Przechowuje dane i artefakty dla warstwy AI/ML.

### Glówne tabele
- `event_features` - cechy eventu do modeli.
- `resource_features` - cechy zasobów.
- `models` - rejestr modeli ML i metryk.
- `predictions` - predykcje modeli.
- `prediction_outcomes` - ewaluacja predykcji.
- `planner_runs` - przebiegi planera.
- `planner_recommendations` - rekomendacje i porównania planów.

## Spójnosc i integralnosc (hardening)
W projekcie aktywne sa constraints i indeksy wspierajace spójnosc:
- check constraints na oknach czasowych assignmentów/timingów,
- check constraints na zgodnosci `resource_type` vs `*_id`,
- unikalne indeksy czesciowe dla slotów assignment,
- indeksy pod locki i zapytania runtime/planner.

Szczególy DDL:
- `docker/postgres/init/01_schema.sql`

Patch dla istniejacych instancji:
- `scripts/sql/cp03_db_hardening.sql`

## Przeplyw danych miedzy schematami
- `core -> ops`: event i assignment staja sie podstawa logów runtime.
- `ops -> ai`: rzeczywiste wykonanie zasila ewaluacje i retraining.
- `core -> ai`: dane planistyczne i cechy eventu stanowia wejscie modeli.
