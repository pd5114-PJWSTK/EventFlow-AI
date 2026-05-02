# Phase 3 Smoke Collection

Szybka kolekcja smoke do walidacji planner-core po checkpointach CP-01..CP-05.

## Prerequisites

- Uruchomione uslugi: `docker compose up -d`
- Backend dostepny pod `http://localhost:8000`
- Testowe dane eventu i zasobow (client/location/event)

## Smoke Steps

1. Dodaj requirementy eventu:
- role (person_role)
- skill (person_skill)
- equipment (equipment_type)
- vehicle (vehicle_type)

2. Dodaj zasoby i availability pokrywajace okno eventu.

3. Wywolaj walidacje planner:

```bash
curl -X POST http://localhost:8000/api/planner/validate-constraints \
  -H "Content-Type: application/json" \
  -d '{"event_id":"<event_id>"}'
```

4. Oczekiwane pola odpowiedzi:
- `is_supportable`
- `gaps`
- `supportable_requirements`
- `unsupported_requirements`
- `estimated_cost`
- `cost_breakdown`
- `budget_available`
- `budget_exceeded`

5. Negatywny smoke:

```bash
curl -X POST http://localhost:8000/api/planner/validate-constraints \
  -H "Content-Type: application/json" \
  -d '{"event_id":"ffffffff-ffff-ffff-ffff-ffffffffffff"}'
```

Oczekiwany status: `404`.

## Test Commands

```bash
# Phase 3 suite
pytest tests/test_phase3_cp01.py tests/test_phase3_cp02.py tests/test_phase3_cp03.py tests/test_phase3_cp04.py tests/test_phase3_cp05.py -q

# Phase 2 + Phase 3 regression
pytest tests/test_phase2_cp01.py tests/test_phase2_cp02.py tests/test_phase2_cp03.py tests/test_phase2_cp04.py tests/test_phase3_cp01.py tests/test_phase3_cp02.py tests/test_phase3_cp03.py tests/test_phase3_cp04.py tests/test_phase3_cp05.py -q
```
