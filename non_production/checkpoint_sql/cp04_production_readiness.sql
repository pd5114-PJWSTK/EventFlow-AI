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
SET contact_person_name = 'Piotr Zieliński',
    notes = 'Klient organizujący eventy miejskie'
WHERE client_id = '11111111-1111-1111-1111-111111111111';

UPDATE core.locations
SET address_line = 'Ignacego Prądzyńskiego 12/14',
    notes = 'Duża przestrzeń eventowa'
WHERE location_id = 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa';

UPDATE core.locations
SET name = 'Tauron Arena Kraków',
    city = 'Kraków',
    address_line = 'Stanisława Lema 7',
    notes = 'Duża hala, skomplikowany setup'
WHERE location_id = 'aaaaaaa2-aaaa-aaaa-aaaa-aaaaaaaaaaa2';

UPDATE core.locations
SET name = 'Baza sprzętu'
WHERE location_id = 'aaaaaaa3-aaaa-aaaa-aaaa-aaaaaaaaaaa3';

UPDATE core.locations
SET name = 'Plac Wolności Poznań',
    city = 'Poznań',
    address_line = 'Plac Wolności'
WHERE location_id = 'aaaaaaa4-aaaa-aaaa-aaaa-aaaaaaaaaaa4';

UPDATE core.skills
SET description = 'Konfiguracja i obsługa audio'
WHERE skill_id = 'bbbbbbb1-bbbb-bbbb-bbbb-bbbbbbbbbbb1';

UPDATE core.skills
SET description = 'Konfiguracja i obsługa oświetlenia'
WHERE skill_id = 'bbbbbbb2-bbbb-bbbb-bbbb-bbbbbbbbbbb2';

UPDATE core.skills
SET description = 'Konfiguracja ekranów i video'
WHERE skill_id = 'bbbbbbb3-bbbb-bbbb-bbbb-bbbbbbbbbbb3';

UPDATE core.resources_people
SET full_name = 'Marta Wiśniewska'
WHERE person_id = 'ccccccc2-cccc-cccc-cccc-ccccccccccc2';

UPDATE core.resources_people
SET full_name = 'Ola Dąbrowska'
WHERE person_id = 'ccccccc4-cccc-cccc-cccc-ccccccccccc4';

UPDATE core.equipment_types
SET description = 'Duży zestaw audio na konferencje i koncerty'
WHERE equipment_type_id = 'ddddddd1-dddd-dddd-dddd-ddddddddddd1';

UPDATE core.equipment_types
SET description = 'Średni zestaw oświetleniowy'
WHERE equipment_type_id = 'ddddddd2-dddd-dddd-dddd-ddddddddddd2';

UPDATE core.equipment_types
SET description = 'Zestaw ekranów LED'
WHERE equipment_type_id = 'ddddddd3-dddd-dddd-dddd-ddddddddddd3';

UPDATE core.equipment
SET asset_tag = 'Główny set audio'
WHERE equipment_id = 'eeeeeee1-eeee-eeee-eeee-eeeeeeeeeee1';

UPDATE core.equipment
SET asset_tag = 'Światła scena'
WHERE equipment_id = 'eeeeeee2-eeee-eeee-eeee-eeeeeeeeeee2';

UPDATE core.vehicles
SET capacity_notes = 'Sprzęt audio/light'
WHERE vehicle_id = 'fffffff1-ffff-ffff-ffff-fffffffffff1';

UPDATE core.vehicles
SET capacity_notes = 'Duży sprzęt i LED'
WHERE vehicle_id = 'fffffff2-ffff-ffff-ffff-fffffffffff2';

UPDATE core.events
SET event_name = 'Kraków Music Night',
    description = 'Wieczorny koncert z pełną oprawą audio-light',
    notes = 'Duże ryzyko operacyjne, skomplikowana scena'
WHERE event_id = '99999992-9999-9999-9999-999999999992';

COMMIT;
