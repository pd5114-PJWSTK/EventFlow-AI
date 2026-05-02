# CP-03: Hardening DB

## Co dodano
- Check constraints:
  - `core.assignments`: poprawny zakres czasu, spojnosc resource identity, zasada `consumed_at >= created_at`.
  - `ops.actual_timings`: poprawne relacje `planned_*` i `actual_*`.
  - `ops.resource_checkpoints`: spojnosc `resource_type` i kolumn `person_id/equipment_id/vehicle_id`.

- Indeksy pod zapytania krytyczne:
  - `core.assignments` po event+okno+status,
  - `ops.event_execution_logs` po event+czas,
  - `ops.actual_timings` po event+phase,
  - `ops.resource_checkpoints` po event+czas.

- Unikalne indeksy czesciowe dla assignment slotow:
  - person/equipment/vehicle (`uq_assignments_*_active_slot`).

## Pliki
- Init dla nowych srodowisk:
  - `docker/postgres/init/01_schema.sql`
- Patch dla istniejacych srodowisk:
  - `scripts/sql/cp03_db_hardening.sql`

## Uruchomienie patcha na istniejacej bazie
Przyklad (z kontenera backend):

```bash
docker compose exec backend psql "$DATABASE_URL" -f scripts/sql/cp03_db_hardening.sql
```
