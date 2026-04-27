# Phase 2 Smoke Collection

Ten dokument opisuje szybki, manualny smoke test API dla checkpointow CP-01..CP-04.

## Prerequisites

- Uruchomione uslugi: `docker compose up -d`
- Backend dostepny pod `http://localhost:8000`
- Naglowek JSON: `-H "Content-Type: application/json"`

## 1. Core CRUD (CP-01)

1. Utworz klienta:

```bash
curl -X POST http://localhost:8000/api/clients \
  -H "Content-Type: application/json" \
  -d '{"name":"Smoke Client"}'
```

2. Utworz lokalizacje:

```bash
curl -X POST http://localhost:8000/api/locations \
  -H "Content-Type: application/json" \
  -d '{"name":"Smoke Venue","city":"Warsaw"}'
```

3. Utworz event z `client_id` i `location_id` z poprzednich krokow.

## 2. Resources CRUD (CP-02)

1. Utworz skill:

```bash
curl -X POST http://localhost:8000/api/resources/skills \
  -H "Content-Type: application/json" \
  -d '{"skill_name":"smoke_skill"}'
```

2. Utworz osobe, sprzet i pojazd.
3. Przypisz skill do osoby przez `/api/resources/people/{person_id}/skills`.

## 3. Requirements + Availability (CP-03)

1. Dodaj requirement do eventu:

```bash
curl -X POST http://localhost:8000/api/events/{event_id}/requirements \
  -H "Content-Type: application/json" \
  -d '{"requirement_type":"person_role","role_required":"coordinator","quantity":1}'
```

2. Dodaj okna dostepnosci dla osoby/sprzetu/pojazdu.
3. Zweryfikuj listy availability i brak konfliktu overlap.

## 4. Planner Validation (CP-04)

1. Uruchom walidacje constraints:

```bash
curl -X POST http://localhost:8000/api/planner/validate-constraints \
  -H "Content-Type: application/json" \
  -d '{"event_id":"<event_id>"}'
```

2. Oczekiwane pola odpowiedzi:
- `is_supportable`
- `gaps`
- `estimated_cost`
- `budget_available`
- `budget_exceeded`

3. Negatywny smoke (nieistniejacy event) powinien zwrocic `404`.

## Quick Test Commands

```bash
# CP-01..CP-04
pytest tests/test_phase2_cp01.py tests/test_phase2_cp02.py tests/test_phase2_cp03.py tests/test_phase2_cp04.py -q

# Full phase-2 pattern
pytest tests/test_phase2_*.py -q
```
