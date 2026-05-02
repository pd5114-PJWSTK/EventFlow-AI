# Phase 4 Smoke Collection

Szybka kolekcja smoke do walidacji generowania planu, timeoutow i fallback policy.

## Prerequisites

- Uruchomione uslugi: `docker compose up -d`
- Backend dostepny pod `http://localhost:8000`
- Testowy event z requirementami i availability zasobow pokrywajacymi okno eventu

## Smoke Steps

1. Przygotuj event z minimum jednym requirementem:
- `person_role` albo `person_skill`
- opcjonalnie `vehicle_type`, aby sprawdzic generowanie `transport_legs`

2. Dodaj aktywne zasoby i okna availability pokrywajace czas requirementow.

3. Wywolaj generowanie planu z jawna polityka:

```bash
curl -X POST http://localhost:8000/api/planner/generate-plan \
  -H "Content-Type: application/json" \
  -d '{
    "event_id":"<event_id>",
    "solver_timeout_seconds":10,
    "fallback_enabled":true,
    "commit_to_assignments":true,
    "trigger_reason":"manual"
  }'
```

4. Oczekiwane pola odpowiedzi:
- `planner_run_id`
- `recommendation_id`
- `solver`
- `solver_duration_ms`
- `fallback_reason`
- `is_fully_assigned`
- `assignments`
- `assignment_ids`
- `transport_leg_ids`
- `estimated_cost`

5. Negatywny smoke fallback policy:

```bash
curl -X POST http://localhost:8000/api/planner/generate-plan \
  -H "Content-Type: application/json" \
  -d '{
    "event_id":"<event_id>",
    "solver_timeout_seconds":10,
    "fallback_enabled":false
  }'
```

W srodowisku bez pakietu OR-Tools oczekiwany status: `400` z komunikatem
`Fallback disabled after ortools_unavailable`.

## Test Commands

```bash
# Phase 4 suite
pytest tests/test_phase4_cp01.py tests/test_phase4_cp02.py tests/test_phase4_cp03.py tests/test_phase4_cp04.py -q

# Phase 3 + Phase 4 regression
pytest tests/test_phase3_cp01.py tests/test_phase3_cp02.py tests/test_phase3_cp03.py tests/test_phase3_cp04.py tests/test_phase3_cp05.py tests/test_phase4_cp01.py tests/test_phase4_cp02.py tests/test_phase4_cp03.py tests/test_phase4_cp04.py -q

# Full regression
pytest -q
```
