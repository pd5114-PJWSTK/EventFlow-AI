-- EventFlow production upgrade patch.
-- Consolidates CP-03 through CP-08 database hardening, seeds, cleanup and planning-state patches.
-- Safe to apply repeatedly with psql -v ON_ERROR_STOP=1.


-- ============================================================================
-- Source: scripts\sql\cp03_db_hardening.sql
-- ============================================================================

-- CP-03 database hardening patch for existing environments.
-- Safe to re-run.

BEGIN;

ALTER TABLE core.assignments
    ADD COLUMN IF NOT EXISTS is_consumed_in_execution BOOLEAN NOT NULL DEFAULT FALSE;

ALTER TABLE core.assignments
    ADD COLUMN IF NOT EXISTS consumed_at TIMESTAMPTZ;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'ck_assignments_time_window'
    ) THEN
        ALTER TABLE core.assignments
            ADD CONSTRAINT ck_assignments_time_window
            CHECK (planned_end > planned_start);
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'ck_assignments_consumed_after_create'
    ) THEN
        ALTER TABLE core.assignments
            ADD CONSTRAINT ck_assignments_consumed_after_create
            CHECK (consumed_at IS NULL OR consumed_at >= created_at);
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'ck_assignments_resource_identity'
    ) THEN
        ALTER TABLE core.assignments
            ADD CONSTRAINT ck_assignments_resource_identity
            CHECK (
                (resource_type = 'person' AND person_id IS NOT NULL AND equipment_id IS NULL AND vehicle_id IS NULL)
                OR
                (resource_type = 'equipment' AND equipment_id IS NOT NULL AND person_id IS NULL AND vehicle_id IS NULL)
                OR
                (resource_type = 'vehicle' AND vehicle_id IS NOT NULL AND person_id IS NULL AND equipment_id IS NULL)
            );
    END IF;
END $$;

CREATE UNIQUE INDEX IF NOT EXISTS uq_assignments_person_active_slot
    ON core.assignments(event_id, person_id, planned_start, planned_end, status)
    WHERE resource_type = 'person';
CREATE UNIQUE INDEX IF NOT EXISTS uq_assignments_equipment_active_slot
    ON core.assignments(event_id, equipment_id, planned_start, planned_end, status)
    WHERE resource_type = 'equipment';
CREATE UNIQUE INDEX IF NOT EXISTS uq_assignments_vehicle_active_slot
    ON core.assignments(event_id, vehicle_id, planned_start, planned_end, status)
    WHERE resource_type = 'vehicle';
CREATE INDEX IF NOT EXISTS ix_assignments_event_window_status
    ON core.assignments(event_id, planned_start, planned_end, status);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'ck_actual_timings_planned_window'
    ) THEN
        ALTER TABLE ops.actual_timings
            ADD CONSTRAINT ck_actual_timings_planned_window
            CHECK ((planned_start IS NULL OR planned_end IS NULL) OR (planned_end >= planned_start));
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'ck_actual_timings_actual_window'
    ) THEN
        ALTER TABLE ops.actual_timings
            ADD CONSTRAINT ck_actual_timings_actual_window
            CHECK ((actual_start IS NULL OR actual_end IS NULL) OR (actual_end >= actual_start));
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'ck_resource_checkpoints_resource_identity'
    ) THEN
        ALTER TABLE ops.resource_checkpoints
            ADD CONSTRAINT ck_resource_checkpoints_resource_identity
            CHECK (
                (resource_type = 'person' AND person_id IS NOT NULL AND equipment_id IS NULL AND vehicle_id IS NULL)
                OR
                (resource_type = 'equipment' AND equipment_id IS NOT NULL AND person_id IS NULL AND vehicle_id IS NULL)
                OR
                (resource_type = 'vehicle' AND vehicle_id IS NOT NULL AND person_id IS NULL AND equipment_id IS NULL)
            );
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS ix_event_execution_logs_event_time
    ON ops.event_execution_logs(event_id, timestamp_at);
CREATE INDEX IF NOT EXISTS ix_actual_timings_event_phase
    ON ops.actual_timings(event_id, phase_name);
CREATE INDEX IF NOT EXISTS ix_resource_checkpoints_event_time
    ON ops.resource_checkpoints(event_id, checkpoint_time);

COMMIT;


-- ============================================================================
-- Source: scripts\sql\cp04_auth_and_security.sql
-- ============================================================================

-- CP-04 auth and security patch for existing environments.
-- Safe to re-run.

BEGIN;

CREATE SCHEMA IF NOT EXISTS auth;

CREATE TABLE IF NOT EXISTS auth.users (
    user_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    is_superadmin BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_login_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS auth.roles (
    role_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS auth.user_roles (
    user_id UUID NOT NULL REFERENCES auth.users(user_id) ON DELETE CASCADE,
    role_id UUID NOT NULL REFERENCES auth.roles(role_id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (user_id, role_id)
);

CREATE TABLE IF NOT EXISTS auth.sessions (
    session_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(user_id) ON DELETE CASCADE,
    refresh_token_hash TEXT NOT NULL UNIQUE,
    refresh_jti TEXT NOT NULL UNIQUE,
    expires_at TIMESTAMPTZ NOT NULL,
    rotated_from_session_id UUID REFERENCES auth.sessions(session_id) ON DELETE SET NULL,
    revoked_at TIMESTAMPTZ,
    revoked_reason TEXT,
    last_used_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    user_agent TEXT,
    ip_address TEXT
);

INSERT INTO auth.roles (name)
VALUES
    ('admin'),
    ('manager'),
    ('coordinator'),
    ('technician')
ON CONFLICT (name) DO NOTHING;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'core' AND table_name = 'events' AND column_name = 'created_by_user_id'
    ) THEN
        ALTER TABLE core.events
            ADD COLUMN created_by_user_id UUID REFERENCES auth.users(user_id) ON DELETE SET NULL;
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'ai' AND table_name = 'planner_runs' AND column_name = 'initiated_by_user_id'
    ) THEN
        ALTER TABLE ai.planner_runs
            ADD COLUMN initiated_by_user_id UUID REFERENCES auth.users(user_id) ON DELETE SET NULL;
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'ops' AND table_name = 'incidents' AND column_name = 'reported_by_user_id'
    ) THEN
        ALTER TABLE ops.incidents
            ADD COLUMN reported_by_user_id UUID REFERENCES auth.users(user_id) ON DELETE SET NULL;
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'ops' AND table_name = 'event_execution_logs' AND column_name = 'author_user_id'
    ) THEN
        ALTER TABLE ops.event_execution_logs
            ADD COLUMN author_user_id UUID REFERENCES auth.users(user_id) ON DELETE SET NULL;
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_auth_sessions_user_active
    ON auth.sessions(user_id, revoked_at, expires_at);
CREATE INDEX IF NOT EXISTS idx_auth_sessions_last_used
    ON auth.sessions(last_used_at);
CREATE INDEX IF NOT EXISTS idx_events_created_by_user_id
    ON core.events(created_by_user_id);
CREATE INDEX IF NOT EXISTS idx_planner_runs_initiated_by_user_id
    ON ai.planner_runs(initiated_by_user_id);
CREATE INDEX IF NOT EXISTS idx_incidents_reported_by_user_id
    ON ops.incidents(reported_by_user_id);
CREATE INDEX IF NOT EXISTS idx_execution_logs_author_user_id
    ON ops.event_execution_logs(author_user_id);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_trigger WHERE tgname = 'trg_auth_users_updated_at'
    ) THEN
        CREATE TRIGGER trg_auth_users_updated_at
        BEFORE UPDATE ON auth.users
        FOR EACH ROW
        EXECUTE FUNCTION core.set_updated_at();
    END IF;
END $$;

COMMIT;


-- ============================================================================
-- Source: scripts\sql\cp04_production_readiness.sql
-- ============================================================================

-- CP-04 production-readiness patch for existing PostgreSQL environments.
-- Safe to re-run before local testing or VPS deployment.

BEGIN;

ALTER TABLE core.assignments
    ADD COLUMN IF NOT EXISTS is_consumed_in_execution BOOLEAN NOT NULL DEFAULT FALSE;

ALTER TABLE core.assignments
    ADD COLUMN IF NOT EXISTS consumed_at TIMESTAMPTZ;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'ck_assignments_consumed_after_create'
    ) THEN
        ALTER TABLE core.assignments
            ADD CONSTRAINT ck_assignments_consumed_after_create
            CHECK (consumed_at IS NULL OR consumed_at >= created_at);
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS ix_assignments_person_window_status
    ON core.assignments(person_id, planned_start, planned_end, status);
CREATE INDEX IF NOT EXISTS ix_assignments_equipment_window_status
    ON core.assignments(equipment_id, planned_start, planned_end, status);
CREATE INDEX IF NOT EXISTS ix_assignments_vehicle_window_status
    ON core.assignments(vehicle_id, planned_start, planned_end, status);

CREATE TABLE IF NOT EXISTS ops.idempotency_records (
    idempotency_record_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    scope TEXT NOT NULL,
    idempotency_key TEXT NOT NULL,
    event_id UUID REFERENCES core.events(event_id) ON DELETE SET NULL,
    request_fingerprint TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'processing',
    response_payload JSONB,
    error_code TEXT,
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_idempotency_scope_key UNIQUE (scope, idempotency_key),
    CONSTRAINT ck_idempotency_status CHECK (status IN ('processing', 'completed', 'failed'))
);

CREATE INDEX IF NOT EXISTS idx_idempotency_records_event_id
    ON ops.idempotency_records(event_id);
CREATE INDEX IF NOT EXISTS idx_idempotency_records_status
    ON ops.idempotency_records(status);

-- Repair mojibake in seed data on already-created local databases.
UPDATE core.clients
SET contact_person_name = 'Piotr ZieliĹ„ski',
    notes = 'Klient organizujÄ…cy eventy miejskie'
WHERE client_id = '11111111-1111-1111-1111-111111111111';

UPDATE core.locations
SET address_line = 'Ignacego PrÄ…dzyĹ„skiego 12/14',
    notes = 'DuĹĽa przestrzeĹ„ eventowa'
WHERE location_id = 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa';

UPDATE core.locations
SET name = 'Tauron Arena KrakĂłw',
    city = 'KrakĂłw',
    address_line = 'StanisĹ‚awa Lema 7',
    notes = 'DuĹĽa hala, skomplikowany setup'
WHERE location_id = 'aaaaaaa2-aaaa-aaaa-aaaa-aaaaaaaaaaa2';

UPDATE core.locations
SET name = 'Baza sprzÄ™tu'
WHERE location_id = 'aaaaaaa3-aaaa-aaaa-aaaa-aaaaaaaaaaa3';

UPDATE core.locations
SET name = 'Plac WolnoĹ›ci PoznaĹ„',
    city = 'PoznaĹ„',
    address_line = 'Plac WolnoĹ›ci'
WHERE location_id = 'aaaaaaa4-aaaa-aaaa-aaaa-aaaaaaaaaaa4';

UPDATE core.skills
SET description = 'Konfiguracja i obsĹ‚uga audio'
WHERE skill_id = 'bbbbbbb1-bbbb-bbbb-bbbb-bbbbbbbbbbb1';

UPDATE core.skills
SET description = 'Konfiguracja i obsĹ‚uga oĹ›wietlenia'
WHERE skill_id = 'bbbbbbb2-bbbb-bbbb-bbbb-bbbbbbbbbbb2';

UPDATE core.skills
SET description = 'Konfiguracja ekranĂłw i video'
WHERE skill_id = 'bbbbbbb3-bbbb-bbbb-bbbb-bbbbbbbbbbb3';

UPDATE core.resources_people
SET full_name = 'Marta WiĹ›niewska'
WHERE person_id = 'ccccccc2-cccc-cccc-cccc-ccccccccccc2';

UPDATE core.resources_people
SET full_name = 'Ola DÄ…browska'
WHERE person_id = 'ccccccc4-cccc-cccc-cccc-ccccccccccc4';

UPDATE core.equipment_types
SET description = 'DuĹĽy zestaw audio na konferencje i koncerty'
WHERE equipment_type_id = 'ddddddd1-dddd-dddd-dddd-ddddddddddd1';

UPDATE core.equipment_types
SET description = 'Ĺšredni zestaw oĹ›wietleniowy'
WHERE equipment_type_id = 'ddddddd2-dddd-dddd-dddd-ddddddddddd2';

UPDATE core.equipment_types
SET description = 'Zestaw ekranĂłw LED'
WHERE equipment_type_id = 'ddddddd3-dddd-dddd-dddd-ddddddddddd3';

UPDATE core.equipment
SET asset_tag = 'GĹ‚Ăłwny set audio'
WHERE equipment_id = 'eeeeeee1-eeee-eeee-eeee-eeeeeeeeeee1';

UPDATE core.equipment
SET asset_tag = 'ĹšwiatĹ‚a scena'
WHERE equipment_id = 'eeeeeee2-eeee-eeee-eeee-eeeeeeeeeee2';

UPDATE core.vehicles
SET capacity_notes = 'SprzÄ™t audio/light'
WHERE vehicle_id = 'fffffff1-ffff-ffff-ffff-fffffffffff1';

UPDATE core.vehicles
SET capacity_notes = 'DuĹĽy sprzÄ™t i LED'
WHERE vehicle_id = 'fffffff2-ffff-ffff-ffff-fffffffffff2';

UPDATE core.events
SET event_name = 'KrakĂłw Music Night',
    description = 'Wieczorny koncert z peĹ‚nÄ… oprawÄ… audio-light',
    notes = 'DuĹĽe ryzyko operacyjne, skomplikowana scena'
WHERE event_id = '99999992-9999-9999-9999-999999999992';

COMMIT;

-- ============================================================================
-- Source: scripts\sql\cp05_operational_training_seed.sql
-- ============================================================================

-- CP-05 operational seed: 60 coherent completed events for local/VPS testing and ML retraining.
-- Safe to re-run.
-- Business refs generated by this patch: TRAIN-001 through TRAIN-060.

BEGIN;

INSERT INTO core.clients (client_id, name, priority, industry, contact_person_name, notes)
SELECT
    ('81000000-0000-0000-0000-' || lpad(i::text, 12, '0'))::uuid,
    'Training Client ' || lpad(i::text, 3, '0'),
    (ARRAY['low','medium','high','critical'])[1 + (i % 4)]::core.priority_level,
    (ARRAY['technology','retail','finance','media'])[1 + (i % 4)],
    'Training Contact ' || lpad(i::text, 3, '0'),
    'Business training record TRAIN-' || lpad(i::text, 3, '0')
FROM generate_series(1, 60) AS s(i)
ON CONFLICT (client_id) DO UPDATE
SET name = EXCLUDED.name,
    priority = EXCLUDED.priority,
    industry = EXCLUDED.industry,
    contact_person_name = EXCLUDED.contact_person_name,
    notes = EXCLUDED.notes;

INSERT INTO core.locations (
    location_id, name, city, address_line, country_code, location_type,
    parking_difficulty, access_difficulty, setup_complexity_score, notes
)
SELECT
    ('82000000-0000-0000-0000-' || lpad(i::text, 12, '0'))::uuid,
    'Training Venue ' || lpad(i::text, 3, '0'),
    (ARRAY['Warsaw','Gdansk','Krakow','Poznan','Wroclaw'])[1 + (i % 5)],
    'Training Street ' || i,
    'PL',
    (ARRAY['conference_center','indoor','stadium','outdoor','office'])[1 + (i % 5)]::core.location_type,
    1 + (i % 5),
    1 + ((i + 1) % 5),
    1 + (i % 10),
    'Business training venue TRAIN-' || lpad(i::text, 3, '0')
FROM generate_series(1, 60) AS s(i)
ON CONFLICT (location_id) DO UPDATE
SET name = EXCLUDED.name,
    city = EXCLUDED.city,
    address_line = EXCLUDED.address_line,
    country_code = EXCLUDED.country_code,
    location_type = EXCLUDED.location_type,
    parking_difficulty = EXCLUDED.parking_difficulty,
    access_difficulty = EXCLUDED.access_difficulty,
    setup_complexity_score = EXCLUDED.setup_complexity_score,
    notes = EXCLUDED.notes;

INSERT INTO core.equipment_types (equipment_type_id, type_name, category, description, default_setup_minutes, default_teardown_minutes)
VALUES
    ('83000000-0000-0000-0000-000000000001', 'Training Audio Kit', 'audio', 'Audio kit used in TRAIN cases', 45, 30),
    ('83000000-0000-0000-0000-000000000002', 'Training LED Screen', 'video', 'LED screen kit used in TRAIN cases', 60, 45)
ON CONFLICT (equipment_type_id) DO UPDATE
SET type_name = EXCLUDED.type_name,
    category = EXCLUDED.category,
    description = EXCLUDED.description,
    default_setup_minutes = EXCLUDED.default_setup_minutes,
    default_teardown_minutes = EXCLUDED.default_teardown_minutes;

INSERT INTO core.events (
    event_id, client_id, location_id, event_name, event_type, event_subtype,
    description, attendee_count, planned_start, planned_end, priority, status,
    budget_estimate, currency_code, source_channel, requires_transport, requires_setup,
    requires_teardown, notes, created_by
)
SELECT
    ('80000000-0000-0000-0000-' || lpad(i::text, 12, '0'))::uuid,
    ('81000000-0000-0000-0000-' || lpad(i::text, 12, '0'))::uuid,
    ('82000000-0000-0000-0000-' || lpad(i::text, 12, '0'))::uuid,
    'TRAIN-' || lpad(i::text, 3, '0') || ' ' || (ARRAY['Executive Summit','Product Launch','Retail Roadshow','Music Night','Investor Day'])[1 + (i % 5)],
    (ARRAY['conference','brand_activation','concert','corporate_meeting'])[1 + (i % 4)],
    (ARRAY['corporate','outdoor_launch','live_music','roadshow'])[1 + (i % 4)],
    'Coherent completed training case TRAIN-' || lpad(i::text, 3, '0'),
    80 + (i * 8),
    ('2025-09-01 08:00:00+00'::timestamptz + (i || ' days')::interval),
    ('2025-09-01 08:00:00+00'::timestamptz + (i || ' days')::interval + ((4 + (i % 6)) || ' hours')::interval),
    (ARRAY['low','medium','high','critical'])[1 + (i % 4)]::core.priority_level,
    'completed'::core.event_status,
    (18000 + (i * 1250))::numeric(12,2),
    'PLN',
    'training_seed_cp05',
    (i % 2 = 0),
    true,
    (i % 3 <> 0),
    'Business ID TRAIN-' || lpad(i::text, 3, '0') || '; deterministic UUID suffix ' || lpad(i::text, 12, '0'),
    'cp05_seed'
FROM generate_series(1, 60) AS s(i)
ON CONFLICT (event_id) DO UPDATE
SET event_name = EXCLUDED.event_name,
    description = EXCLUDED.description,
    attendee_count = EXCLUDED.attendee_count,
    planned_start = EXCLUDED.planned_start,
    planned_end = EXCLUDED.planned_end,
    priority = EXCLUDED.priority,
    status = EXCLUDED.status,
    budget_estimate = EXCLUDED.budget_estimate,
    source_channel = EXCLUDED.source_channel,
    notes = EXCLUDED.notes;

INSERT INTO core.event_requirements (requirement_id, event_id, requirement_type, role_required, quantity, mandatory, notes)
SELECT
    ('84000000-0000-0000-0000-' || lpad(i::text, 12, '0'))::uuid,
    ('80000000-0000-0000-0000-' || lpad(i::text, 12, '0'))::uuid,
    'person_role'::core.requirement_type,
    'coordinator'::core.person_role,
    (1 + (i % 3))::numeric,
    true,
    'TRAIN-' || lpad(i::text, 3, '0') || ' coordinator requirement'
FROM generate_series(1, 60) AS s(i)
ON CONFLICT (requirement_id) DO UPDATE
SET quantity = EXCLUDED.quantity,
    notes = EXCLUDED.notes;

INSERT INTO core.event_requirements (requirement_id, event_id, requirement_type, equipment_type_id, quantity, mandatory, notes)
SELECT
    ('85000000-0000-0000-0000-' || lpad(i::text, 12, '0'))::uuid,
    ('80000000-0000-0000-0000-' || lpad(i::text, 12, '0'))::uuid,
    'equipment_type'::core.requirement_type,
    CASE WHEN i % 2 = 0 THEN '83000000-0000-0000-0000-000000000001'::uuid ELSE '83000000-0000-0000-0000-000000000002'::uuid END,
    (1 + (i % 2))::numeric,
    true,
    'TRAIN-' || lpad(i::text, 3, '0') || ' equipment requirement'
FROM generate_series(1, 60) AS s(i)
ON CONFLICT (requirement_id) DO UPDATE
SET equipment_type_id = EXCLUDED.equipment_type_id,
    quantity = EXCLUDED.quantity,
    notes = EXCLUDED.notes;

INSERT INTO ops.event_outcomes (
    event_id, finished_on_time, total_delay_minutes, actual_cost, overtime_cost,
    transport_cost, sla_breached, client_satisfaction_score, internal_quality_score,
    margin_estimate, summary_notes, closed_at
)
SELECT
    ('80000000-0000-0000-0000-' || lpad(i::text, 12, '0'))::uuid,
    (i % 5 <> 0),
    CASE WHEN i % 5 = 0 THEN 20 + (i % 35) ELSE 0 END,
    (17000 + (i * 1180) + CASE WHEN i % 5 = 0 THEN 3500 ELSE 0 END)::numeric(12,2),
    CASE WHEN i % 4 = 0 THEN (450 + i * 12)::numeric(12,2) ELSE NULL END,
    CASE WHEN i % 2 = 0 THEN (900 + i * 20)::numeric(12,2) ELSE NULL END,
    (i % 13 = 0),
    (3.4 + ((i % 7) * 0.2))::numeric(3,2),
    (3.5 + ((i % 6) * 0.2))::numeric(3,2),
    (4000 + i * 180)::numeric(12,2),
    'Completed coherent training case TRAIN-' || lpad(i::text, 3, '0'),
    ('2025-09-01 08:00:00+00'::timestamptz + (i || ' days')::interval + ((4 + (i % 6)) || ' hours')::interval + (CASE WHEN i % 5 = 0 THEN '35 minutes' ELSE '0 minutes' END)::interval)
FROM generate_series(1, 60) AS s(i)
ON CONFLICT (event_id) DO UPDATE
SET finished_on_time = EXCLUDED.finished_on_time,
    total_delay_minutes = EXCLUDED.total_delay_minutes,
    actual_cost = EXCLUDED.actual_cost,
    overtime_cost = EXCLUDED.overtime_cost,
    transport_cost = EXCLUDED.transport_cost,
    sla_breached = EXCLUDED.sla_breached,
    client_satisfaction_score = EXCLUDED.client_satisfaction_score,
    internal_quality_score = EXCLUDED.internal_quality_score,
    margin_estimate = EXCLUDED.margin_estimate,
    summary_notes = EXCLUDED.summary_notes,
    closed_at = EXCLUDED.closed_at;

INSERT INTO ops.actual_timings (
    timing_id, event_id, phase_name, planned_start, actual_start, planned_end,
    actual_end, notes
)
SELECT
    ('86000000-0000-0000-0000-' || lpad(i::text, 12, '0'))::uuid,
    ('80000000-0000-0000-0000-' || lpad(i::text, 12, '0'))::uuid,
    'event_runtime'::ops.phase_name,
    ('2025-09-01 08:00:00+00'::timestamptz + (i || ' days')::interval),
    ('2025-09-01 08:00:00+00'::timestamptz + (i || ' days')::interval),
    ('2025-09-01 08:00:00+00'::timestamptz + (i || ' days')::interval + ((4 + (i % 6)) || ' hours')::interval),
    ('2025-09-01 08:00:00+00'::timestamptz + (i || ' days')::interval + ((4 + (i % 6)) || ' hours')::interval + (CASE WHEN i % 5 = 0 THEN '35 minutes' ELSE '0 minutes' END)::interval),
    'TRAIN-' || lpad(i::text, 3, '0') || ' actual timing'
FROM generate_series(1, 60) AS s(i)
ON CONFLICT (timing_id) DO UPDATE
SET actual_end = EXCLUDED.actual_end,
    notes = EXCLUDED.notes;

COMMIT;

-- ============================================================================
-- Source: scripts\sql\cp06_operational_company_seed.sql
-- ============================================================================

-- CP-06 operational company seed.
-- Safe to re-run. It keeps existing database state and upserts operational data.
-- Business refs generated by this patch: OP-001 through OP-060.

BEGIN;

WITH admin_user AS (
    SELECT user_id FROM auth.users WHERE username = 'admin' ORDER BY created_at LIMIT 1
)
UPDATE core.clients c
SET
    name = 'Client ' || lpad(split_part(c.client_id::text, '-', 5)::bigint::text, 3, '0'),
    priority = (ARRAY['medium','high','critical','low'])[1 + (split_part(c.client_id::text, '-', 5)::bigint % 4)]::core.priority_level,
    industry = (ARRAY['technology','retail','finance','media'])[1 + (split_part(c.client_id::text, '-', 5)::bigint % 4)],
    contact_person_name = (ARRAY['Anna Nowak','Marek Zielinski','Julia Adams','Piotr Kowal'])[1 + (split_part(c.client_id::text, '-', 5)::bigint % 4)],
    notes = 'Operational client profile for recurring business events.'
WHERE c.client_id::text LIKE '81000000-0000-0000-0000-%';

UPDATE core.locations l
SET
    name = (ARRAY['Amber Expo','National Stadium','ICE Krakow','Poznan Congress Center','Wroclaw Business Hall'])[1 + (split_part(l.location_id::text, '-', 5)::bigint % 5)] || ' ' || lpad(split_part(l.location_id::text, '-', 5)::bigint::text, 3, '0'),
    city = (ARRAY['Warsaw','Gdansk','Krakow','Poznan','Wroclaw'])[1 + (split_part(l.location_id::text, '-', 5)::bigint % 5)],
    address_line = 'Business Avenue ' || split_part(l.location_id::text, '-', 5)::bigint,
    postal_code = lpad((10000 + split_part(l.location_id::text, '-', 5)::bigint)::text, 5, '0'),
    country_code = 'PL',
    location_type = (ARRAY['conference_center','indoor','stadium','outdoor','office'])[1 + (split_part(l.location_id::text, '-', 5)::bigint % 5)]::core.location_type,
    latitude = (52.00 + (split_part(l.location_id::text, '-', 5)::bigint % 10) * 0.07)::numeric(9,6),
    longitude = (20.00 + (split_part(l.location_id::text, '-', 5)::bigint % 10) * 0.09)::numeric(9,6),
    parking_difficulty = 1 + (split_part(l.location_id::text, '-', 5)::bigint % 5),
    access_difficulty = 1 + ((split_part(l.location_id::text, '-', 5)::bigint + 1) % 5),
    setup_complexity_score = 2 + (split_part(l.location_id::text, '-', 5)::bigint % 7),
    notes = 'Fully profiled operational venue with access, parking and setup data.'
WHERE l.location_id::text LIKE '82000000-0000-0000-0000-%';

INSERT INTO core.skills (skill_id, skill_name, skill_category, description)
VALUES
    ('86500000-0000-0000-0000-000000000001', 'Audio engineering', 'technical', 'Live audio setup, tuning and incident recovery.'),
    ('86500000-0000-0000-0000-000000000002', 'Lighting design', 'technical', 'Stage and architectural lighting setup.'),
    ('86500000-0000-0000-0000-000000000003', 'Video wall operation', 'technical', 'LED wall, projection and signal routing.'),
    ('86500000-0000-0000-0000-000000000004', 'Stage management', 'operations', 'Run-of-show coordination and backstage control.'),
    ('86500000-0000-0000-0000-000000000005', 'Client coordination', 'operations', 'Client communication and onsite escalation.'),
    ('86500000-0000-0000-0000-000000000006', 'Transport logistics', 'logistics', 'Vehicle dispatch and load planning.'),
    ('86500000-0000-0000-0000-000000000007', 'Warehouse handling', 'logistics', 'Picking, packing and equipment returns.'),
    ('86500000-0000-0000-0000-000000000008', 'Project leadership', 'management', 'Budget, risk and stakeholder management.')
ON CONFLICT (skill_id) DO UPDATE
SET skill_name = EXCLUDED.skill_name,
    skill_category = EXCLUDED.skill_category,
    description = EXCLUDED.description;

INSERT INTO core.equipment_types (equipment_type_id, type_name, category, description, default_setup_minutes, default_teardown_minutes)
VALUES
    ('83000000-0000-0000-0000-000000000001', 'Line Array Audio Kit', 'audio', 'Main PA set for medium and large venues.', 70, 45),
    ('83000000-0000-0000-0000-000000000002', 'LED Screen 4x3m', 'video', 'Modular LED screen wall for stages and conferences.', 80, 55),
    ('83000000-0000-0000-0000-000000000003', 'Wireless Microphone Set', 'audio', 'Eight-channel wireless microphone rack.', 25, 20),
    ('83000000-0000-0000-0000-000000000004', 'Stage Lighting Package', 'lighting', 'Moving heads, wash fixtures and control desk.', 65, 45),
    ('83000000-0000-0000-0000-000000000005', 'Streaming Encoder Kit', 'video', 'Encoder, capture devices and network failover.', 35, 25),
    ('83000000-0000-0000-0000-000000000006', 'Portable Stage Deck', 'stage', 'Modular stage deck with stairs and skirts.', 90, 70),
    ('83000000-0000-0000-0000-000000000007', 'Power Distribution Rack', 'power', 'Power distribution, cabling and protection.', 45, 35),
    ('83000000-0000-0000-0000-000000000008', 'Registration Kiosk Set', 'frontdesk', 'Tablets, printers and attendee check-in stands.', 30, 25)
ON CONFLICT (equipment_type_id) DO UPDATE
SET type_name = EXCLUDED.type_name,
    category = EXCLUDED.category,
    description = EXCLUDED.description,
    default_setup_minutes = EXCLUDED.default_setup_minutes,
    default_teardown_minutes = EXCLUDED.default_teardown_minutes;

INSERT INTO core.resources_people (
    person_id, full_name, role, employment_type, home_base_location_id,
    availability_status, max_daily_hours, max_weekly_hours, cost_per_hour,
    reliability_notes, active
)
SELECT
    ('87000000-0000-0000-0000-' || lpad(i::text, 12, '0'))::uuid,
    (ARRAY['Anna','Marek','Julia','Piotr','Katarzyna','Tomasz','Ewa','Michal'])[1 + (i % 8)] || ' ' ||
    (ARRAY['Nowak','Zielinski','Adams','Kowal','Wisniewska','Lewandowski'])[1 + (i % 6)] || ' ' || lpad(i::text, 2, '0'),
    (ARRAY['technician_audio','technician_light','technician_video','stage_manager','coordinator','driver','warehouse_operator','project_manager'])[1 + (i % 8)]::core.person_role,
    (ARRAY['employee','contractor','freelancer','agency_staff'])[1 + (i % 4)]::core.employment_type,
    ('82000000-0000-0000-0000-' || lpad(((i % 20) + 1)::text, 12, '0'))::uuid,
    'available'::core.resource_status,
    (8 + (i % 3))::numeric(4,2),
    (40 + (i % 4) * 4)::numeric(5,2),
    (95 + i * 4)::numeric(10,2),
    'Reliable operational team member. Business ref PER-' || lpad(i::text, 3, '0'),
    true
FROM generate_series(1, 48) AS s(i)
ON CONFLICT (person_id) DO UPDATE
SET full_name = EXCLUDED.full_name,
    role = EXCLUDED.role,
    employment_type = EXCLUDED.employment_type,
    home_base_location_id = EXCLUDED.home_base_location_id,
    availability_status = EXCLUDED.availability_status,
    max_daily_hours = EXCLUDED.max_daily_hours,
    max_weekly_hours = EXCLUDED.max_weekly_hours,
    cost_per_hour = EXCLUDED.cost_per_hour,
    reliability_notes = EXCLUDED.reliability_notes,
    active = EXCLUDED.active,
    updated_at = NOW();

INSERT INTO core.people_skills (person_id, skill_id, skill_level, certified, last_verified_at, notes)
SELECT
    ('87000000-0000-0000-0000-' || lpad(i::text, 12, '0'))::uuid,
    ('86500000-0000-0000-0000-' || lpad((1 + (i % 8))::text, 12, '0'))::uuid,
    3 + (i % 3),
    (i % 2 = 0),
    '2026-01-15 10:00:00+00'::timestamptz + (i || ' days')::interval,
    'Verified operational skill mapping.'
FROM generate_series(1, 48) AS s(i)
ON CONFLICT (person_id, skill_id) DO UPDATE
SET skill_level = EXCLUDED.skill_level,
    certified = EXCLUDED.certified,
    last_verified_at = EXCLUDED.last_verified_at,
    notes = EXCLUDED.notes;

INSERT INTO core.equipment (
    equipment_id, equipment_type_id, asset_tag, serial_number, status,
    warehouse_location_id, transport_requirements, replacement_available,
    hourly_cost_estimate, purchase_date, notes, active
)
SELECT
    ('88000000-0000-0000-0000-' || lpad(i::text, 12, '0'))::uuid,
    ('83000000-0000-0000-0000-' || lpad((1 + (i % 8))::text, 12, '0'))::uuid,
    'EQ-' || lpad(i::text, 4, '0'),
    'SN-CP06-' || lpad(i::text, 5, '0'),
    'available'::core.resource_status,
    ('82000000-0000-0000-0000-' || lpad(((i % 20) + 1)::text, 12, '0'))::uuid,
    (ARRAY['single van case','two-person lift','flight case','requires power check'])[1 + (i % 4)],
    (i % 3 <> 0),
    (45 + i * 3)::numeric(10,2),
    ('2023-01-01'::date + (i || ' days')::interval)::date,
    'Operational asset with business ref EQ-' || lpad(i::text, 4, '0'),
    true
FROM generate_series(1, 60) AS s(i)
ON CONFLICT (equipment_id) DO UPDATE
SET equipment_type_id = EXCLUDED.equipment_type_id,
    asset_tag = EXCLUDED.asset_tag,
    serial_number = EXCLUDED.serial_number,
    status = EXCLUDED.status,
    warehouse_location_id = EXCLUDED.warehouse_location_id,
    transport_requirements = EXCLUDED.transport_requirements,
    replacement_available = EXCLUDED.replacement_available,
    hourly_cost_estimate = EXCLUDED.hourly_cost_estimate,
    purchase_date = EXCLUDED.purchase_date,
    notes = EXCLUDED.notes,
    active = EXCLUDED.active,
    updated_at = NOW();

INSERT INTO core.vehicles (
    vehicle_id, vehicle_name, vehicle_type, registration_number, capacity_notes,
    status, home_location_id, cost_per_km, cost_per_hour, active
)
SELECT
    ('89000000-0000-0000-0000-' || lpad(i::text, 12, '0'))::uuid,
    (ARRAY['City Van','Cargo Truck','Crew Car','Stage Trailer'])[1 + (i % 4)] || ' ' || lpad(i::text, 2, '0'),
    (ARRAY['van','truck','car','trailer'])[1 + (i % 4)]::core.vehicle_type,
    'WX' || lpad(i::text, 4, '0') || 'CP',
    (ARRAY['audio cases and crew','large stage cargo','four-person crew transfer','stage deck trailer'])[1 + (i % 4)],
    'available'::core.resource_status,
    ('82000000-0000-0000-0000-' || lpad(((i % 20) + 1)::text, 12, '0'))::uuid,
    (2.40 + i * 0.08)::numeric(10,2),
    (70 + i * 3)::numeric(10,2),
    true
FROM generate_series(1, 16) AS s(i)
ON CONFLICT (vehicle_id) DO UPDATE
SET vehicle_name = EXCLUDED.vehicle_name,
    vehicle_type = EXCLUDED.vehicle_type,
    registration_number = EXCLUDED.registration_number,
    capacity_notes = EXCLUDED.capacity_notes,
    status = EXCLUDED.status,
    home_location_id = EXCLUDED.home_location_id,
    cost_per_km = EXCLUDED.cost_per_km,
    cost_per_hour = EXCLUDED.cost_per_hour,
    active = EXCLUDED.active,
    updated_at = NOW();

INSERT INTO core.people_availability (availability_id, person_id, available_from, available_to, is_available, source, notes)
SELECT
    ('87100000-0000-0000-0000-' || lpad(i::text, 12, '0'))::uuid,
    ('87000000-0000-0000-0000-' || lpad(i::text, 12, '0'))::uuid,
    '2026-01-01 00:00:00+00'::timestamptz,
    '2027-12-31 23:59:00+00'::timestamptz,
    true,
    'cp06_operational_seed',
    'Default operational availability window.'
FROM generate_series(1, 48) AS s(i)
ON CONFLICT (availability_id) DO UPDATE
SET available_from = EXCLUDED.available_from,
    available_to = EXCLUDED.available_to,
    is_available = EXCLUDED.is_available,
    source = EXCLUDED.source,
    notes = EXCLUDED.notes;

INSERT INTO core.equipment_availability (availability_id, equipment_id, available_from, available_to, is_available, source, notes)
SELECT
    ('88100000-0000-0000-0000-' || lpad(i::text, 12, '0'))::uuid,
    ('88000000-0000-0000-0000-' || lpad(i::text, 12, '0'))::uuid,
    '2026-01-01 00:00:00+00'::timestamptz,
    '2027-12-31 23:59:00+00'::timestamptz,
    true,
    'cp06_operational_seed',
    'Default operational equipment availability.'
FROM generate_series(1, 60) AS s(i)
ON CONFLICT (availability_id) DO UPDATE
SET available_from = EXCLUDED.available_from,
    available_to = EXCLUDED.available_to,
    is_available = EXCLUDED.is_available,
    source = EXCLUDED.source,
    notes = EXCLUDED.notes;

INSERT INTO core.vehicle_availability (availability_id, vehicle_id, available_from, available_to, is_available, source, notes)
SELECT
    ('89100000-0000-0000-0000-' || lpad(i::text, 12, '0'))::uuid,
    ('89000000-0000-0000-0000-' || lpad(i::text, 12, '0'))::uuid,
    '2026-01-01 00:00:00+00'::timestamptz,
    '2027-12-31 23:59:00+00'::timestamptz,
    true,
    'cp06_operational_seed',
    'Default operational vehicle availability.'
FROM generate_series(1, 16) AS s(i)
ON CONFLICT (availability_id) DO UPDATE
SET available_from = EXCLUDED.available_from,
    available_to = EXCLUDED.available_to,
    is_available = EXCLUDED.is_available,
    source = EXCLUDED.source,
    notes = EXCLUDED.notes;

WITH admin_user AS (
    SELECT user_id FROM auth.users WHERE username = 'admin' ORDER BY created_at LIMIT 1
)
UPDATE core.events e
SET
    event_name = 'OP-' || lpad(split_part(e.event_id::text, '-', 5)::bigint::text, 3, '0') || ' ' || (ARRAY['Executive Summit','Product Launch','Retail Roadshow','Music Night','Investor Day'])[1 + (split_part(e.event_id::text, '-', 5)::bigint % 5)],
    event_type = (ARRAY['conference','brand_activation','concert','corporate_meeting'])[1 + (split_part(e.event_id::text, '-', 5)::bigint % 4)],
    event_subtype = (ARRAY['executive','product','retail','live','investor'])[1 + (split_part(e.event_id::text, '-', 5)::bigint % 5)],
    description = 'Operational business event based on realistic historical planning patterns. Business ref OP-' || lpad(split_part(e.event_id::text, '-', 5)::bigint::text, 3, '0'),
    attendee_count = 80 + (split_part(e.event_id::text, '-', 5)::bigint * 8),
    budget_estimate = (18000 + (split_part(e.event_id::text, '-', 5)::bigint * 1250))::numeric(12,2),
    currency_code = 'PLN',
    source_channel = 'operational_seed_cp06',
    requires_transport = (split_part(e.event_id::text, '-', 5)::bigint % 2 = 0),
    requires_setup = true,
    requires_teardown = (split_part(e.event_id::text, '-', 5)::bigint % 3 <> 0),
    planned_start = CASE
        WHEN split_part(e.event_id::text, '-', 5)::bigint <= 20
            THEN ('2026-02-01 09:00:00+00'::timestamptz + ((split_part(e.event_id::text, '-', 5)::bigint - 1) * interval '2 days'))
        ELSE ('2026-05-10 09:00:00+00'::timestamptz + ((split_part(e.event_id::text, '-', 5)::bigint - 21) * interval '3 days'))
    END,
    planned_end = CASE
        WHEN split_part(e.event_id::text, '-', 5)::bigint <= 20
            THEN ('2026-02-01 17:00:00+00'::timestamptz + ((split_part(e.event_id::text, '-', 5)::bigint - 1) * interval '2 days'))
        ELSE ('2026-05-10 17:00:00+00'::timestamptz + ((split_part(e.event_id::text, '-', 5)::bigint - 21) * interval '3 days'))
    END,
    status = CASE
        WHEN split_part(e.event_id::text, '-', 5)::bigint <= 20 THEN 'completed'::core.event_status
        ELSE 'planned'::core.event_status
    END,
    priority = (ARRAY['low','medium','high','critical'])[1 + (split_part(e.event_id::text, '-', 5)::bigint % 4)]::core.priority_level,
    notes = 'Business ID OP-' || lpad(split_part(e.event_id::text, '-', 5)::bigint::text, 3, '0') || '; seeded from realistic operational templates.',
    created_by = 'cp06_operational_seed',
    created_by_user_id = COALESCE((SELECT user_id FROM admin_user), e.created_by_user_id)
WHERE e.event_id::text LIKE '80000000-0000-0000-0000-%';

UPDATE core.event_requirements r
SET
    role_required = (ARRAY['coordinator','technician_audio','technician_light','stage_manager'])[1 + (split_part(r.requirement_id::text, '-', 5)::bigint % 4)]::core.person_role,
    quantity = (1 + (split_part(r.requirement_id::text, '-', 5)::bigint % 3))::numeric,
    notes = 'Operational person requirement for OP-' || lpad(split_part(r.event_id::text, '-', 5)::bigint::text, 3, '0')
WHERE r.requirement_id::text LIKE '84000000-0000-0000-0000-%';

UPDATE core.event_requirements r
SET
    equipment_type_id = ('83000000-0000-0000-0000-' || lpad((1 + (split_part(r.requirement_id::text, '-', 5)::bigint % 8))::text, 12, '0'))::uuid,
    quantity = (1 + (split_part(r.requirement_id::text, '-', 5)::bigint % 2))::numeric,
    notes = 'Operational equipment requirement for OP-' || lpad(split_part(r.event_id::text, '-', 5)::bigint::text, 3, '0')
WHERE r.requirement_id::text LIKE '85000000-0000-0000-0000-%';

INSERT INTO core.event_requirements (requirement_id, event_id, requirement_type, vehicle_type_required, quantity, mandatory, notes)
SELECT
    ('85500000-0000-0000-0000-' || lpad(i::text, 12, '0'))::uuid,
    ('80000000-0000-0000-0000-' || lpad(i::text, 12, '0'))::uuid,
    'vehicle_type'::core.requirement_type,
    (ARRAY['van','truck','car','trailer'])[1 + (i % 4)]::core.vehicle_type,
    1::numeric,
    true,
    'Operational vehicle requirement for OP-' || lpad(i::text, 3, '0')
FROM generate_series(1, 60) AS s(i)
ON CONFLICT (requirement_id) DO UPDATE
SET vehicle_type_required = EXCLUDED.vehicle_type_required,
    quantity = EXCLUDED.quantity,
    notes = EXCLUDED.notes;

UPDATE ops.event_outcomes o
SET
    summary_notes = 'Completed operational event OP-' || lpad(split_part(o.event_id::text, '-', 5)::bigint::text, 3, '0') || ' with validated cost, timing and satisfaction metrics.'
WHERE o.event_id::text LIKE '80000000-0000-0000-0000-%'
  AND split_part(o.event_id::text, '-', 5)::bigint <= 20;

DELETE FROM ops.event_outcomes o
WHERE o.event_id::text LIKE '80000000-0000-0000-0000-%'
  AND split_part(o.event_id::text, '-', 5)::bigint > 20;

UPDATE ops.actual_timings t
SET
    actual_start = COALESCE(actual_start, planned_start),
    notes = 'Operational actual timing for OP-' || lpad(split_part(t.event_id::text, '-', 5)::bigint::text, 3, '0')
WHERE t.event_id::text LIKE '80000000-0000-0000-0000-%'
  AND split_part(t.event_id::text, '-', 5)::bigint <= 20;

DELETE FROM ops.actual_timings t
WHERE t.event_id::text LIKE '80000000-0000-0000-0000-%'
  AND split_part(t.event_id::text, '-', 5)::bigint > 20;

COMMIT;

-- ============================================================================
-- Source: scripts\sql\cp07_operational_cleanup_and_live_events.sql
-- ============================================================================

BEGIN;

-- CP-07 is safe to re-run. It cleans local checkpoint smoke records with incomplete
-- business fields and keeps the operational CP-06 data set alive without resetting DB.

DELETE FROM core.events e
WHERE (
    e.event_name IN ('CP05 Live Post Event', 'CP03 Event', 'CP01 Smoke Event', 'Gala Firmowa Q3')
    OR (lower(e.event_name) = 'executive product launch' AND e.source_channel = 'ai_ingest' AND e.description IS NULL)
)
AND (
    e.description IS NULL
    OR e.attendee_count IS NULL
    OR e.budget_estimate IS NULL
);

DELETE FROM core.clients c
WHERE NOT EXISTS (SELECT 1 FROM core.events e WHERE e.client_id = c.client_id)
  AND (c.name ILIKE 'CP%' OR c.name ILIKE '%Smoke%' OR c.name ILIKE '%Gala%' OR c.name ILIKE '%Live Post%');

DELETE FROM core.locations l
WHERE NOT EXISTS (SELECT 1 FROM core.events e WHERE e.location_id = l.location_id)
  AND (l.name ILIKE 'CP%' OR l.name ILIKE '%Smoke%' OR l.name ILIKE '%Gala%' OR l.name ILIKE '%Live Post%');

UPDATE core.events e
SET
    status = CASE
        WHEN split_part(e.event_id::text, '-', 5)::bigint <= 20 THEN 'completed'::core.event_status
        WHEN split_part(e.event_id::text, '-', 5)::bigint <= 28 THEN 'in_progress'::core.event_status
        ELSE 'planned'::core.event_status
    END,
    notes = 'Business ID OP-' || lpad(split_part(e.event_id::text, '-', 5)::bigint::text, 3, '0') ||
        CASE
            WHEN split_part(e.event_id::text, '-', 5)::bigint <= 20 THEN '; completed operational history.'
            WHEN split_part(e.event_id::text, '-', 5)::bigint <= 28 THEN '; currently live for runtime dashboard and replanning tests.'
            ELSE '; future event ready for planning.'
        END
WHERE e.event_id::text LIKE '80000000-0000-0000-0000-%';

DELETE FROM ops.event_outcomes o
WHERE o.event_id::text LIKE '80000000-0000-0000-0000-%'
  AND split_part(o.event_id::text, '-', 5)::bigint > 20;

DELETE FROM ops.actual_timings t
WHERE t.event_id::text LIKE '80000000-0000-0000-0000-%'
  AND split_part(t.event_id::text, '-', 5)::bigint > 20;

COMMIT;

-- ============================================================================
-- Source: scripts\sql\cp08_business_event_names_and_planning_state.sql
-- ============================================================================

BEGIN;

-- CP-08 keeps the local database state, but converts checkpoint seed records into
-- business-readable events and restores future planning records to a not-yet-planned status.

WITH seeded AS (
    SELECT
        e.event_id,
        split_part(e.event_id::text, '-', 5)::bigint AS n,
        l.city,
        l.name AS location_name
    FROM core.events e
    JOIN core.locations l ON l.location_id = e.location_id
    WHERE e.event_id::text LIKE '80000000-0000-0000-0000-%'
)
UPDATE core.events e
SET
    event_name = (ARRAY[
        'Krakow Music Night',
        'Warsaw Executive Summit',
        'Gdansk Product Launch',
        'Poznan Retail Roadshow',
        'Wroclaw Investor Day',
        'Lodz Design Forum',
        'Katowice Tech Expo',
        'Sopot Brand Showcase',
        'Lublin Medical Congress',
        'Torun University Gala',
        'Rzeszow Partner Meetup',
        'Bialystok Logistics Workshop'
    ])[1 + ((s.n - 1) % 12)],
    description = 'Business event for ' || COALESCE(s.location_name, s.city, 'selected venue') ||
        '. The record contains complete planning inputs, operational requirements and post-event history where applicable.',
    notes = CASE
        WHEN s.n <= 20 THEN 'Completed operational history based on realistic company events.'
        WHEN s.n <= 28 THEN 'Live operational event for incident and replanning workflows.'
        ELSE 'Future event ready for first planning. No final assignment is approved yet.'
    END,
    status = CASE
        WHEN s.n <= 20 THEN 'completed'::core.event_status
        WHEN s.n <= 28 THEN 'in_progress'::core.event_status
        WHEN s.n % 3 = 0 THEN 'submitted'::core.event_status
        ELSE 'validated'::core.event_status
    END,
    source_channel = 'operational_seed_cp08'
FROM seeded s
WHERE e.event_id = s.event_id;

UPDATE core.event_requirements r
SET notes = 'Person requirement derived from the event profile and expected service scope.'
WHERE r.requirement_id::text LIKE '84000000-0000-0000-0000-%';

UPDATE core.event_requirements r
SET notes = 'Equipment requirement derived from venue size, audience profile and production setup.'
WHERE r.requirement_id::text LIKE '85000000-0000-0000-0000-%';

UPDATE core.event_requirements r
SET notes = 'Vehicle requirement derived from equipment volume and transport window.'
WHERE r.requirement_id::text LIKE '85500000-0000-0000-0000-%';

DELETE FROM core.assignments a
USING core.events e
WHERE a.event_id = e.event_id
  AND e.event_id::text LIKE '80000000-0000-0000-0000-%'
  AND split_part(e.event_id::text, '-', 5)::bigint > 28
  AND a.is_manual_override IS FALSE;

INSERT INTO core.assignments (
    assignment_id, event_id, resource_type, person_id, equipment_id, vehicle_id,
    assignment_role, planned_start, planned_end, status, is_manual_override,
    is_consumed_in_execution, notes
)
SELECT
    ('89510000-0000-0000-0000-' || lpad(n::text, 12, '0'))::uuid,
    e.event_id,
    'person'::core.assignment_resource_type,
    ('87000000-0000-0000-0000-' || lpad(((n % 48) + 1)::text, 12, '0'))::uuid,
    NULL::uuid,
    NULL::uuid,
    'Live crew lead',
    e.planned_start,
    e.planned_end,
    'planned'::core.assignment_status,
    false,
    n % 2 = 0,
    'Seeded live assignment for operational visibility.'
FROM core.events e
CROSS JOIN LATERAL (SELECT split_part(e.event_id::text, '-', 5)::bigint AS n) s
WHERE e.event_id::text LIKE '80000000-0000-0000-0000-%'
  AND n BETWEEN 21 AND 28
ON CONFLICT (assignment_id) DO UPDATE
SET person_id = EXCLUDED.person_id,
    planned_start = EXCLUDED.planned_start,
    planned_end = EXCLUDED.planned_end,
    status = EXCLUDED.status,
    is_consumed_in_execution = EXCLUDED.is_consumed_in_execution,
    notes = EXCLUDED.notes;

INSERT INTO core.assignments (
    assignment_id, event_id, resource_type, person_id, equipment_id, vehicle_id,
    assignment_role, planned_start, planned_end, status, is_manual_override,
    is_consumed_in_execution, notes
)
SELECT
    ('89520000-0000-0000-0000-' || lpad(n::text, 12, '0'))::uuid,
    e.event_id,
    'equipment'::core.assignment_resource_type,
    NULL::uuid,
    ('88000000-0000-0000-0000-' || lpad(((n % 32) + 1)::text, 12, '0'))::uuid,
    NULL::uuid,
    'Live production kit',
    e.planned_start,
    e.planned_end,
    'planned'::core.assignment_status,
    false,
    n % 3 = 0,
    'Seeded live equipment assignment for operational visibility.'
FROM core.events e
CROSS JOIN LATERAL (SELECT split_part(e.event_id::text, '-', 5)::bigint AS n) s
WHERE e.event_id::text LIKE '80000000-0000-0000-0000-%'
  AND n BETWEEN 21 AND 28
ON CONFLICT (assignment_id) DO UPDATE
SET equipment_id = EXCLUDED.equipment_id,
    planned_start = EXCLUDED.planned_start,
    planned_end = EXCLUDED.planned_end,
    status = EXCLUDED.status,
    is_consumed_in_execution = EXCLUDED.is_consumed_in_execution,
    notes = EXCLUDED.notes;

INSERT INTO core.assignments (
    assignment_id, event_id, resource_type, person_id, equipment_id, vehicle_id,
    assignment_role, planned_start, planned_end, status, is_manual_override,
    is_consumed_in_execution, notes
)
SELECT
    ('89530000-0000-0000-0000-' || lpad(n::text, 12, '0'))::uuid,
    e.event_id,
    'vehicle'::core.assignment_resource_type,
    NULL::uuid,
    NULL::uuid,
    ('89000000-0000-0000-0000-' || lpad(((n % 16) + 1)::text, 12, '0'))::uuid,
    'Live transport unit',
    e.planned_start,
    e.planned_end,
    'planned'::core.assignment_status,
    false,
    n % 4 = 0,
    'Seeded live vehicle assignment for operational visibility.'
FROM core.events e
CROSS JOIN LATERAL (SELECT split_part(e.event_id::text, '-', 5)::bigint AS n) s
WHERE e.event_id::text LIKE '80000000-0000-0000-0000-%'
  AND n BETWEEN 21 AND 28
ON CONFLICT (assignment_id) DO UPDATE
SET vehicle_id = EXCLUDED.vehicle_id,
    planned_start = EXCLUDED.planned_start,
    planned_end = EXCLUDED.planned_end,
    status = EXCLUDED.status,
    is_consumed_in_execution = EXCLUDED.is_consumed_in_execution,
    notes = EXCLUDED.notes;

COMMIT;

-- ============================================================================
-- Source: CP-11 demo planning event
-- ============================================================================

BEGIN;

UPDATE core.events e
SET status = 'validated'::core.event_status
WHERE e.status = 'submitted'::core.event_status
  AND e.planned_start >= NOW()
  AND e.attendee_count IS NOT NULL
  AND e.budget_estimate IS NOT NULL
  AND EXISTS (SELECT 1 FROM core.event_requirements r WHERE r.event_id = e.event_id);

INSERT INTO core.clients (client_id, name, priority, industry, contact_person_name, notes)
VALUES (
    '81000000-0000-0000-0000-000000000901',
    'Demo Production Client',
    'high'::core.priority_level,
    'Live entertainment',
    'Marta Demo',
    'Client used for CP-11 event planning demo.'
)
ON CONFLICT (client_id) DO UPDATE
SET name = EXCLUDED.name,
    priority = EXCLUDED.priority,
    industry = EXCLUDED.industry,
    contact_person_name = EXCLUDED.contact_person_name,
    notes = EXCLUDED.notes;

INSERT INTO core.locations (
    location_id, name, city, address_line, postal_code, country_code,
    location_type, parking_difficulty, access_difficulty, setup_complexity_score, notes
)
VALUES (
    '82000000-0000-0000-0000-000000000901',
    'Demo Arena Main Hall',
    'Krakow',
    'ul. Demonstracyjna 11',
    '30-901',
    'PL',
    'conference_center'::core.location_type,
    4,
    4,
    8,
    'Demo venue with demanding audio setup and limited loading access.'
)
ON CONFLICT (location_id) DO UPDATE
SET name = EXCLUDED.name,
    city = EXCLUDED.city,
    address_line = EXCLUDED.address_line,
    postal_code = EXCLUDED.postal_code,
    country_code = EXCLUDED.country_code,
    location_type = EXCLUDED.location_type,
    parking_difficulty = EXCLUDED.parking_difficulty,
    access_difficulty = EXCLUDED.access_difficulty,
    setup_complexity_score = EXCLUDED.setup_complexity_score,
    notes = EXCLUDED.notes;

INSERT INTO core.equipment_types (equipment_type_id, type_name, category, description, default_setup_minutes, default_teardown_minutes)
VALUES (
    '83000000-0000-0000-0000-000000000901',
    'Demo Premium Audio System',
    'audio',
    'Line-array audio system used to demonstrate baseline versus optimized planning.',
    85,
    50
)
ON CONFLICT (equipment_type_id) DO UPDATE
SET type_name = EXCLUDED.type_name,
    category = EXCLUDED.category,
    description = EXCLUDED.description,
    default_setup_minutes = EXCLUDED.default_setup_minutes,
    default_teardown_minutes = EXCLUDED.default_teardown_minutes;

INSERT INTO core.events (
    event_id, client_id, location_id, event_name, event_type, event_subtype,
    description, attendee_count, planned_start, planned_end, priority, status,
    budget_estimate, currency_code, source_channel, requires_transport,
    requires_setup, requires_teardown, notes
)
VALUES (
    '80000000-0000-0000-0000-000000000901',
    '81000000-0000-0000-0000-000000000901',
    '82000000-0000-0000-0000-000000000901',
    'Demo-plan-event',
    'concert',
    'premium_audio_showcase',
    'Demo event designed to show clear differences between baseline and optimized resource planning.',
    850,
    '2026-09-18 14:00:00+00'::timestamptz,
    '2026-09-18 23:00:00+00'::timestamptz,
    'high'::core.priority_level,
    'validated'::core.event_status,
    68000.00,
    'PLN',
    'demo_cp11',
    true,
    true,
    true,
    'Validated demo event ready to plan. Baseline should prefer cheaper resources, optimized should prefer more reliable resources.'
)
ON CONFLICT (event_id) DO UPDATE
SET event_name = EXCLUDED.event_name,
    event_type = EXCLUDED.event_type,
    event_subtype = EXCLUDED.event_subtype,
    description = EXCLUDED.description,
    attendee_count = EXCLUDED.attendee_count,
    planned_start = EXCLUDED.planned_start,
    planned_end = EXCLUDED.planned_end,
    priority = EXCLUDED.priority,
    status = EXCLUDED.status,
    budget_estimate = EXCLUDED.budget_estimate,
    source_channel = EXCLUDED.source_channel,
    requires_transport = EXCLUDED.requires_transport,
    requires_setup = EXCLUDED.requires_setup,
    requires_teardown = EXCLUDED.requires_teardown,
    notes = EXCLUDED.notes;

INSERT INTO core.resources_people (
    person_id, full_name, role, employment_type, home_base_location_id,
    availability_status, max_daily_hours, max_weekly_hours, cost_per_hour,
    reliability_notes, active
)
VALUES
    ('87000000-0000-0000-0000-000000000901', 'Adam Budget Audio', 'technician_audio'::core.person_role, 'contractor'::core.employment_type, '82000000-0000-0000-0000-000000000901', 'available'::core.resource_status, 10.00, 44.00, 30.00, 'Standard reliability; cost-efficient demo baseline option.', true),
    ('87000000-0000-0000-0000-000000000902', 'Beata Budget Audio', 'technician_audio'::core.person_role, 'contractor'::core.employment_type, '82000000-0000-0000-0000-000000000901', 'available'::core.resource_status, 10.00, 44.00, 35.00, 'Standard reliability; cost-efficient demo baseline option.', true),
    ('87000000-0000-0000-0000-000000000903', 'Celina Budget Audio', 'technician_audio'::core.person_role, 'contractor'::core.employment_type, '82000000-0000-0000-0000-000000000901', 'available'::core.resource_status, 10.00, 44.00, 40.00, 'Standard reliability; cost-efficient demo baseline option.', true),
    ('87000000-0000-0000-0000-000000000904', 'Daniel High Reliability Audio', 'technician_audio'::core.person_role, 'employee'::core.employment_type, '82000000-0000-0000-0000-000000000901', 'available'::core.resource_status, 10.00, 44.00, 70.00, 'high reliability; senior audio engineer for complex live shows.', true),
    ('87000000-0000-0000-0000-000000000905', 'Ewa High Reliability Audio', 'technician_audio'::core.person_role, 'employee'::core.employment_type, '82000000-0000-0000-0000-000000000901', 'available'::core.resource_status, 10.00, 44.00, 75.00, 'high reliability; senior RF and console specialist.', true),
    ('87000000-0000-0000-0000-000000000906', 'Filip High Reliability Audio', 'technician_audio'::core.person_role, 'employee'::core.employment_type, '82000000-0000-0000-0000-000000000901', 'available'::core.resource_status, 10.00, 44.00, 80.00, 'high reliability; backup systems and live failover specialist.', true)
ON CONFLICT (person_id) DO UPDATE
SET full_name = EXCLUDED.full_name,
    role = EXCLUDED.role,
    employment_type = EXCLUDED.employment_type,
    home_base_location_id = EXCLUDED.home_base_location_id,
    availability_status = EXCLUDED.availability_status,
    max_daily_hours = EXCLUDED.max_daily_hours,
    max_weekly_hours = EXCLUDED.max_weekly_hours,
    cost_per_hour = EXCLUDED.cost_per_hour,
    reliability_notes = EXCLUDED.reliability_notes,
    active = EXCLUDED.active,
    updated_at = NOW();

INSERT INTO core.equipment (
    equipment_id, equipment_type_id, asset_tag, serial_number, status,
    warehouse_location_id, transport_requirements, replacement_available,
    hourly_cost_estimate, purchase_date, notes, active
)
VALUES
    ('88000000-0000-0000-0000-000000000901', '83000000-0000-0000-0000-000000000901', 'DEMO-AUDIO-BUDGET-1', 'DEMO-AUD-B-001', 'available'::core.resource_status, '82000000-0000-0000-0000-000000000901', 'standard van case', false, 35.00, '2024-01-15', 'Baseline audio system: cheap, no immediate replacement kit.', true),
    ('88000000-0000-0000-0000-000000000902', '83000000-0000-0000-0000-000000000901', 'DEMO-AUDIO-BUDGET-2', 'DEMO-AUD-B-002', 'available'::core.resource_status, '82000000-0000-0000-0000-000000000901', 'standard van case', false, 38.00, '2024-02-10', 'Baseline audio system: cheap, no immediate replacement kit.', true),
    ('88000000-0000-0000-0000-000000000903', '83000000-0000-0000-0000-000000000901', 'DEMO-AUDIO-RELIABLE-1', 'DEMO-AUD-R-001', 'available'::core.resource_status, '82000000-0000-0000-0000-000000000901', 'flight case with spare amp', true, 45.00, '2025-04-20', 'Optimized audio system: higher reliability and replacement path.', true),
    ('88000000-0000-0000-0000-000000000904', '83000000-0000-0000-0000-000000000901', 'DEMO-AUDIO-RELIABLE-2', 'DEMO-AUD-R-002', 'available'::core.resource_status, '82000000-0000-0000-0000-000000000901', 'flight case with spare amp', true, 48.00, '2025-05-18', 'Optimized audio system: higher reliability and replacement path.', true)
ON CONFLICT (equipment_id) DO UPDATE
SET equipment_type_id = EXCLUDED.equipment_type_id,
    asset_tag = EXCLUDED.asset_tag,
    serial_number = EXCLUDED.serial_number,
    status = EXCLUDED.status,
    warehouse_location_id = EXCLUDED.warehouse_location_id,
    transport_requirements = EXCLUDED.transport_requirements,
    replacement_available = EXCLUDED.replacement_available,
    hourly_cost_estimate = EXCLUDED.hourly_cost_estimate,
    purchase_date = EXCLUDED.purchase_date,
    notes = EXCLUDED.notes,
    active = EXCLUDED.active,
    updated_at = NOW();

INSERT INTO core.vehicles (
    vehicle_id, vehicle_name, vehicle_type, registration_number, capacity_notes,
    status, home_location_id, cost_per_km, cost_per_hour, active
)
VALUES (
    '89000000-0000-0000-0000-000000000901',
    'Demo Audio Cargo Van',
    'van'::core.vehicle_type,
    'KR901DE',
    'Dedicated van for demo audio systems and crew transport.',
    'available'::core.resource_status,
    '82000000-0000-0000-0000-000000000901',
    2.80,
    85.00,
    true
)
ON CONFLICT (vehicle_id) DO UPDATE
SET vehicle_name = EXCLUDED.vehicle_name,
    vehicle_type = EXCLUDED.vehicle_type,
    registration_number = EXCLUDED.registration_number,
    capacity_notes = EXCLUDED.capacity_notes,
    status = EXCLUDED.status,
    home_location_id = EXCLUDED.home_location_id,
    cost_per_km = EXCLUDED.cost_per_km,
    cost_per_hour = EXCLUDED.cost_per_hour,
    active = EXCLUDED.active,
    updated_at = NOW();

INSERT INTO core.people_availability (availability_id, person_id, available_from, available_to, is_available, source, notes)
SELECT
    ('87100000-0000-0000-0000-' || lpad(i::text, 12, '0'))::uuid,
    ('87000000-0000-0000-0000-' || lpad(i::text, 12, '0'))::uuid,
    '2026-09-18 08:00:00+00'::timestamptz,
    '2026-09-19 02:00:00+00'::timestamptz,
    true,
    'demo_cp11',
    'Available for Demo-plan-event.'
FROM generate_series(901, 906) AS s(i)
ON CONFLICT (availability_id) DO UPDATE
SET available_from = EXCLUDED.available_from,
    available_to = EXCLUDED.available_to,
    is_available = EXCLUDED.is_available,
    source = EXCLUDED.source,
    notes = EXCLUDED.notes;

INSERT INTO core.equipment_availability (availability_id, equipment_id, available_from, available_to, is_available, source, notes)
SELECT
    ('88100000-0000-0000-0000-' || lpad(i::text, 12, '0'))::uuid,
    ('88000000-0000-0000-0000-' || lpad(i::text, 12, '0'))::uuid,
    '2026-09-18 08:00:00+00'::timestamptz,
    '2026-09-19 02:00:00+00'::timestamptz,
    true,
    'demo_cp11',
    'Available for Demo-plan-event.'
FROM generate_series(901, 904) AS s(i)
ON CONFLICT (availability_id) DO UPDATE
SET available_from = EXCLUDED.available_from,
    available_to = EXCLUDED.available_to,
    is_available = EXCLUDED.is_available,
    source = EXCLUDED.source,
    notes = EXCLUDED.notes;

INSERT INTO core.vehicle_availability (availability_id, vehicle_id, available_from, available_to, is_available, source, notes)
VALUES (
    '89100000-0000-0000-0000-000000000901',
    '89000000-0000-0000-0000-000000000901',
    '2026-09-18 08:00:00+00'::timestamptz,
    '2026-09-19 02:00:00+00'::timestamptz,
    true,
    'demo_cp11',
    'Available for Demo-plan-event.'
)
ON CONFLICT (availability_id) DO UPDATE
SET available_from = EXCLUDED.available_from,
    available_to = EXCLUDED.available_to,
    is_available = EXCLUDED.is_available,
    source = EXCLUDED.source,
    notes = EXCLUDED.notes;

INSERT INTO core.event_requirements (
    requirement_id, event_id, requirement_type, role_required, equipment_type_id,
    vehicle_type_required, quantity, mandatory, required_start, required_end, notes
)
VALUES
    ('84000000-0000-0000-0000-000000000901', '80000000-0000-0000-0000-000000000901', 'person_role'::core.requirement_type, 'technician_audio'::core.person_role, NULL, NULL, 3.00, true, '2026-09-18 14:00:00+00'::timestamptz, '2026-09-18 23:00:00+00'::timestamptz, 'Three audio technicians required for complex live audio setup.'),
    ('85000000-0000-0000-0000-000000000901', '80000000-0000-0000-0000-000000000901', 'equipment_type'::core.requirement_type, NULL, '83000000-0000-0000-0000-000000000901', NULL, 2.00, true, '2026-09-18 14:00:00+00'::timestamptz, '2026-09-18 23:00:00+00'::timestamptz, 'Two premium audio systems required for main PA and redundant side-fill coverage.'),
    ('85500000-0000-0000-0000-000000000901', '80000000-0000-0000-0000-000000000901', 'vehicle_type'::core.requirement_type, NULL, NULL, 'van'::core.vehicle_type, 1.00, true, '2026-09-18 14:00:00+00'::timestamptz, '2026-09-18 23:00:00+00'::timestamptz, 'One van required for audio cargo and crew movement.')
ON CONFLICT (requirement_id) DO UPDATE
SET requirement_type = EXCLUDED.requirement_type,
    role_required = EXCLUDED.role_required,
    equipment_type_id = EXCLUDED.equipment_type_id,
    vehicle_type_required = EXCLUDED.vehicle_type_required,
    quantity = EXCLUDED.quantity,
    mandatory = EXCLUDED.mandatory,
    required_start = EXCLUDED.required_start,
    required_end = EXCLUDED.required_end,
    notes = EXCLUDED.notes;

DELETE FROM core.assignments
WHERE event_id = '80000000-0000-0000-0000-000000000901'
  AND is_manual_override IS FALSE;

COMMIT;


-- CP-12 realistic planning calibration: keep historical cases business-like and make ML value visible.
BEGIN;

UPDATE core.resources_people p
SET cost_per_hour = CASE
        WHEN p.role IN ('project_manager', 'stage_manager') THEN (140 + (split_part(p.person_id::text, '-', 5)::bigint % 5) * 18)::numeric(10,2)
        WHEN p.role IN ('technician_audio', 'technician_video', 'technician_light') THEN (75 + (split_part(p.person_id::text, '-', 5)::bigint % 6) * 22)::numeric(10,2)
        WHEN p.role = 'driver' THEN (65 + (split_part(p.person_id::text, '-', 5)::bigint % 4) * 12)::numeric(10,2)
        ELSE (70 + (split_part(p.person_id::text, '-', 5)::bigint % 5) * 10)::numeric(10,2)
    END,
    reliability_notes = CASE
        WHEN split_part(p.person_id::text, '-', 5)::bigint % 4 = 0 THEN 'high reliability; senior operator with strong on-time delivery and low incident history.'
        WHEN split_part(p.person_id::text, '-', 5)::bigint % 4 = 1 THEN 'reliable standard crew member; good delivery history with normal supervision.'
        WHEN split_part(p.person_id::text, '-', 5)::bigint % 4 = 2 THEN 'cost-efficient available resource; suitable for non-critical slots.'
        ELSE 'high reliability backup-ready resource; recommended for critical live-event assignments.'
    END,
    max_daily_hours = CASE WHEN p.role IN ('project_manager', 'stage_manager') THEN 12 ELSE 10 END,
    updated_at = NOW()
WHERE p.person_id::text LIKE '87000000-0000-0000-0000-%';

UPDATE core.equipment eq
SET hourly_cost_estimate = CASE
        WHEN eq.equipment_type_id = '83000000-0000-0000-0000-000000000001' THEN (120 + (split_part(eq.equipment_id::text, '-', 5)::bigint % 5) * 45)::numeric(10,2)
        WHEN eq.equipment_type_id = '83000000-0000-0000-0000-000000000002' THEN (170 + (split_part(eq.equipment_id::text, '-', 5)::bigint % 4) * 55)::numeric(10,2)
        WHEN eq.equipment_type_id = '83000000-0000-0000-0000-000000000004' THEN (130 + (split_part(eq.equipment_id::text, '-', 5)::bigint % 5) * 35)::numeric(10,2)
        ELSE (70 + (split_part(eq.equipment_id::text, '-', 5)::bigint % 6) * 24)::numeric(10,2)
    END,
    replacement_available = (split_part(eq.equipment_id::text, '-', 5)::bigint % 3 <> 1),
    notes = CASE
        WHEN split_part(eq.equipment_id::text, '-', 5)::bigint % 3 <> 1 THEN 'Production-ready asset with available backup path and recent service check.'
        ELSE 'Lower-cost asset without confirmed backup; use only for non-critical assignments.'
    END,
    updated_at = NOW()
WHERE eq.equipment_id::text LIKE '88000000-0000-0000-0000-%';

UPDATE core.vehicles v
SET cost_per_hour = CASE
        WHEN v.vehicle_type = 'truck' THEN (165 + (split_part(v.vehicle_id::text, '-', 5)::bigint % 4) * 30)::numeric(10,2)
        WHEN v.vehicle_type = 'van' THEN (115 + (split_part(v.vehicle_id::text, '-', 5)::bigint % 4) * 20)::numeric(10,2)
        ELSE (80 + (split_part(v.vehicle_id::text, '-', 5)::bigint % 4) * 14)::numeric(10,2)
    END,
    cost_per_km = CASE
        WHEN v.vehicle_type = 'truck' THEN 4.20
        WHEN v.vehicle_type = 'van' THEN 3.10
        ELSE 2.40
    END,
    updated_at = NOW()
WHERE v.vehicle_id::text LIKE '89000000-0000-0000-0000-%';

UPDATE core.events e
SET event_name = CASE (split_part(e.event_id::text, '-', 5)::bigint % 6)
        WHEN 0 THEN 'Regional Sales Kickoff ' || lpad(split_part(e.event_id::text, '-', 5)::bigint::text, 2, '0')
        WHEN 1 THEN 'Krakow Product Showcase ' || lpad(split_part(e.event_id::text, '-', 5)::bigint::text, 2, '0')
        WHEN 2 THEN 'Executive Partner Summit ' || lpad(split_part(e.event_id::text, '-', 5)::bigint::text, 2, '0')
        WHEN 3 THEN 'Retail Roadshow Evening ' || lpad(split_part(e.event_id::text, '-', 5)::bigint::text, 2, '0')
        WHEN 4 THEN 'Investor Demo Forum ' || lpad(split_part(e.event_id::text, '-', 5)::bigint::text, 2, '0')
        ELSE 'City Music Showcase ' || lpad(split_part(e.event_id::text, '-', 5)::bigint::text, 2, '0')
    END,
    description = 'Realistic operations case for planning-model calibration. Budget is full event budget; planner cost covers assignable people, equipment and vehicles only.',
    attendee_count = (180 + (split_part(e.event_id::text, '-', 5)::bigint % 10) * 85)::integer,
    budget_estimate = (28000 + (split_part(e.event_id::text, '-', 5)::bigint % 12) * 6500)::numeric(12,2),
    priority = CASE WHEN split_part(e.event_id::text, '-', 5)::bigint % 5 = 0 THEN 'critical'::core.priority_level WHEN split_part(e.event_id::text, '-', 5)::bigint % 3 = 0 THEN 'high'::core.priority_level ELSE 'medium'::core.priority_level END,
    status = CASE WHEN e.status IN ('draft'::core.event_status, 'submitted'::core.event_status) THEN 'validated'::core.event_status ELSE e.status END,
    source_channel = 'operational_seed_cp12',
    notes = 'CP-12 calibrated case: resource cost, reliability and backup coverage are intentionally varied to demonstrate baseline-vs-optimized planning value.',
    updated_at = NOW()
WHERE e.event_id::text LIKE '80000000-0000-0000-0000-%'
  AND e.source_channel <> 'demo_cp11';

UPDATE ops.event_outcomes o
SET actual_cost = (e.budget_estimate * (0.78 + ((split_part(e.event_id::text, '-', 5)::bigint % 7) * 0.025)))::numeric(12,2),
    total_delay_minutes = CASE WHEN split_part(e.event_id::text, '-', 5)::bigint % 4 = 0 THEN 45 ELSE 8 + (split_part(e.event_id::text, '-', 5)::bigint % 6) * 4 END,
    client_satisfaction_score = CASE WHEN split_part(e.event_id::text, '-', 5)::bigint % 4 = 0 THEN 3 ELSE 4 + (split_part(e.event_id::text, '-', 5)::bigint % 2) END,
    internal_quality_score = CASE WHEN split_part(e.event_id::text, '-', 5)::bigint % 4 = 0 THEN 3 ELSE 4 END,
    summary_notes = 'CP-12 realistic outcome: cost, delay and quality calibrated for current ML retraining.'
FROM core.events e
WHERE e.event_id = o.event_id
  AND e.event_id::text LIKE '80000000-0000-0000-0000-%';

UPDATE core.resources_people
SET cost_per_hour = CASE person_id
        WHEN '87000000-0000-0000-0000-000000000901' THEN 95.00
        WHEN '87000000-0000-0000-0000-000000000902' THEN 105.00
        WHEN '87000000-0000-0000-0000-000000000903' THEN 110.00
        WHEN '87000000-0000-0000-0000-000000000904' THEN 205.00
        WHEN '87000000-0000-0000-0000-000000000905' THEN 220.00
        WHEN '87000000-0000-0000-0000-000000000906' THEN 235.00
        ELSE cost_per_hour
    END,
    reliability_notes = CASE
        WHEN person_id IN ('87000000-0000-0000-0000-000000000904','87000000-0000-0000-0000-000000000905','87000000-0000-0000-0000-000000000906') THEN 'high reliability; senior live audio engineer with proven low-delay incident history.'
        ELSE 'cost-efficient baseline audio technician; available but not preferred for critical demo slots.'
    END,
    updated_at = NOW()
WHERE person_id IN (
    '87000000-0000-0000-0000-000000000901', '87000000-0000-0000-0000-000000000902',
    '87000000-0000-0000-0000-000000000903', '87000000-0000-0000-0000-000000000904',
    '87000000-0000-0000-0000-000000000905', '87000000-0000-0000-0000-000000000906'
);

UPDATE core.equipment
SET hourly_cost_estimate = CASE equipment_id
        WHEN '88000000-0000-0000-0000-000000000901' THEN 155.00
        WHEN '88000000-0000-0000-0000-000000000902' THEN 165.00
        WHEN '88000000-0000-0000-0000-000000000903' THEN 360.00
        WHEN '88000000-0000-0000-0000-000000000904' THEN 380.00
        ELSE hourly_cost_estimate
    END,
    replacement_available = equipment_id IN ('88000000-0000-0000-0000-000000000903','88000000-0000-0000-0000-000000000904'),
    notes = CASE
        WHEN equipment_id IN ('88000000-0000-0000-0000-000000000903','88000000-0000-0000-0000-000000000904') THEN 'High-reliability audio system with spare amplifier and replacement path for critical live events.'
        ELSE 'Lower-cost audio system; acceptable baseline option with limited redundancy.'
    END,
    updated_at = NOW()
WHERE equipment_id IN (
    '88000000-0000-0000-0000-000000000901', '88000000-0000-0000-0000-000000000902',
    '88000000-0000-0000-0000-000000000903', '88000000-0000-0000-0000-000000000904'
);

UPDATE core.vehicles
SET cost_per_hour = 165.00,
    cost_per_km = 3.60,
    capacity_notes = 'Demo van sized for audio racks, crew transport and same-day fallback delivery.',
    updated_at = NOW()
WHERE vehicle_id = '89000000-0000-0000-0000-000000000901';

UPDATE core.events
SET budget_estimate = 52000.00,
    attendee_count = 720,
    priority = 'critical'::core.priority_level,
    notes = 'CP-12 demo: baseline should choose lower-cost resources; optimized should trade higher assignment cost for lower risk, stronger reliability and backup coverage.',
    status = 'validated'::core.event_status,
    updated_at = NOW()
WHERE event_id = '80000000-0000-0000-0000-000000000901';

DELETE FROM core.assignments
WHERE event_id = '80000000-0000-0000-0000-000000000901'
  AND is_manual_override IS FALSE;

COMMIT;






-- CP-12 training sample completion: feature snapshots, timings and outcomes for current seeded events.
BEGIN;

INSERT INTO ai.event_features (
    event_id, feature_event_type, feature_event_subtype, feature_city, feature_location_type,
    feature_attendee_count, feature_attendee_bucket, feature_setup_complexity_score,
    feature_access_difficulty, feature_parking_difficulty, feature_priority,
    feature_day_of_week, feature_month, feature_season, feature_requires_transport,
    feature_requires_setup, feature_requires_teardown, feature_required_person_count,
    feature_required_equipment_count, feature_required_vehicle_count, feature_estimated_distance_km,
    feature_client_priority, generated_at
)
SELECT
    e.event_id,
    e.event_type,
    e.event_subtype,
    l.city,
    l.location_type::text,
    e.attendee_count,
    CASE WHEN e.attendee_count < 250 THEN 'small' WHEN e.attendee_count < 700 THEN 'medium' ELSE 'large' END,
    l.setup_complexity_score,
    l.access_difficulty,
    l.parking_difficulty,
    e.priority::text,
    EXTRACT(ISODOW FROM e.planned_start)::smallint,
    EXTRACT(MONTH FROM e.planned_start)::smallint,
    CASE WHEN EXTRACT(MONTH FROM e.planned_start) IN (12,1,2) THEN 'winter' WHEN EXTRACT(MONTH FROM e.planned_start) IN (3,4,5) THEN 'spring' WHEN EXTRACT(MONTH FROM e.planned_start) IN (6,7,8) THEN 'summer' ELSE 'autumn' END,
    e.requires_transport,
    e.requires_setup,
    e.requires_teardown,
    COALESCE(req.person_count, 0)::integer,
    COALESCE(req.equipment_count, 0)::integer,
    COALESCE(req.vehicle_count, 0)::integer,
    (15 + (split_part(e.event_id::text, '-', 5)::bigint % 18) * 6)::numeric(10,2),
    c.priority::text,
    NOW()
FROM core.events e
JOIN core.locations l ON l.location_id = e.location_id
JOIN core.clients c ON c.client_id = e.client_id
LEFT JOIN (
    SELECT
        event_id,
        SUM(CASE WHEN requirement_type IN ('person_role','person_skill') THEN quantity ELSE 0 END) AS person_count,
        SUM(CASE WHEN requirement_type = 'equipment_type' THEN quantity ELSE 0 END) AS equipment_count,
        SUM(CASE WHEN requirement_type = 'vehicle_type' THEN quantity ELSE 0 END) AS vehicle_count
    FROM core.event_requirements
    GROUP BY event_id
) req ON req.event_id = e.event_id
WHERE e.event_id::text LIKE '80000000-0000-0000-0000-%'
ON CONFLICT (event_id) DO UPDATE
SET feature_event_type = EXCLUDED.feature_event_type,
    feature_event_subtype = EXCLUDED.feature_event_subtype,
    feature_city = EXCLUDED.feature_city,
    feature_location_type = EXCLUDED.feature_location_type,
    feature_attendee_count = EXCLUDED.feature_attendee_count,
    feature_attendee_bucket = EXCLUDED.feature_attendee_bucket,
    feature_setup_complexity_score = EXCLUDED.feature_setup_complexity_score,
    feature_access_difficulty = EXCLUDED.feature_access_difficulty,
    feature_parking_difficulty = EXCLUDED.feature_parking_difficulty,
    feature_priority = EXCLUDED.feature_priority,
    feature_day_of_week = EXCLUDED.feature_day_of_week,
    feature_month = EXCLUDED.feature_month,
    feature_season = EXCLUDED.feature_season,
    feature_requires_transport = EXCLUDED.feature_requires_transport,
    feature_requires_setup = EXCLUDED.feature_requires_setup,
    feature_requires_teardown = EXCLUDED.feature_requires_teardown,
    feature_required_person_count = EXCLUDED.feature_required_person_count,
    feature_required_equipment_count = EXCLUDED.feature_required_equipment_count,
    feature_required_vehicle_count = EXCLUDED.feature_required_vehicle_count,
    feature_estimated_distance_km = EXCLUDED.feature_estimated_distance_km,
    feature_client_priority = EXCLUDED.feature_client_priority,
    generated_at = EXCLUDED.generated_at;

INSERT INTO ops.actual_timings (
    timing_id, event_id, phase_name, planned_start, planned_end, actual_start, actual_end,
    delay_reason_code, notes
)
SELECT
    ('89800000-0000-0000-0000-' || lpad(split_part(e.event_id::text, '-', 5), 12, '0'))::uuid,
    e.event_id,
    'other'::ops.phase_name,
    e.planned_start,
    e.planned_end,
    e.planned_start + make_interval(mins => (split_part(e.event_id::text, '-', 5)::integer % 9)),
    e.planned_start + make_interval(mins => (
        260
        + COALESCE(e.attendee_count, 0) / 4
        + COALESCE(l.setup_complexity_score, 1) * 18
        + COALESCE(l.access_difficulty, 1) * 9
        + COALESCE(l.parking_difficulty, 1) * 6
        + CASE WHEN e.priority = 'critical'::core.priority_level THEN 40 WHEN e.priority = 'high'::core.priority_level THEN 25 ELSE 0 END
        + (split_part(e.event_id::text, '-', 5)::integer % 11) * 7
    )),
    CASE WHEN split_part(e.event_id::text, '-', 5)::bigint % 4 = 0 THEN 'resource_delay' ELSE NULL END,
    'CP-12 calibrated actual duration sample for ML retraining.'
FROM core.events e
JOIN core.locations l ON l.location_id = e.location_id
WHERE e.event_id::text LIKE '80000000-0000-0000-0000-%'
ON CONFLICT (timing_id) DO UPDATE
SET planned_start = EXCLUDED.planned_start,
    planned_end = EXCLUDED.planned_end,
    actual_start = EXCLUDED.actual_start,
    actual_end = EXCLUDED.actual_end,
    delay_reason_code = EXCLUDED.delay_reason_code,
    notes = EXCLUDED.notes;

INSERT INTO ops.event_outcomes (
    event_id, finished_on_time, total_delay_minutes, actual_cost, overtime_cost,
    transport_cost, sla_breached, client_satisfaction_score, internal_quality_score,
    margin_estimate, summary_notes, closed_at
)
SELECT
    e.event_id,
    (split_part(e.event_id::text, '-', 5)::bigint % 4 <> 0),
    CASE WHEN split_part(e.event_id::text, '-', 5)::bigint % 4 = 0 THEN 45 ELSE 8 + (split_part(e.event_id::text, '-', 5)::bigint % 6) * 4 END,
    (e.budget_estimate * (0.78 + ((split_part(e.event_id::text, '-', 5)::bigint % 7) * 0.025)))::numeric(12,2),
    CASE WHEN split_part(e.event_id::text, '-', 5)::bigint % 4 = 0 THEN 1200 ELSE 300 END,
    (600 + (split_part(e.event_id::text, '-', 5)::bigint % 5) * 180)::numeric(12,2),
    (split_part(e.event_id::text, '-', 5)::bigint % 4 = 0),
    CASE WHEN split_part(e.event_id::text, '-', 5)::bigint % 4 = 0 THEN 3 ELSE 4 + (split_part(e.event_id::text, '-', 5)::bigint % 2) END,
    CASE WHEN split_part(e.event_id::text, '-', 5)::bigint % 4 = 0 THEN 3 ELSE 4 END,
    (e.budget_estimate * 0.18)::numeric(12,2),
    'CP-12 calibrated outcome sample for current model training and demo planning.',
    e.planned_end + interval '1 day'
FROM core.events e
WHERE e.event_id::text LIKE '80000000-0000-0000-0000-%'
ON CONFLICT (event_id) DO UPDATE
SET finished_on_time = EXCLUDED.finished_on_time,
    total_delay_minutes = EXCLUDED.total_delay_minutes,
    actual_cost = EXCLUDED.actual_cost,
    overtime_cost = EXCLUDED.overtime_cost,
    transport_cost = EXCLUDED.transport_cost,
    sla_breached = EXCLUDED.sla_breached,
    client_satisfaction_score = EXCLUDED.client_satisfaction_score,
    internal_quality_score = EXCLUDED.internal_quality_score,
    margin_estimate = EXCLUDED.margin_estimate,
    summary_notes = EXCLUDED.summary_notes,
    closed_at = EXCLUDED.closed_at;

COMMIT;
