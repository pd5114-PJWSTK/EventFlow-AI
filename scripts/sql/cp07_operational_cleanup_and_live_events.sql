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
