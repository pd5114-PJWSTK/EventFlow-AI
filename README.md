# EventFlow AI

EventFlow AI to backendowy system do planowania i replanningu eventow (ludzie, sprzet, pojazdy, czas), z warstwa ML do oceny wariantow planu i runtime operations do pracy na zywo.

## Co robi program
- Zarzadza eventami, wymaganiami i zasobami.
- Generuje plan przydzialow i transportu (OR-Tools + fallback).
- Wykrywa luki planu i prowadzi decyzje operatora (uzupelnienie zasobow lub przelozenie eventu).
- Obsluguje live incidenty i replanning z uwzglednieniem zasobow juz zuzytych.
- Zbiera dane wykonawcze (ops logs) i prowadzi pipeline ML (features -> training -> inference -> retraining).

## Najwazniejsze moduly
- `app/api/` - endpointy FastAPI
- `app/services/` - logika domenowa (planner, runtime, ML, AI)
- `app/models/` - modele SQLAlchemy (`core`, `ops`, `ai`)
- `app/schemas/` - kontrakty request/response
- `app/workers/` - zadania Celery
- `docker/postgres/init/` - inicjalizacja DB dla nowego srodowiska
- `tests/` - testy fazowe i regresja
- `docs/` - dokumentacja funkcjonalna i techniczna

## Struktura dokumentacji
- indeks: `docs/README.md`
- plan i architektura: `docs/reference/Plan.md`
- baza danych: `docs/reference/Baza_danych.md`
- przykladowe dane: `docs/reference/Przykladowe_dane.md`
- kontrakt wizard luk: `docs/contracts/frontend-gap-wizard.md`
- hardening DB (CP-03): `docs/database/cp03-hardening.md`
- smoke testy: `docs/testing/smoke/`
- raport implementacji: `raport.txt`

## Szybki start (Docker)
1. Skopiuj konfiguracje:
```bash
cp .env.example .env
```

2. Uruchom stack:
```bash
docker compose up --build
```

3. Sprawdz health:
- `GET http://localhost:8000/health`
- `GET http://localhost:8000/ready`

4. Swagger:
- `http://localhost:8000/docs`

## Uruchamianie testow
Lokalnie (jesli masz `pytest`):
```bash
pytest -q
```

W kontenerze backend:
```bash
docker compose exec -e READY_CHECK_EXTERNALS=false backend pytest -q
```

## Kluczowe endpointy (przeglad)
### Planner
- `POST /api/planner/generate-plan`
- `POST /api/planner/replan/{event_id}`
- `POST /api/planner/recommend-best-plan`
- `POST /api/planner/preview-gaps/{event_id}`
- `POST /api/planner/resolve-gaps/{event_id}`

### Runtime operations
- `POST /api/runtime/events/{event_id}/start`
- `POST /api/runtime/events/{event_id}/checkpoint`
- `POST /api/runtime/events/{event_id}/incident`
- `POST /api/runtime/events/{event_id}/complete`

### ML
- `POST /api/ml/features/events/{event_id}`
- `POST /api/ml/models/train-baseline`
- `POST /api/ml/models/harden-duration`
- `POST /api/ml/models/train-plan-evaluator`
- `POST /api/ml/predictions`

## Kontrakty i niezawodnosc
- Idempotency dla runtime/replan/resolve-gaps (`idempotency_key`, replay header).
- Stabilne domenowe kody bledow przez `X-Error-Code`.
- Guardraile ML przy wyborze planu.
- Hardening DB (constraints + indeksy) opisany w `docs/database/cp03-hardening.md`.

## Praca na branchach i checkpointach
- Integracja fazowa: `phase/*`
- Checkpointy: `phase-N-cp-XX-*`
- Stabilne domkniecia: `phase-N-complete`

## Dla osob trzecich (jak czytac projekt)
1. Zacznij od `docs/README.md` i `docs/reference/Plan.md`.
2. Przejrzyj API przez `/docs` i kontrakt wizarda w `docs/contracts/frontend-gap-wizard.md`.
3. Uruchom testy (`pytest -q` lub Docker) i sprawdz raport `raport.txt`.
