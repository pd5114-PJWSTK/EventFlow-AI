# Kontrakt frontend wizard: luki planu (CP-03)

## Cel
Utrzymac stabilny przeplyw:
1. preview luk,
2. wybor strategii,
3. commit decyzji,
4. odczyt nowego planu i audit trail.

## Endpointy
- `POST /api/planner/preview-gaps/{event_id}`
  - generuje plan bez commitu assignmentow,
  - zwraca `generated_plan.gap_resolution` i wersje kontraktu.

- `POST /api/planner/resolve-gaps/{event_id}`
  - strategia `augment_resources` lub `reschedule_event`,
  - wykonuje zmiany domenowe,
  - uruchamia ponowne planowanie,
  - zwraca finalny plan i podsumowanie decyzji.

## Najwazniejsze pola odpowiedzi
- `generated_plan.gap_resolution.has_gaps`
- `generated_plan.gap_resolution.requirement_gaps[]`
- `generated_plan.gap_resolution.options[]`
- `generated_plan.gap_resolution.suggested_reschedule_windows[]`
- `generated_plan.planner_run_id`
- `generated_plan.recommendation_id`

## Idempotency i retry
- `resolve-gaps` przyjmuje `idempotency_key`.
- Przy replay backend zwraca naglowek `X-Idempotency-Replayed: true`.

## Kody bledow (naglowek `X-Error-Code`)
- `PLANNER_EVENT_NOT_FOUND`
- `PLANNER_INPUT_ERROR`
- `PLANNER_GENERATION_ERROR`
- `IDEMPOTENCY_CONFLICT`
- `IDEMPOTENCY_PENDING`

## Przeplyw UI (minimalny)
1. Uzytkownik uruchamia `preview-gaps`.
2. UI pokazuje luki i 2 opcje:
   - uzupelnienie zasobow,
   - przelozenie eventu.
3. UI wysyla `resolve-gaps` z wybrana strategia.
4. UI pokazuje nowy plan i `decision_summary`.
