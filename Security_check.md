# Security Check - EventFlow AI

Data: 2026-05-02  
Zakres: repozytorium `C:\repos\Projekt`  
Metoda: przeglad statyczny + dynamiczne PoC lokalnie

## Podsumowanie

Zidentyfikowano i potwierdzono 3 glowne podatnosci:

1. `P0` Brak wymuszenia auth/authz na endpointach biznesowych.
2. `P1` Path traversal przy zapisie artefaktow modeli ML.
3. `P2` Niebezpieczne domyslne sekrety i konto administracyjne.

Wszystkie trzy zostaly dodatkowo sprawdzone dynamicznie.

---

## 1) [P0] Brak uwierzytelniania/autoryzacji na endpointach biznesowych

### Opis
Middleware RBAC istnieje, ale nie jest podpite do routerow API. W efekcie endpointy biznesowe sa dostepne bez tokena.

### Dowody statyczne
- `app/main.py:23-35` - routery podpinane bez `Depends(require_role(...))`.
- `app/middleware/rbac.py:9-25` - istnieje mechanizm `require_role`, ale nieuzywany.
- Przykladowe endpointy bez guardow:
  - `app/api/ai_agents.py:24`, `:47`, `:72`
  - `app/api/planner.py:42`, `:63`, `:101`
  - `app/api/resources.py:90` i kolejne CRUD.

### Dowody dynamiczne (PoC)
- PoC request bez `Authorization`:
  - `POST /api/ai-agents/optimize`
  - wynik: `HTTP 200`, brak bledu `401/403`.

### Ryzyko
Nieautoryzowany uzytkownik moze wykonywac operacje biznesowe i operacyjne bez logowania.

### Plan latania
1. Wymusic uwierzytelnianie i role na wszystkich routerach biznesowych.
2. Zdefiniowac macierz uprawnien per endpoint (manager/coordinator/technician).
3. Dodac testy negatywne `401/403` dla kazdego endpointu modyfikujacego stan.
4. Zabezpieczyc rowniez kanaly powiadomien/WS tym samym modelem auth.

---

## 2) [P1] Path traversal przy zapisie artefaktow modelu

### Opis
`model_name` trafia bez sanityzacji do budowy sciezki zapisu (`artifact_dir / model_name / model_version`), co pozwala wyjsc poza katalog `models`.

### Dowody statyczne
- `app/schemas/ml_models.py:13`, `:37`, `:58`, `:75` - `model_name` przyjmowane z API.
- `app/services/ml_training_service.py:1447-1448` - tworzenie katalogu na podstawie `model_name` bez walidacji.

### Dowody dynamiczne (PoC)
- Wywolanie `_save_model_artifact(...)` z `model_name="..\\poc_escape_dynamic"`.
- Wynik:
  - `artifact_path`: `C:\repos\Projekt\poc_escape_dynamic\v_dynamic\model.pkl`
  - `models_dir`: `C:\repos\Projekt\models`
  - `outside_models_dir`: `true`
  - `metadata_exists`: `true`

To potwierdza zapis poza `models/`.

### Ryzyko
Atakujacy moze zapisywac pliki poza dedykowany katalog modeli (w granicach uprawnien procesu), co jest baza do dalszych naduzyc.

### Plan latania
1. Ograniczyc `model_name` do whitelisty znakow (np. `^[a-zA-Z0-9_-]{1,120}$`).
2. Po `resolve()` wymusic, ze sciezka koncowa zaczyna sie od `ML_MODELS_DIR`.
3. Odrzucac payloady z separatorami sciezek i `..`.
4. Dodac testy traversal (`../`, `..\\`, sciezki absolutne, UNC).

---

## 3) [P2] Niebezpieczne domyslne sekrety i konto administracyjne

### Opis
Konfiguracja dopuszcza domyslne, przewidywalne wartosci dla JWT i konta admin.

### Dowody statyczne
- `app/config.py:17-23` - defaulty dla `jwt_secret_key`, `demo_admin_username`, `demo_admin_password`.
- `.env.example:15`, `:19`, `:20` - slabe/domyslne wartosci (`change-me-in-production`, `admin`, `admin123`).

### Dowody dynamiczne (PoC)
- Runtime `Settings` zwraca:
  - `jwt_secret_key = change-me-in-production`
  - `demo_admin_username = admin`
  - `demo_admin_password = admin123`
- `POST /auth/login` z `admin/admin123`:
  - wynik: `HTTP 200`
  - zwracany `access_token` i `refresh_token`.

### Ryzyko
Latwe przejecie konta i tokenow, jesli srodowisko dziala na domyslnych wartosciach.

### Plan latania
1. Usunac insecure defaulty i fail-fast przy ich uzyciu poza `development`.
2. Wymusic minimalna sile sekretu JWT (dlugosc/entropia).
3. Wylaczyc konto demo domyslnie; aktywowac tylko jawnie i lokalnie.
4. Docelowo przeniesc auth do uzytkownikow z hashem (`argon2`/`bcrypt`) w DB.

---

## Wyniki dynamicznego PoC - log skrocony

```json
{
  "unauth_ai_optimize": {
    "status_code": 200,
    "has_auth_error": false
  },
  "default_admin_login": {
    "status_code": 200,
    "has_access_token": true,
    "token_type": "bearer"
  },
  "path_traversal_artifact_write": {
    "artifact_path": "C:\\repos\\Projekt\\poc_escape_dynamic\\v_dynamic\\model.pkl",
    "models_dir": "C:\\repos\\Projekt\\models",
    "outside_models_dir": true,
    "metadata_exists": true
  },
  "default_settings_values": {
    "jwt_secret_key": "change-me-in-production",
    "demo_admin_username": "admin",
    "demo_admin_password": "admin123"
  }
}
```

---

## Nowe rzeczy dopisane po PoC

1. Potwierdzone dynamicznie, ze endpoint biznesowy dziala bez auth (`/api/ai-agents/optimize` -> `200` bez tokena).
2. Potwierdzone dynamicznie, ze zapis artefaktu modelu wychodzi poza `models/`.
3. Potwierdzone dynamicznie, ze runtime uzywa domyslnych credow i pozwala na login `admin/admin123`.
