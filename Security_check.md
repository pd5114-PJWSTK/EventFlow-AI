# Security Check - EventFlow AI (Po CP-05)

Data aktualizacji: 2026-05-03  
Zakres: repozytorium `C:\repos\Projekt`  
Metoda: przeglad statyczny + testy automatyczne CP-04/CP-05 + regresja Docker

## Executive summary

Status podatnosci z raportu:

1. `P0` Brak wymuszenia auth/authz na endpointach biznesowych -> **FIXED**
2. `P1` Path traversal przy zapisie artefaktow modeli ML -> **FIXED**
3. `P2` Niebezpieczne domyslne sekrety i konto administracyjne -> **FIXED**

---

## 1) [P0] Auth/Authz na endpointach biznesowych - FIXED

### Co wdrozono
- Wymuszenie RBAC per grupa endpointow:
  - planowanie i CRUD domenowe: `manager`, `coordinator`,
  - runtime operacyjny + websocket runtime: `manager`, `coordinator`, `technician`,
  - trening modeli ML i `api/test/*`: `manager`,
  - administracja userami: `admin`.
- `/health`, `/ready`, `/auth/login`, `/auth/refresh` pozostaja publiczne.

### Dowody statyczne
- `app/main.py` - routery podpinane z `Depends(require_role(...))` zgodnie z matryca.
- `app/middleware/rbac.py` - wspolna walidacja access token + role-check dla HTTP i WS.

### Dowody testowe
- `tests/test_phase8_cp04.py`:
  - `401` bez tokena na `/api/*`,
  - `403` dla non-admin na `/admin/*`,
  - reject/accept websocket auth.
- `tests/test_phase8_cp05.py`:
  - parametryzowane `401` dla mutujacych endpointow `/api/*`,
  - `403` dla roli nieuprawnionej (technician/coordinator/admin-only),
  - runtime WS role enforcement.

---

## 2) [P1] Path Traversal przy artefaktach ML - FIXED

### Co wdrozono
- Whitelist `model_name`: `^[A-Za-z0-9_-]{1,120}$`.
- Blokada separatorow i traversal w resolverze zapisu artefaktu.
- Twarda kontrola po `resolve()`: zapis musi pozostac pod `ML_MODELS_DIR`.

### Dowody statyczne
- `app/schemas/ml_models.py` - `pattern` na `model_name`.
- `app/services/ml_training_service.py` - `_resolve_model_artifact_dir(...)` z kontrola `relative_to`.

### Dowody testowe
- `tests/test_phase8_cp04.py` - blokada `../` i `..\\`.
- `tests/test_phase8_cp05.py` - blokada `../`, `..\\`, sciezek absolutnych i UNC.

---

## 3) [P2] Domyslne sekrety i demo-admin - FIXED

### Co wdrozono
- Usuniete niebezpieczne defaulty demo:
  - `DEMO_ADMIN_ENABLED=false` domyslnie,
  - brak domyslnych `DEMO_ADMIN_USERNAME/DEMO_ADMIN_PASSWORD`.
- Fail-fast security:
  - poza `development` slaby/krótki `JWT_SECRET_KEY` blokuje start,
  - poza `development` `DEMO_ADMIN_ENABLED=true` blokuje start,
  - poza `development` `API_TEST_JOBS_ENABLED=true` blokuje start.
- Gdy demo jest jawnie wlaczone, wymagane sa jawne demo credentials.

### Dowody statyczne
- `app/config.py` - walidator `validate_security_settings`.
- `.env.example` - bezpieczne domyslne wartosci.

### Dowody testowe
- `tests/test_phase8_cp04.py` - fail-fast dla slabych sekretow poza development.
- `tests/test_phase8_cp05.py` - fail-fast dla `API_TEST_JOBS_ENABLED` poza development i dla demo bez jawnych credow.

---

## Walidacja koncowa (regresja)

- Pelny pakiet testow przez Docker:
  - `docker compose run --rm -e READY_CHECK_EXTERNALS=false -e CELERY_ALWAYS_EAGER=true backend pytest -q`
- Wynik oczekiwany dla CP-05: brak regresji i zielony komplet testow.

---

## Residual Risk (operacyjny)

- Bezpieczenstwo nadal zalezy od poprawnej konfiguracji VPS:
  - mocny `JWT_SECRET_KEY`,
  - `APP_ENV=production`,
  - `DEMO_ADMIN_ENABLED=false`,
  - rotacja hasel bootstrap/admin po wdrozeniu.
