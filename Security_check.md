# Security Check - EventFlow AI (2 iteracje)

Data: 2026-05-03  
Zakres: `C:\repos\Projekt`  
Tryb: security scan repozytorium + PoC dynamiczny w kontenerze

## Podsumowanie

Wcześniejsze luki (RBAC endpointów, traversal ML, domyślne sekrety) nadal wyglądają na załatane.  
W tym skanie wykryto podatności wymagające poprawy przed bezpiecznym wystawieniem na VPS.

---

## Iteracja 1 - Findings

### 1) [P1] Access token nie jest unieważniany po `logout-all` ani po deaktywacji użytkownika

#### Opis
Autoryzacja endpointów ufa wyłącznie claimom z JWT access token. Serwer nie sprawdza, czy sesja/token jest już odwołany oraz czy użytkownik został zdezaktywowany po wydaniu tokena.

#### Dowody statyczne
- `app/middleware/rbac.py:10-27` - walidacja tylko podpisu/`type=access`, brak sprawdzenia stanu sesji i `is_active` użytkownika.
- `app/services/auth_service.py:274-288` - `revoke_all_user_sessions` odwołuje tylko refresh sessions.
- `app/services/auth_service.py:182-217` - access token powstaje jako stateless JWT, bez mechanizmu runtime revocation check.

#### Dowody dynamiczne (PoC)
- Po `POST /auth/logout-all` ten sam access token nadal działa:
  - `login 200`, `logout_all 200`, `me_after_logout_all 200`.
- Po deaktywacji użytkownika (`PATCH /admin/users/{id} is_active=false`) wcześniej wydany access token nadal działa:
  - `me_before_disable 200`, `disable 200`, `me_after_disable 200`.

#### Ryzyko
Przejęty access token daje dostęp do API do czasu wygaśnięcia (`ACCESS_TOKEN_EXPIRE_MINUTES`), nawet po „wyloguj wszędzie” i po blokadzie konta.

#### Plan zalatania
1. Powiązać access token z serwerowym stanem sesji (`sid` / `session_id` claim).
2. W `get_current_auth_payload` sprawdzać (cache/DB):
   - czy sesja nie jest revoked,
   - czy użytkownik jest `is_active=true`,
   - czy wersja tokena użytkownika (np. `token_version`) jest aktualna.
3. Przy `logout`, `logout-all`, deaktywacji usera, reset hasła, zmianie ról - zwiększać `token_version`/odwoływać aktywne sesje.
4. Dodać testy regresyjne:
   - `me` po `logout-all` => `401`,
   - `me` po `is_active=false` => `401/403`.

---

## Iteracja 2 - Re-check po analizie skutków łatania

Po zaadresowaniu problemów sesji przeprowadzono drugi pass pod kątem „co może wyjść dodatkowo” dla deploymentu VPS.

### 2) [P2] Throttling per-IP jest podatny na masowe lockouty za reverse proxy (DoS)

#### Opis
Klucz limitera opiera się na `request.client.host`. W typowym scenariuszu VPS za Nginx/Traefik aplikacja może widzieć IP proxy zamiast realnego klienta. Wtedy wiele użytkowników dzieli jeden klucz IP i atakujący może łatwo wywołać lockout dla wszystkich za tym samym proxy/NAT.

#### Dowody statyczne
- `app/api/auth.py:53`, `app/api/auth.py:101` - użycie `request.client.host` jako źródła IP.
- `app/services/auth_rate_limit_service.py:14-16`, `191-203` - osobne scope IP (`login_ip`, `refresh_ip`).
- `docker-compose.yml:47` - uruchomienie uvicorn bez jawnej konfiguracji proxy trust (`forwarded-allow-ips`) dla środowiska reverse proxy.

#### Ryzyko
Atakujący generujący błędne logowania może zablokować logowanie/odświeżanie tokenów dla całej puli użytkowników widzianych pod wspólnym IP.

#### Plan zalatania
1. Wystandaryzować pozyskiwanie IP:
   - ufać tylko nagłówkom zaufanego proxy (allowlist),
   - odrzucać/ignorować spoofowane `X-Forwarded-For` spoza trust chain.
2. Dodać konfigurację deploymentu proxy-aware (`FORWARDED_ALLOW_IPS` / analogiczna) i opisać ją w runbooku VPS.
3. Zmniejszyć wpływ lockoutu per-IP:
   - limit per-username jako priorytet,
   - osobny, wyższy próg dla IP,
   - telemetry i alerty przy anomaliach lockout.
4. Dodać testy integracyjne z nagłówkami proxy oraz scenariuszem wielu użytkowników za jednym IP.

---

## Priorytet wdrożenia

1. Zamknąć lukę unieważniania access tokenów (logout-all / disable user).  
2. Utwardzić model pozyskiwania IP i politykę throttlingu pod reverse proxy na VPS.
