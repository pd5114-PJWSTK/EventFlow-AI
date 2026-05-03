# Security Check - EventFlow AI (VPS)

Data: 2026-05-03  
Zakres: `C:\repos\Projekt`  
Metoda: przeglad statyczny + szybki test dynamiczny w kontenerze

## Executive Summary

Wczesniejsze krytyczne luki (RBAC, path traversal ML, slabe domyslne sekrety) pozostaja zalatane.  
W tym skanie wykryto 3 aktualne obszary do poprawy przed wystawieniem na VPS.

---

## 1) [P1] Publiczna ekspozycja dokumentacji API i OpenAPI

### Opis
Instancja publikuje `/docs` i `/openapi.json` bez uwierzytelnienia. Na publicznym VPS ulatwia to rekonesans atakujacemu (pelna mapa endpointow, modele wejscia/wyjscia, nazwy operacji).

### Dowody
- Kod: `app/main.py:28` (`FastAPI(...)` bez `docs_url=None`, `redoc_url=None`, `openapi_url=None` w trybie produkcyjnym).
- Test dynamiczny:
  - `/docs -> 200`
  - `/openapi.json -> 200`
  - kontrolnie endpoint biznesowy `/api/clients -> 401`

### Plan zalatania
1. Dodac w `Settings` flage np. `api_docs_enabled` (domyslnie `False` poza development).
2. Tworzyc aplikacje warunkowo:
   - production: `FastAPI(..., docs_url=None, redoc_url=None, openapi_url=None)`
   - development: standardowe URL dokumentacji.
3. Dodac test regresyjny: w `APP_ENV=production` endpointy docs zwracaja `404`.

---

## 2) [P1] Brute-force lockout dziala tylko in-memory (brak wspolnego store)

### Opis
Rate limiting logowania jest trzymany w procesie (`dict` + `Lock`). Przy wielu instancjach backendu lub restarcie procesu lockout znika i atak brute-force mozna obchodzic przez rozproszenie prob miedzy repliki/procesy.

### Dowody
- `app/services/auth_rate_limit_service.py:24-26` - lokalny stan `self._buckets`.
- `app/services/auth_rate_limit_service.py:61-63` - `clear()` kasuje caly stan; restart procesu daje ten sam efekt.
- `app/api/auth.py:49` - klucz ograniczenia oparty o `username|ip` tylko w lokalnym serwisie.

### Plan zalatania
1. Przeniesc limiter do wspolnego magazynu (Redis) z TTL.
2. Wprowadzic dwa niezalezne limity:
   - per `username` (globalnie),
   - per `ip` (globalnie).
3. Dodac licznik i lockout dla `/auth/refresh` (ochrona przed credential stuffing tokenow).
4. Dodac testy integracyjne potwierdzajace lockout po restarcie procesu i miedzy instancjami.

---

## 3) [P2] Konfiguracja kontenerow nieutwardzona pod produkcje (root + bind mount kodu)

### Opis
Kontenery aplikacyjne dzialaja jako root i montuja caly katalog projektu RW (`./:/app`). Przy RCE w aplikacji napastnik moze trwale modyfikowac kod uruchomieniowy i artefakty na hoscie.

### Dowody
- `Dockerfile:1-15` - brak `USER`, proces startuje jako root.
- `docker-compose.yml:48-49`, `68-69`, `88-89` - bind mount `./:/app` dla backend/worker/beat.

### Plan zalatania
1. W `Dockerfile` dodac uzytkownika nieuprzywilejowanego (`useradd`, `chown`, `USER app`).
2. Dla produkcji usunac bind mount kodu (`./:/app`) i uruchamiac tylko z immutable image.
3. Rozdzielic compose na `docker-compose.dev.yml` (z mountami) i `docker-compose.prod.yml` (bez mountow, minimalne uprawnienia).
4. Opcjonalnie: `read_only: true`, `tmpfs` dla katalogow tymczasowych, ograniczenia `cap_drop` i `no-new-privileges`.

---

## Priorytet wdrozenia

1. Zablokowac publiczne docs/openapi w production.
2. Wdrozyc rozproszony limiter logowania (Redis) z limitami per-user i per-IP.
3. Utwardzic kontenery produkcyjne (non-root, bez bind mountow kodu).
