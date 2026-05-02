# Test programu - CP-08

Poniżej są dwa realne przebiegi E2E, które zostały zaimplementowane i zweryfikowane testem `tests/test_phase7_cp08.py`.

## Scenariusz 1 - Nowy event -> ingest LLM -> planner + optymalizacja -> akceptacja -> zakończenie

1. Operator wprowadza nowy event tekstowo przez `POST /api/ai-agents/ingest-event`.
2. Pipeline ingest:
   - parsuje dane eventu,
   - tworzy klienta, lokalizację, event i wymagania,
   - zwraca `event_id` bez potrzeby ręcznego uzupełniania pól.
3. System generuje cechy ML dla eventu przez `POST /api/ml/features/generate`.
4. Planner uruchamia porównanie wariantów przez `POST /api/planner/recommend-best-plan`:
   - wylicza predykcje per plan: transport/setup/teardown/total/cost/risk,
   - stosuje guardraile (confidence, OOD, high-risk),
   - liczy `plan_score` i wybiera najlepszy wariant z uzasadnieniem.
5. W teście najlepszy wariant jest automatycznie zaakceptowany (`commit_to_assignments=true`).
6. Event zostaje uruchomiony (`/api/runtime/events/{event_id}/start`) i domknięty (`/complete`) z raportem końcowym.
7. Potwierdzenie: status eventu przechodzi na `completed`, a feed notyfikacji zawiera `event_completed`.

## Scenariusz 2 - Live log incydentu -> replan + optymalizacja -> wybór zmienionego planu -> zakończenie

1. Dla eventu z bazy uruchamiany jest baseline plan (`recommend-best-plan` + commit).
2. W trakcie realizacji operator dodaje live log incydentu przez:
   - `POST /api/runtime/events/{event_id}/incident/parse`.
3. Parser incydentu:
   - klasyfikuje incydent i severity,
   - zapisuje incydent do `ops.incidents`,
   - zwraca `incident_id`.
4. Planner wykonuje przeplanowanie przez:
   - `POST /api/planner/replan/{event_id}` z `incident_id`.
5. System zwraca nowy plan oraz porównanie z bazą (`comparison.decision_note`), a plan jest zaakceptowany (`commit_to_assignments=true`).
6. Event zostaje zakończony raportem przez `/complete`.
7. Potwierdzenie: status eventu to `completed`, a notyfikacje zawierają `incident_reported`, `replan_completed`, `event_completed`.

## Co ten test potwierdza praktycznie

- Działa pełny przepływ: ingest -> planowanie -> optymalizacja -> wykonanie -> log końcowy.
- Działa przepływ runtime: live incident -> replanning -> wykonanie zmienionego planu.
- Działa warstwa ML CP-07: predykcje per plan, scoring, guardraile, uzasadnienie wyboru oraz feedback loop po zakończeniu eventu.
