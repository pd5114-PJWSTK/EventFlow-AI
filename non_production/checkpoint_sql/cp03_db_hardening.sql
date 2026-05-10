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
