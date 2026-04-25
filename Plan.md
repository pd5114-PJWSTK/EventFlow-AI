# EventFlow AI - Plan Projektu

## 1. Przegląd Projektu

**Nazwa:** EventFlow AI - System Automatycznego Planowania Zasobów w Firmie

**Cel:** Opracowanie zdecentralizowanej aplikacji webowej wspomagającej automatyczne planowanie zasobów (ludzie, sprzęt, pojazdy, czas) dla firm zajmujących się organizacją eventów. System wykorzystuje Artificial Intelligence do optymalizacji alokacji zasobów, predykcji ryzyka, reagowania na zmiany w real-time oraz historyzacji decyzji.

**Typ systemu:** B2B SaaS - aplikacja webowa dla firm event-managementowych

**Rola AI:** Asystent wspomagający planowanie i monitorowanie, nie zastępujący człowieka

---

## 2. Stack Techniczny

### Infrastruktura
- **Serwer:** VPS (Ubuntu 22.04 LTS)
- **Konteneryzacja:** Docker + Docker Compose
- **Reverse Proxy / SSL:** Nginx (certyfikaty Let's Encrypt)
- **Repozytorium kodu:** GitHub (Git)

### Backend
- **Framework:** Python + FastAPI
- **Database ORM:** SQLAlchemy (dla PostgreSQL)
- **Baza danych:** PostgreSQL 14+ (3 schematy: core, ops, ai)
- **Message Queue / Cache:** Redis
- **Background Jobs:** Celery + Redis
- **AI Orchestration:** LangGraph (dla workflow'ów agentów)
- **Optymalizacja zasobów:** Google OR-Tools
- **ML/Predykcje:** Python + Pandas + scikit-learn
- **LLM API:** Azure OpenAI (GPT-4o lub podobne)

### Frontend
- **Framework:** React 19+
- **Język:** TypeScript
- **UI Library:** Material-UI (MUI)
- **Build Tool:** Vite
- **Package Manager:** npm/pnpm

### Testowanie & Code Quality
- **Unit Tests:** pytest
- **Code Formatting:** black
- **Linting:** ruff
- **Type Checking:** mypy

### Monitoring & Logging
- TBD (elasticsearch + kibana lub cloudwatch)

---

## 3. Architektura Systemu

### 3.1 Schemat Przepływu Danych

```
┌─────────────────┐
│   Frontend      │
│   (React/TS)    │
└────────┬────────┘
         │
         ▼
┌─────────────────────────────┐
│   API Gateway (Nginx)       │
│   - SSL/TLS                 │
│   - Load Balancing          │
└────────┬────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────┐
│          FastAPI Backend (Docker)               │
│  ┌─────────────────────────────────────────┐   │
│  │   REST API Endpoints                    │   │
│  │   - /api/events                         │   │
│  │   - /api/resources                      │   │
│  │   - /api/planner                        │   │
│  │   - /api/ai-agents                      │   │
│  │   - /api/logs/history                   │   │
│  └─────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────┐   │
│  │   Core Services                         │   │
│  │   - EventService                        │   │
│  │   - ResourceService                     │   │
│  │   - PlannerService (OR-Tools)           │   │
│  │   - PredictionService (scikit-learn)    │   │
│  └─────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────┐   │
│  │   AI Agent Orchestration (LangGraph)    │   │
│  │   - Master Agent State Machine          │   │
│  │   - Workflow Executors                  │   │
│  └─────────────────────────────────────────┘   │
└─┬──────────────────────────────────────────────┘
  │
  ├──────────────────┬──────────────────┬──────────────────┐
  ▼                  ▼                  ▼                  ▼
┌───────────┐   ┌───────────┐   ┌────────────┐   ┌──────────────┐
│PostgreSQL │   │  Redis    │   │   LLM API  │   │   OR-Tools   │
│  (core,   │   │ (cache &  │   │ (Azure     │   │ (optymali-   │
│   ops,    │   │  queue)   │   │  OpenAI)   │   │  zacja)      │
│    ai)    │   │           │   │            │   │              │
└───────────┘   └───────────┘   └────────────┘   └──────────────┘
  │
  └──────────────────────────────────────────────────────────┐
                                                               │
                            ┌──────────────────────────────────┘
                            ▼
                  ┌──────────────────────┐
                  │  Background Jobs     │
                  │  (Celery + Redis)    │
                  │  - Email notifications
                  │  - Report generation │
                  │  - ML model retraining
                  └──────────────────────┘
```

### 3.2 Schemat Bazy Danych

**Trzy logiczne schematy PostgreSQL:**

1. **core** - dane operacyjne planowania
   - `clients` - klienci
   - `locations` - lokalizacje eventów
   - `events` - zlecenia eventów
   - `resources_people` - pracownicy i freelancerzy
   - `equipment` - sprzęt
   - `vehicles` - pojazdy transportowe
   - `event_requirements` - wymagania eventu
   - `people_availability`, `equipment_availability`, `vehicle_availability` - kalendarze dostępności
   - `skills` - katalog umiejętności
   - `people_skills` - przypisanie umiejętności pracownikom
   - `assignments` - przydzielone zasoby
   - `transport_legs` - etapy transportu

2. **ops** - historia operacyjna i obsługa zdarzeń
   - `event_execution_logs` - logi z przebiegu eventu
   - `actual_timings` - rzeczywiste czasy
   - `incidents` - incydenty i problemy
   - `resource_checkpoints` - punkty kontrolne zasobów
   - `event_outcomes` - wyniki finalne eventu

3. **ai** - prognozowanie i rekomendacje
   - `event_features` - cechy eventów (do ML)
   - `resource_features` - cechy zasobów
   - `predictions` - predykcje modeli
   - `prediction_outcomes` - ocena dokładności predykcji
   - `planner_runs` - historia przebiegów planera
   - `planner_recommendations` - rekomendacje planera
   - `models` - metadane modeli ML

---

## 4. Wymagania Funkcjonalne

### 4.1 Moduł Zarządzania Eventami
- [x] CRUD eventów (draft → submitted → validated → planned → confirmed → in_progress → completed)
- [x] Definiowanie wymagań eventu (role, umiejętności, sprzęt, pojazdy, bufory czasowe)
- [x] Zarządzanie lokalizacjami (współrzędne, trudność dostępu, złożoność setup'u)
- [x] Zarządzanie klientami i priorytetami

### 4.2 Moduł Zarządzania Zasobami
- [x] Rejestr pracowników (role, umiejętności, dostępność, koszty)
- [x] Rejestr sprzętu (typy, dostępność, wymagania transportu)
- [x] Rejestr pojazdów (typy, pojemność, koszty)
- [x] Kalendarze dostępności (ograniczenia, urlopy, maintanance)
- [x] Katalog umiejętności i certyfikatów

### 4.3 Moduł Planowania (Deterministic + AI)

#### a) Generator Danych Wejściowych
- **a.1)** Agent AI generujący początkowe dane wejściowe (na bazie event requirements + dostępne zasoby)
  - Walidacja wymogów
  - Wstępna sugestia zasobów
- **a.2)** Walidacja danych wejściowych (business rules, constraints)

#### b) Optymalizacja Zasobów (OR-Tools)
- Google OR-Tools do rozwiązania Vehicle Routing Problem (VRP)
- Ograniczenia: dostępność, umiejętności, koszty, bufory czasowe
- Wyjście: optymalny harmonogram przydziału zasobów

#### c) Planowanie Optymalizacji & Ewaluacja
- **c.1)** Agent AI do planowania optymalizacji (co można zmienić dla lepszego wyniku?)
  - Ocena aktualnego planu
  - Propozycje alternatywnych scenariuszy
  - Szacowanie ryzyka dla danego planu
- **c.2)** Ewaluator (czy nowy plan jest lepszy niż poprzedni?)
  - Porównanie metryk (koszt, czas, ryzyko)
  - Akceptacja lub odrzucenie

### 4.4 Moduł Obsługi Zmian w Runtime (Live Reactions)

#### d) Manualnie Wprowadzane Logi Historii
- **d.1)** Agent AI do przetwarzania informacji wprowadzanych ręcznie
  - Parsing naturalnego tekstu (np. "Sprzęt audio się zepsuł w lokalizacji X")
  - Ekstrahowanie metadanych (typ problemu, lokalizacja, zasób, czas)
  - Zapisanie do `ops.incidents`
- **d.2)** Walidacja i normalizacja logów

#### e) Reagowanie Live (Real-time Adjustments)
- **e.1)** Agent AI reagujący na nagłe zmiany
  - Analiza incydentu
  - Trigger replanning (ponowne uruchomienie OR-Tools)
  - Propozycja zmian (zastępstwo, przesunięcie, anulowanie)
- **e.2)** Evaluator po zmianie
  - Czy zmiana jest akceptowalna?
  - Analiza wpływu na inne zasoby/eventy
  - Notyfikacja interesariuszy

### 4.5 Moduł Predykcji & ML
- Predykcja czasu trwania fazę (loadout, transport, setup, event, teardown, return)
- Predykcja wymaganej liczby pracowników
- Ocena ryzyka (delay, sprzęt, pracownik, pogoda, SLA)
- Scoring wiarygodności zasobów (na bazie historii)
- Estymacja kosztów

### 4.6 Moduł Historyzacji & Reportingu
- Kompletny audit trail wszystkich decyzji (kto, co, kiedy, dlaczego)
- Raporty z realizacji eventów
- Porównanie predykcji vs. rzeczywistość
- Dashboard dla managera (KPI, wyniki, problemy)

### 4.7 Integracje
- Azure OpenAI API (LLM do przetwarzania tekstu)
- Potencjalnie: integracja z Google Calendar, Slack, email

---

## 5. Wymagania Niefunkcjonalne

### Wydajność
- API response time < 500ms (95 percentile)
- Planowanie eventu < 10s (dla 100+ zasobów)
- Celery job completion: real-time do 30s (zależy od złożoności)

### Skalowalność
- Wspieraj minimum 1000 eventów jednocześnie w queue
- Wspieraj 10,000+ zasobów w bazie
- Możliwość horizontal scaling (Docker Compose + Kubernetes later)

### Bezpieczeństwo
- Autentykacja: JWT tokens
- Autoryzacja: Role-Based Access Control (RBAC)
- HTTPS/SSL (Let's Encrypt)
- Audit logging wszystkich zmian
- Hashing haseł (bcrypt)
- Rate limiting na API

### Reliability
- SLA uptime: 99.5% (4hrs 22min downtime/miesiąc)
- Health checks na endpointach
- Automatic failover dla Redis
- Database backups (daily snapshots)
- Graceful shutdown & startup aplikacji

### Maintainability
- Code coverage > 80%
- Comprehensive logging (DEBUG, INFO, WARNING, ERROR)
- Documentation (API docs, deployment docs)
- Secrets management (environment variables, vaults)

---

## 6. Złożoność Techniczna

### Wyzwania Główne

| Obszar | Złożoność | Objaśnienie |
|--------|-----------|------------|
| **OR-Tools Integration** | 🔴 Wysoka | VRP to NP-hard problem; wymagana konfiguracja constraints, timeouts | 
| **LLM Integration** | 🟡 Średnia | Azure OpenAI API + prompt engineering; rate limiting; fallback strategy |
| **Real-time Replanning** | 🔴 Wysoka | Koordynacja między Celery jobami, websockets, state invalidation |
| **Agent Orchestration** | 🔴 Wysoka | LangGraph state machine; error handling; retry logic |
| **DB Consistency** | 🟡 Średnia | PostgreSQL transactions; constraint enforcement; ACID guarantees |
| **ML Model Training** | 🟡 Średnia | Pandas + scikit-learn; data splits; hyperparameter tuning; periodic retraining |
| **Async Job Processing** | 🟡 Średnia | Celery + Redis; task tracking; priority queues |

### Gotowe komponenty (biblioteki)
- ✅ **Google OR-Tools** - dobrze udokumentowane, battle-tested
- ✅ **LangGraph** - nowy ale wspierany przez LangChain community
- ✅ **FastAPI** - moderni, high-performance
- ✅ **SQLAlchemy** - flexible ORM
- ✅ **scikit-learn** - solidne narzędzie do ML

### Komponenty do zbudowania
- API endpoints + business logic
- Agent workflows (LangGraph)
- ML feature engineering + model training
- Frontend UI/UX
- Deployment infrastructure (Docker, Nginx, systemd)

---

## 7. Data Consistency Between Schemas

System wykorzystuje 3 schematy PostgreSQL z różnym celem. Consistency strategy:

### 7.1 Referencje między Schematami

**core → ops:**
- `core.events` → `ops.event_execution_logs` (foreign key)
- `core.assignments` → `ops.actual_timings` (FK)
- `core.resources_people/equipment/vehicles` → `ops.resource_checkpoints` (FK)
- ✅ Strong integrity constraints

**core → ai:**
- `core.events` → `ai.event_features` (FK, extracted z event metadata)
- `core.resources_people/equipment` → `ai.resource_features` (FK)
- `ai.predictions` ↔ `ops.actual_timings` (dla comparison, nie FK)
- ✅ Loosely coupled, pozwala na niezależny training

**ops → ai:**
- `ops.actual_timings` + `ops.incidents` dostarczają ground-truth do oceny predykcji
- `ai.prediction_outcomes` łączy wynik ewaluacji przez `prediction_id` (z `ai.predictions`)
- ✅ One-way data flow: ops generuje rzeczywistość, ai ją ocenia

### 7.2 Transaction Boundaries

- **Planning transaction**: core.events → core.event_requirements → core.assignments (atomic)
- **Execution transaction**: ops.event_execution_logs, ops.actual_timings (separate from core)
- **ML pipeline**: ai.* tables (read-from core/ops, write predictions)

### 7.3 Backup & Recovery

Priorytet: `core` > `ops` > `ai`
- core schema: daily backup (crucial dla business data)
- ops schema: weekly backup (historical, less critical)
- ai schema: can be regenerated (models retrain na demand)

---

## 8. ML Model Versioning & Management

Strategy do trackowania i deploymentu ML modeli:

### 8.1 Model Storage

**Struktura katalogów:**
```
/models/
  ├── v1_initial/
  │   ├── duration_predictor.pkl
  │   ├── resource_reliability.pkl
  │   ├── metadata.json  # features, training date, accuracy
  │   └── training_log.txt
  ├── v2_improved/
  │   ├── ...
  └── current/ → symlink do active version
```

### 8.2 Model Metadata (ai.models table)

```sql
CREATE TABLE ai.models (
   model_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
   model_name TEXT NOT NULL,
   model_version TEXT NOT NULL,
   prediction_type ai.prediction_type NOT NULL,
   status ai.model_status NOT NULL DEFAULT 'training',
   training_data_from TIMESTAMPTZ,
   training_data_to TIMESTAMPTZ,
   metrics JSONB NOT NULL DEFAULT '{}'::jsonb,
   created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    notes TEXT
);
```

### 8.3 Prediction Outcomes Tracking (ai.prediction_outcomes)

```sql
CREATE TABLE ai.prediction_outcomes (
   prediction_outcome_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
   prediction_id UUID NOT NULL REFERENCES ai.predictions(prediction_id) ON DELETE CASCADE,
   actual_numeric_value NUMERIC(14,4),
   actual_label TEXT,
   evaluated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
   error_value NUMERIC(14,4),
    notes TEXT
);
```

### 8.4 Model Retraining Process

1. **Extract data**: query `ops.*` tables dla nowych historii
2. **Feature engineering**: transform raw data na features
3. **Train**: sklearn pipeline na new dataset
4. **Validate**: compare accuracy na test set
5. **Version**: if accuracy > threshold, save as new version
6. **Deploy**: update symlink `current/` jeśli lepsze niż active
7. **Monitor**: track prediction_outcomes dla drift detection

### 8.5 A/B Testing (Future)

Możliwe do implementacji w Later Phase:
- Run nowego modelu obok starego na subset eventów
- Track prediction_outcomes dla obu
- Décision: switch lub rollback

---

## 9. Plan Implementacji (Step-by-Step Technical Build)

Sekwencja poniżej pokrywa pełny scope funkcjonalny (w tym AI orchestration, Live Reactions i ML feedback loop) oraz minimalizuje rework.

### Phase 1: Infrastructure, Database, Async Foundation

**Goal**: Stabilne środowisko uruchomieniowe z DB i background jobs.

**Stack tej fazy**: Docker, Docker Compose, Python, FastAPI, SQLAlchemy, PostgreSQL, Redis, Celery

1. [ ] Docker setup
   - [ ] `Dockerfile` dla FastAPI
   - [ ] `docker-compose.yml` (backend + postgres + redis + celery-worker + celery-beat)
   - [ ] `.env` i secrets strategy

2. [ ] PostgreSQL initialization
   - [ ] Zaaplikowanie schema z Baza danych.md
   - [ ] Smoke test połączenia SQLAlchemy
   - [ ] Seed minimalnych danych testowych (clients, locations, resources, skills)

3. [ ] FastAPI scaffold
   - [ ] Struktura `app/`, `models/`, `schemas/`, `services/`, `workers/`
   - [ ] Dependency injection + config loader
   - [ ] Health checks (`/health`, `/ready`)

4. [ ] Authentication baseline (POC)
   - [ ] JWT token generation/validation
   - [ ] `/auth/login`, `/auth/refresh`
   - [ ] RBAC middleware i mapowanie ról operacyjnych (manager/coordinator/technician)

**Deliverable**: API + worker startują lokalnie, health-check działa, task Celery wykonuje testowy job.

---

### Phase 2: Core CRUD + Business Validation

**Goal**: Kompletny CRUD na `core.*` jako wejście dla planera.

**Stack tej fazy**: Python, FastAPI, SQLAlchemy, PostgreSQL, pytest

1. [ ] CRUD endpoints
   - [ ] `clients`, `locations`, `events`, `resources_people`, `equipment`, `vehicles`, `event_requirements`
   - [ ] Kalendarze dostępności (`people_availability`, `equipment_availability`, `vehicle_availability`)

2. [ ] Walidacje domenowe
   - [ ] `planned_end > planned_start`, budżet, status transitions
   - [ ] Spójność requirement_type z kolumnami (`role_required`, `skill_id`, `equipment_type_id`, `vehicle_type_required`)

3. [ ] Testy API
   - [ ] Unit + integration (CRUD + walidacje)
   - [ ] Collection testowa dla szybkiego smoke testu

**Deliverable**: Dane eventu i zasobów są poprawnie walidowane i gotowe do planowania.

---

### Phase 3: Planner Core - Deterministic Constraints

**Goal**: Deterministyczny silnik walidacji i doboru zasobów.

**Stack tej fazy**: Python, FastAPI, SQLAlchemy, PostgreSQL, pytest

1. [ ] ConstraintValidator
   - [ ] Dostępność czasowa
   - [ ] Skill/role matching
   - [ ] Ograniczenia kosztowe i godzinowe

2. [ ] ResourceMatcher
   - [ ] Ranking zasobów po koszcie i historycznej niezawodności
   - [ ] Obsługa wymagań mandatory vs optional

3. [ ] Endpoint walidacyjny
   - [ ] `POST /api/planner/validate-constraints`
   - [ ] Raport supportable/unsupportable requirements

**Deliverable**: Deterministyczna walidacja constraints z pełnym raportem błędów.

---

### Phase 4: OR-Tools Planner + Planner Runs

**Goal**: Generowanie planu z pełnym śladem w `ai.planner_runs`.

**Stack tej fazy**: Python, FastAPI, SQLAlchemy, PostgreSQL, Google OR-Tools

1. [ ] OR-Tools setup
   - [ ] Modelowanie problemu z time windows
   - [ ] Parametry solvera (timeout, fallback strategy)

2. [ ] Mapowanie DB → OR-Tools
   - [ ] Time windows: `events` + availability tables
   - [ ] Cost: `resources_people.cost_per_hour`, `vehicles.cost_per_km/cost_per_hour`
   - [ ] Distance: `locations.latitude/longitude` + wyliczenia transportowe

3. [ ] Plan generation
   - [ ] `POST /api/planner/generate-plan`
   - [ ] Zapis `ai.planner_runs`, `ai.planner_recommendations`
   - [ ] Commit wybranej rekomendacji do `core.assignments` i `core.transport_legs`

4. [ ] Testy wydajności
   - [ ] Scenariusz 100+ zasobów, cel < 10s

**Deliverable**: Powtarzalny plan z traceability run-to-run i zapisanymi rekomendacjami.

---

### Phase 5: AI Orchestration (LangGraph) + Azure OpenAI

**Goal**: Agentowe workflow dla input generation, optymalizacji i ewaluacji.

**Stack tej fazy**: Python, FastAPI, LangGraph, Azure OpenAI API, Redis

1. [ ] Integracja Azure OpenAI
   - [ ] Klient, retry policy, rate limiting
   - [ ] Prompt templates dla: parsing, optimization proposals, risk explanation

2. [ ] LangGraph state machine
   - [ ] Flow: input generation (4.3.a) → optimize (4.3.c.1) → evaluator (4.3.c.2)
   - [ ] Guardrails: schema validation, fallback do heurystyk

3. [ ] API dla agentów
   - [ ] `/api/ai-agents/optimize`
   - [ ] `/api/ai-agents/evaluate`

**Deliverable**: Agent zwraca uzasadnione rekomendacje i wynik ewaluacji planu.

---

### Phase 6: Runtime Operations + Live Reactions

**Goal**: Obsługa incydentów i replanning zgodnie z sekcją 4.4.

**Stack tej fazy**: Python, FastAPI, PostgreSQL, SQLAlchemy, Celery, Redis, LangGraph, Azure OpenAI API

1. [ ] Operacyjne logowanie realizacji
   - [ ] Zapis do `ops.event_execution_logs`, `ops.actual_timings`, `ops.incidents`, `ops.event_outcomes`
   - [ ] Endpointy start/checkpoint/incident/complete

2. [ ] Manual log parsing (4.4.d)
   - [ ] NLP parsing wpisów operatora
   - [ ] Normalizacja do struktury `ops.incidents`

3. [ ] Live replanning (4.4.e)
   - [ ] `POST /api/planner/replan/{event_id}`
   - [ ] `ai.planner_runs.trigger_reason = 'incident'`
   - [ ] Evaluator porównujący plan poprzedni vs nowy (koszt/czas/ryzyko)

4. [ ] Notyfikacje runtime
   - [ ] Celery tasks + opcjonalnie websocket feed dla UI

**Deliverable**: Incident -> analiza -> rekomendacja -> zaakceptowany replan działa end-to-end.

---

### Phase 7: ML Feature Pipeline + Model Versioning

**Goal**: Spięcie danych historycznych z predykcjami i oceną modeli.

**Stack tej fazy**: Python, Pandas, scikit-learn, PostgreSQL, SQLAlchemy, Celery, Redis

1. [ ] Feature engineering
   - [ ] Populate `ai.event_features` i `ai.resource_features`
   - [ ] Snapshot cech dla predykcji

2. [ ] Trening i rejestr modeli
   - [ ] Trening baseline modeli
   - [ ] Rejestracja w `ai.models` (`model_name`, `model_version`, `prediction_type`, `metrics`)

3. [ ] Inference i ewaluacja
   - [ ] Zapis do `ai.predictions`
   - [ ] Ground-truth do `ai.prediction_outcomes`

4. [ ] Retraining workflow
   - [ ] Harmonogram Celery beat
   - [ ] Warunki aktywacji nowej wersji modelu

**Deliverable**: Aktywny model z metrykami, predykcjami i feedback loop dla drift detection.

---

### Phase 8: Frontend + End-to-End Hardening

**Goal**: Używalny interfejs oraz stabilizacja całego przepływu.

**Stack tej fazy**: React, TypeScript, Material-UI (MUI), Vite, npm/pnpm

1. [ ] Frontend scaffold
   - [ ] React + TypeScript + MUI
   - [ ] Auth flow + API client

2. [ ] Kluczowe widoki
   - [ ] Event list/detail, requirements, assignments
   - [ ] Incident/logging form + porównanie plan vs actual
   - [ ] Panel rekomendacji AI

3. [ ] E2E i hardening
   - [ ] 3 scenariusze end-to-end (planowanie, runtime incident, ML feedback)
   - [ ] Performance i timeout handling
   - [ ] Error handling i observability logs

**Deliverable**: Stabilny POC webapp pokrywający pełny workflow biznesowy.

---

### Phase 9: Deployment, Operations, Documentation

**Goal**: Przekazanie rozwiązania do wdrożenia i utrzymania.

**Stack tej fazy**: Docker, Docker Compose, Nginx, FastAPI, PostgreSQL, Redis, Celery, GitHub

1. [ ] API + architektura
   - [ ] Swagger + opis workflow (planner, ai agents, live reactions)

2. [ ] Operacje
   - [ ] Backup/restore procedury (`core` > `ops` > `ai`)
   - [ ] Monitoring health-check, kolejki Celery i opóźnień jobów

3. [ ] Playbook zespołu
   - [ ] Runbook incydentów
   - [ ] Checklist release i rollback
   - [ ] Onboarding deweloperski

**Deliverable**: Gotowy do staging/production POC z dokumentacją techniczną i operacyjną.

---

## 10. Ryzyka & Mitygacja

| Ryzyko | Wagi | Mitygacja |
|--------|------|-----------|
| **OR-Tools timeout** | 🔴 | Implementować timeout strategy; fallback greedy algorithm |
| **LLM API rate limits / costs** | 🔴 | Caching responses; batch processing; fallback to heuristics |
| **Data consistency under load** | 🟡 | PostgreSQL ACID + proper transaction handling |
| **Agent hallucination** | 🟡 | Strict output validation; rules engine; human approval loops |
| **ML model drift** | 🟡 | Monitoring prediction accuracy; automated retraining |
| **Scope creep** | 🔴 | MVP focus; clear iteration planning; requirements freezing |
| **Celery job failures** | 🟡 | Dead-letter queues; monitoring + alerts; retry logic |

---

## 11. Metryki Sukcesu

- [ ] API endpoints szybciej niż 500ms (95 percentile)
- [ ] Planning time < 10s dla 100+ zasobów
- [ ] ML model accuracy > 75% (predykcje czasu)
- [ ] Plan approval rate > 80% (bez zmian ze strony użytkownika)
- [ ] System uptime > 99%
- [ ] Code coverage > 80%
- [ ] User adoption w pilotażu: > 5 events/tydzień

---

## 12. Stack Podsumowanie

| Komponent | Technologia | Justyfikacja |
|-----------|-------------|-------------|
| **Framework API** | FastAPI | Async-first, fast, modern, excellent ORM ecosystem |
| **Baza danych** | PostgreSQL | ACID, complex queries, excellent for inventory systems |
| **Optymalizacja** | Google OR-Tools | State-of-the-art routing/scheduling, open-source |
| **AI Orchestration** | LangGraph | Best-in-class workflow orchestration for agents |
| **LLM** | Azure OpenAI | Enterprise-grade, reliable, good support |
| **Job Queue** | Celery + Redis | Industry standard, reliable, scalable |
| **Frontend** | React + TS + MUI | Modern, type-safe, component library included |
| **Infrastructure** | Docker + Nginx | Containerized, easy to scale, production-ready |
| **Testing** | pytest | Python standard, excellent ecosystem |

---

## 13. Następne Kroki

1. **Finalizacja requirements** - przeprowadsić sesję design review
2. **Team setup** - alokacja osób (BE, FE, DevOps)
3. **Environment setup** - local dev, staging, production
4. **Sprint planning** - szczegółowe story points dla fazy 1
5. **Kickoff meeting** - alignment na zespół

---

**Dokument zaktualizowany:** 2026-04-25  
**Version:** 1.1 - Spójność i kolejność implementacji
