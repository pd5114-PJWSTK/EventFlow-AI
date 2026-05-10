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
