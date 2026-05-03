# Security Check - EventFlow AI

Data: 2026-05-03  
Zakres: `C:\repos\Projekt`  
Metoda: przeglad statyczny + PoC dynamiczny w kontenerze

## Executive Summary

Aktualny stan security jest znacząco lepszy (RBAC, revocation access tokenów, hardening kontenerów).  
W tym checku wykryto 2 kwestie warte poprawy przed produkcyjnym VPS.

---

## 1) [P1] Brak reautoryzacji aktywnej sesji podczas otwartego websocketu runtime

### Opis
Połączenie websocket jest autoryzowane tylko na starcie. Po późniejszej deaktywacji użytkownika lub revokacji sesji, połączenie pozostaje aktywne i dalej streamuje dane.

### Dowody statyczne
- `app/api/runtime_ops.py:414-421` - auth tylko przy wejściu do websocket.
- `app/api/runtime_ops.py:425-437` - pętla streamująca działa bez ponownej walidacji sesji/aktywności użytkownika.

### Dowód dynamiczny (PoC)
Uruchomiono PoC w kontenerze:
- user `technician` łączy się przez WS,
- admin wykonuje `PATCH /admin/users/{id}` z `is_active=false`,
- websocket nadal odbiera wiadomości (`ws_after_disable_items 1`).

### Ryzyko
Użytkownik z już odwołanym dostępem może utrzymać aktywny kanał danych do momentu rozłączenia (okno nieautoryzowanego dostępu w runtime feed).

### Plan zalatania
1. Dodać cykliczną rewalidację sesji w pętli WS (np. co N sekund lub przed każdym push).
2. Przy revokacji sesji/usera zamykać aktywne WS dla danego `user_id` (connection registry + disconnect).
3. Dodać test regresyjny: deaktywacja usera w trakcie aktywnego WS kończy połączenie (kod 1008).

---

## 2) [P2] Ryzyko błędnej identyfikacji IP klienta za reverse proxy (lockout/DoS)

### Opis
Mechanizm throttlingu opiera się na IP z `resolve_client_ip()`. Jeśli `AUTH_TRUSTED_PROXY_IPS` nie będzie poprawnie ustawione dla realnej topologii VPS (Nginx/Traefik/LB), aplikacja może traktować IP proxy jako IP użytkownika i agregować wielu klientów pod jeden klucz limitera.

### Dowody statyczne
- `app/services/client_ip_service.py:8-24` - IP klienta zależy od listy zaufanych proxy i nagłówków `X-Forwarded-For`/`X-Real-IP`.
- `app/config.py:42` - domyślna allowlista proxy: `127.0.0.1,::1`.
- `app/api/auth.py:54-64` oraz `102-106` - throttling login/refresh używa tego IP.

### Ryzyko
Przy błędnej konfiguracji proxy możliwe są masowe lockouty (DoS) wielu użytkowników za jednym adresem pośredniczącym.

### Plan zalatania
1. W deployment runbooku wymusić jawne ustawienie `AUTH_TRUSTED_PROXY_IPS` per środowisko VPS.
2. Dodać startup preflight (lub hard-fail w non-dev), gdy aplikacja działa za proxy, a allowlista nie jest jawnie ustawiona.
3. Dodać testy integracyjne z reverse proxy headers dla scenariuszy multi-client za jednym proxy.

---

## Priorytet wdrożenia

1. Zamknąć lukę WS (reautoryzacja/rozłączanie po revokacji).  
2. Domknąć konfigurację `AUTH_TRUSTED_PROXY_IPS` dla topologii VPS i dodać twarde guardy deploymentowe.
