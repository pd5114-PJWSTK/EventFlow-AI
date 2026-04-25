BEGIN;

-- =========================================================
-- CLIENTS
-- =========================================================
INSERT INTO core.clients (
    client_id, name, industry, priority, sla_type,
    contact_person_name, contact_email, contact_phone, notes
)
VALUES
(
    '11111111-1111-1111-1111-111111111111',
    'TechVision Polska',
    'Technology',
    'high',
    'premium',
    'Anna Nowak',
    'anna.nowak@techvision.pl',
    '+48500100100',
    'Strategiczny klient konferencyjny'
),
(
    '22222222-2222-2222-2222-222222222222',
    'City Events Group',
    'Events',
    'medium',
    'standard',
    'Piotr ZieliĹ„ski',
    'piotr.zielinski@cityevents.pl',
    '+48500200200',
    'Klient organizujÄ…cy eventy miejskie'
),
(
    '33333333-3333-3333-3333-333333333333',
    'Retail Future Sp. z o.o.',
    'Retail',
    'critical',
    'vip',
    'Magdalena Lis',
    'm.lis@retailfuture.pl',
    '+48500300300',
    'Wysoka presja SLA'
);

-- =========================================================
-- LOCATIONS
-- =========================================================
INSERT INTO core.locations (
    location_id, name, city, address_line, postal_code, country_code,
    latitude, longitude, location_type,
    parking_difficulty, access_difficulty, setup_complexity_score, notes
)
VALUES
(
    'aaaaaaa1-aaaa-aaaa-aaaa-aaaaaaaaaaa1',
    'EXPO XXI Warszawa',
    'Warszawa',
    'Ignacego PrÄ…dzyĹ„skiego 12/14',
    '01-222',
    'PL',
    52.227000,
    20.967000,
    'conference_center',
    3,
    2,
    6,
    'DuĹĽa przestrzeĹ„ eventowa'
),
(
    'aaaaaaa2-aaaa-aaaa-aaaa-aaaaaaaaaaa2',
    'Tauron Arena KrakĂłw',
    'KrakĂłw',
    'StanisĹ‚awa Lema 7',
    '31-571',
    'PL',
    50.068500,
    19.991900,
    'stadium',
    4,
    3,
    8,
    'DuĹĽa hala, skomplikowany setup'
),
(
    'aaaaaaa3-aaaa-aaaa-aaaa-aaaaaaaaaaa3',
    'Magazyn Centralny',
    'Warszawa',
    'Magazynowa 1',
    '02-100',
    'PL',
    52.190000,
    20.950000,
    'warehouse',
    1,
    1,
    2,
    'Baza sprzÄ™tu'
),
(
    'aaaaaaa4-aaaa-aaaa-aaaa-aaaaaaaaaaa4',
    'Plac WolnoĹ›ci PoznaĹ„',
    'PoznaĹ„',
    'Plac WolnoĹ›ci',
    '61-738',
    'PL',
    52.408300,
    16.925200,
    'outdoor',
    4,
    4,
    7,
    'Event plenerowy w centrum'
);

-- =========================================================
-- SKILLS
-- =========================================================
INSERT INTO core.skills (
    skill_id, skill_name, skill_category, description
)
VALUES
(
    'bbbbbbb1-bbbb-bbbb-bbbb-bbbbbbbbbbb1',
    'Audio Setup',
    'technical',
    'Konfiguracja i obsĹ‚uga audio'
),
(
    'bbbbbbb2-bbbb-bbbb-bbbb-bbbbbbbbbbb2',
    'Lighting Setup',
    'technical',
    'Konfiguracja i obsĹ‚uga oĹ›wietlenia'
),
(
    'bbbbbbb3-bbbb-bbbb-bbbb-bbbbbbbbbbb3',
    'Video Setup',
    'technical',
    'Konfiguracja ekranĂłw i video'
),
(
    'bbbbbbb4-bbbb-bbbb-bbbb-bbbbbbbbbbb4',
    'Event Coordination',
    'operations',
    'Koordynacja wydarzenia'
);

-- =========================================================
-- PEOPLE
-- =========================================================
INSERT INTO core.resources_people (
    person_id, full_name, role, employment_type,
    home_base_location_id, availability_status,
    max_daily_hours, max_weekly_hours, cost_per_hour,
    reliability_notes, active
)
VALUES
(
    'ccccccc1-cccc-cccc-cccc-ccccccccccc1',
    'Jan Kowalski',
    'technician_audio',
    'employee',
    'aaaaaaa3-aaaa-aaaa-aaaa-aaaaaaaaaaa3',
    'available',
    10.0,
    50.0,
    70.00,
    'DoĹ›wiadczony technik audio',
    TRUE
),
(
    'ccccccc2-cccc-cccc-cccc-ccccccccccc2',
    'Marta WiĹ›niewska',
    'technician_light',
    'employee',
    'aaaaaaa3-aaaa-aaaa-aaaa-aaaaaaaaaaa3',
    'available',
    10.0,
    50.0,
    72.00,
    'Specjalizacja: sceny i koncerty',
    TRUE
),
(
    'ccccccc3-cccc-cccc-cccc-ccccccccccc3',
    'Piotr Mazur',
    'coordinator',
    'employee',
    'aaaaaaa3-aaaa-aaaa-aaaa-aaaaaaaaaaa3',
    'available',
    12.0,
    55.0,
    95.00,
    'Koordynator operacyjny',
    TRUE
),
(
    'ccccccc4-cccc-cccc-cccc-ccccccccccc4',
    'Ola DÄ…browska',
    'technician_video',
    'freelancer',
    'aaaaaaa3-aaaa-aaaa-aaaa-aaaaaaaaaaa3',
    'available',
    8.0,
    32.0,
    85.00,
    'Freelance video tech',
    TRUE
);

-- =========================================================
-- PEOPLE SKILLS
-- =========================================================
INSERT INTO core.people_skills (
    person_id, skill_id, skill_level, certified, last_verified_at, notes
)
VALUES
(
    'ccccccc1-cccc-cccc-cccc-ccccccccccc1',
    'bbbbbbb1-bbbb-bbbb-bbbb-bbbbbbbbbbb1',
    5,
    TRUE,
    NOW() - INTERVAL '30 days',
    'Senior audio'
),
(
    'ccccccc2-cccc-cccc-cccc-ccccccccccc2',
    'bbbbbbb2-bbbb-bbbb-bbbb-bbbbbbbbbbb2',
    5,
    TRUE,
    NOW() - INTERVAL '45 days',
    'Senior lighting'
),
(
    'ccccccc3-cccc-cccc-cccc-ccccccccccc3',
    'bbbbbbb4-bbbb-bbbb-bbbb-bbbbbbbbbbb4',
    5,
    TRUE,
    NOW() - INTERVAL '20 days',
    'Lead coordinator'
),
(
    'ccccccc4-cccc-cccc-cccc-ccccccccccc4',
    'bbbbbbb3-bbbb-bbbb-bbbb-bbbbbbbbbbb3',
    4,
    TRUE,
    NOW() - INTERVAL '15 days',
    'Video operator'
);

-- =========================================================
-- EQUIPMENT TYPES
-- =========================================================
INSERT INTO core.equipment_types (
    equipment_type_id, type_name, category, description,
    default_setup_minutes, default_teardown_minutes
)
VALUES
(
    'ddddddd1-dddd-dddd-dddd-ddddddddddd1',
    'Audio Set Large',
    'audio',
    'DuĹĽy zestaw audio na konferencje i koncerty',
    120,
    90
),
(
    'ddddddd2-dddd-dddd-dddd-ddddddddddd2',
    'Lighting Rig Medium',
    'lighting',
    'Ĺšredni zestaw oĹ›wietleniowy',
    150,
    120
),
(
    'ddddddd3-dddd-dddd-dddd-ddddddddddd3',
    'LED Screen Set',
    'video',
    'Zestaw ekranĂłw LED',
    180,
    150
);

-- =========================================================
-- EQUIPMENT
-- =========================================================
INSERT INTO core.equipment (
    equipment_id, equipment_type_id, asset_tag, serial_number, status,
    warehouse_location_id, transport_requirements,
    replacement_available, hourly_cost_estimate, purchase_date, notes, active
)
VALUES
(
    'eeeeeee1-eeee-eeee-eeee-eeeeeeeeeee1',
    'ddddddd1-dddd-dddd-dddd-ddddddddddd1',
    'AUD-001',
    'SN-AUD-001',
    'available',
    'aaaaaaa3-aaaa-aaaa-aaaa-aaaaaaaaaaa3',
    'Van required',
    TRUE,
    120.00,
    '2024-02-10',
    'GĹ‚Ăłwny set audio',
    TRUE
),
(
    'eeeeeee2-eeee-eeee-eeee-eeeeeeeeeee2',
    'ddddddd2-dddd-dddd-dddd-ddddddddddd2',
    'LGT-001',
    'SN-LGT-001',
    'available',
    'aaaaaaa3-aaaa-aaaa-aaaa-aaaaaaaaaaa3',
    'Van required',
    TRUE,
    140.00,
    '2024-03-15',
    'ĹšwiatĹ‚a scena',
    TRUE
),
(
    'eeeeeee3-eeee-eeee-eeee-eeeeeeeeeee3',
    'ddddddd3-dddd-dddd-dddd-ddddddddddd3',
    'VID-001',
    'SN-VID-001',
    'available',
    'aaaaaaa3-aaaa-aaaa-aaaa-aaaaaaaaaaa3',
    'Truck preferred',
    FALSE,
    200.00,
    '2024-05-20',
    'LED screens premium',
    TRUE
);

-- =========================================================
-- VEHICLES
-- =========================================================
INSERT INTO core.vehicles (
    vehicle_id, vehicle_name, vehicle_type, registration_number,
    capacity_notes, status, home_location_id,
    cost_per_km, cost_per_hour, active
)
VALUES
(
    'fffffff1-ffff-ffff-ffff-fffffffffff1',
    'Van 1',
    'van',
    'WX12345',
    'SprzÄ™t audio/light',
    'available',
    'aaaaaaa3-aaaa-aaaa-aaaa-aaaaaaaaaaa3',
    1.80,
    40.00,
    TRUE
),
(
    'fffffff2-ffff-ffff-ffff-fffffffffff2',
    'Truck 1',
    'truck',
    'WX54321',
    'DuĹĽy sprzÄ™t i LED',
    'available',
    'aaaaaaa3-aaaa-aaaa-aaaa-aaaaaaaaaaa3',
    3.20,
    65.00,
    TRUE
);

-- =========================================================
-- EVENTS
-- =========================================================
INSERT INTO core.events (
    event_id, client_id, location_id, event_name, event_type, event_subtype,
    description, attendee_count, planned_start, planned_end,
    priority, status, budget_estimate, currency_code,
    source_channel, requires_transport, requires_setup, requires_teardown,
    notes, created_by
)
VALUES
(
    '99999991-9999-9999-9999-999999999991',
    '11111111-1111-1111-1111-111111111111',
    'aaaaaaa1-aaaa-aaaa-aaaa-aaaaaaaaaaa1',
    'TechVision Annual Summit',
    'conference',
    'corporate',
    'Konferencja roczna klienta technologicznego',
    500,
    '2026-05-15 08:00:00+02',
    '2026-05-15 18:00:00+02',
    'high',
    'planned',
    45000.00,
    'PLN',
    'sales_team',
    TRUE,
    TRUE,
    TRUE,
    'Wymagany wysoki standard wykonania',
    'demo_admin'
),
(
    '99999992-9999-9999-9999-999999999992',
    '22222222-2222-2222-2222-222222222222',
    'aaaaaaa2-aaaa-aaaa-aaaa-aaaaaaaaaaa2',
    'KrakĂłw Music Night',
    'concert',
    'live_music',
    'Wieczorny koncert z peĹ‚nÄ… oprawÄ… audio-light',
    3000,
    '2026-05-20 14:00:00+02',
    '2026-05-20 23:30:00+02',
    'critical',
    'planned',
    120000.00,
    'PLN',
    'account_manager',
    TRUE,
    TRUE,
    TRUE,
    'DuĹĽe ryzyko operacyjne, skomplikowana scena',
    'demo_admin'
),
(
    '99999993-9999-9999-9999-999999999993',
    '33333333-3333-3333-3333-333333333333',
    'aaaaaaa4-aaaa-aaaa-aaaa-aaaaaaaaaaa4',
    'Retail Future Outdoor Launch',
    'brand_activation',
    'outdoor_launch',
    'Premiera produktu w centrum miasta',
    800,
    '2026-05-25 10:00:00+02',
    '2026-05-25 17:00:00+02',
    'critical',
    'planned',
    60000.00,
    'PLN',
    'marketing_team',
    TRUE,
    TRUE,
    TRUE,
    'Plener, wysokie ryzyko pogodowe',
    'demo_admin'
);

-- =========================================================
-- EVENT REQUIREMENTS
-- =========================================================
-- Event 1
INSERT INTO core.event_requirements (
    requirement_id, event_id, requirement_type,
    role_required, skill_id, equipment_type_id, vehicle_type_required,
    quantity, mandatory, required_start, required_end, notes
)
VALUES
(
    '12111111-0000-0000-0000-000000000001',
    '99999991-9999-9999-9999-999999999991',
    'person_role',
    'coordinator',
    NULL,
    NULL,
    NULL,
    1,
    TRUE,
    '2026-05-15 07:00:00+02',
    '2026-05-15 19:00:00+02',
    'Koordynator prowadzÄ…cy'
),
(
    '12111111-0000-0000-0000-000000000002',
    '99999991-9999-9999-9999-999999999991',
    'person_skill',
    NULL,
    'bbbbbbb1-bbbb-bbbb-bbbb-bbbbbbbbbbb1',
    NULL,
    NULL,
    1,
    TRUE,
    '2026-05-15 06:00:00+02',
    '2026-05-15 19:00:00+02',
    'Audio specialist'
),
(
    '12111111-0000-0000-0000-000000000003',
    '99999991-9999-9999-9999-999999999991',
    'equipment_type',
    NULL,
    NULL,
    'ddddddd1-dddd-dddd-dddd-ddddddddddd1',
    NULL,
    1,
    TRUE,
    '2026-05-15 06:00:00+02',
    '2026-05-15 19:00:00+02',
    'DuĹĽy audio set'
),
(
    '12111111-0000-0000-0000-000000000004',
    '99999991-9999-9999-9999-999999999991',
    'vehicle_type',
    NULL,
    NULL,
    NULL,
    'van',
    1,
    TRUE,
    '2026-05-15 05:30:00+02',
    '2026-05-15 20:00:00+02',
    'Transport audio'
);

-- Event 2
INSERT INTO core.event_requirements (
    requirement_id, event_id, requirement_type,
    role_required, skill_id, equipment_type_id, vehicle_type_required,
    quantity, mandatory, required_start, required_end, notes
)
VALUES
(
    '12111111-0000-0000-0000-000000000005',
    '99999992-9999-9999-9999-999999999992',
    'person_role',
    'coordinator',
    NULL,
    NULL,
    NULL,
    1,
    TRUE,
    '2026-05-20 10:00:00+02',
    '2026-05-21 00:30:00+02',
    'Koordynator eventu koncertowego'
),
(
    '12111111-0000-0000-0000-000000000006',
    '99999992-9999-9999-9999-999999999992',
    'person_skill',
    NULL,
    'bbbbbbb1-bbbb-bbbb-bbbb-bbbbbbbbbbb1',
    NULL,
    NULL,
    1,
    TRUE,
    '2026-05-20 09:00:00+02',
    '2026-05-21 00:30:00+02',
    'Audio setup'
),
(
    '12111111-0000-0000-0000-000000000007',
    '99999992-9999-9999-9999-999999999992',
    'person_skill',
    NULL,
    'bbbbbbb2-bbbb-bbbb-bbbb-bbbbbbbbbbb2',
    NULL,
    NULL,
    1,
    TRUE,
    '2026-05-20 09:00:00+02',
    '2026-05-21 00:30:00+02',
    'Lighting setup'
),
(
    '12111111-0000-0000-0000-000000000008',
    '99999992-9999-9999-9999-999999999992',
    'equipment_type',
    NULL,
    NULL,
    'ddddddd1-dddd-dddd-dddd-ddddddddddd1',
    NULL,
    1,
    TRUE,
    '2026-05-20 09:00:00+02',
    '2026-05-21 00:30:00+02',
    'Audio set'
),
(
    '12111111-0000-0000-0000-000000000009',
    '99999992-9999-9999-9999-999999999992',
    'equipment_type',
    NULL,
    NULL,
    'ddddddd2-dddd-dddd-dddd-ddddddddddd2',
    NULL,
    1,
    TRUE,
    '2026-05-20 09:00:00+02',
    '2026-05-21 00:30:00+02',
    'Lighting rig'
),
(
    '12111111-0000-0000-0000-000000000010',
    '99999992-9999-9999-9999-999999999992',
    'vehicle_type',
    NULL,
    NULL,
    NULL,
    'truck',
    1,
    TRUE,
    '2026-05-20 08:00:00+02',
    '2026-05-21 01:00:00+02',
    'Transport ciÄ™ĹĽki'
);

-- Event 3
INSERT INTO core.event_requirements (
    requirement_id, event_id, requirement_type,
    role_required, skill_id, equipment_type_id, vehicle_type_required,
    quantity, mandatory, required_start, required_end, notes
)
VALUES
(
    '12111111-0000-0000-0000-000000000011',
    '99999993-9999-9999-9999-999999999993',
    'person_role',
    'coordinator',
    NULL,
    NULL,
    NULL,
    1,
    TRUE,
    '2026-05-25 07:00:00+02',
    '2026-05-25 18:00:00+02',
    'Koordynator outdoor'
),
(
    '12111111-0000-0000-0000-000000000012',
    '99999993-9999-9999-9999-999999999993',
    'person_skill',
    NULL,
    'bbbbbbb3-bbbb-bbbb-bbbb-bbbbbbbbbbb3',
    NULL,
    NULL,
    1,
    TRUE,
    '2026-05-25 06:30:00+02',
    '2026-05-25 18:00:00+02',
    'Video / LED'
),
(
    '12111111-0000-0000-0000-000000000013',
    '99999993-9999-9999-9999-999999999993',
    'equipment_type',
    NULL,
    NULL,
    'ddddddd3-dddd-dddd-dddd-ddddddddddd3',
    NULL,
    1,
    TRUE,
    '2026-05-25 06:00:00+02',
    '2026-05-25 18:30:00+02',
    'LED screen set'
),
(
    '12111111-0000-0000-0000-000000000014',
    '99999993-9999-9999-9999-999999999993',
    'vehicle_type',
    NULL,
    NULL,
    NULL,
    'truck',
    1,
    TRUE,
    '2026-05-25 05:30:00+02',
    '2026-05-25 19:00:00+02',
    'Transport LED'
);

-- =========================================================
-- PLANNER RUN
-- =========================================================
INSERT INTO ai.planner_runs (
    planner_run_id, started_at, finished_at, run_status,
    objective_version, initiated_by, trigger_reason,
    input_snapshot, total_cost, total_risk_score, sla_risk_count, notes
)
VALUES
(
    '77777777-7777-7777-7777-777777777777',
    NOW() - INTERVAL '5 minutes',
    NOW(),
    'completed',
    'v1.0',
    'demo_admin',
    'manual',
    '{"mode":"demo","events":3}'::jsonb,
    18500.00,
    1.82,
    1,
    'Pierwszy run demonstracyjny'
);

-- =========================================================
-- ASSIGNMENTS
-- Event 1
-- =========================================================
INSERT INTO core.assignments (
    assignment_id, event_id, resource_type,
    person_id, equipment_id, vehicle_id,
    assignment_role, planned_start, planned_end, status,
    planner_run_id, is_manual_override, notes
)
VALUES
(
    '66666661-6666-6666-6666-666666666661',
    '99999991-9999-9999-9999-999999999991',
    'person',
    'ccccccc3-cccc-cccc-cccc-ccccccccccc3',
    NULL,
    NULL,
    'Lead Coordinator',
    '2026-05-15 07:00:00+02',
    '2026-05-15 19:00:00+02',
    'planned',
    '77777777-7777-7777-7777-777777777777',
    FALSE,
    'Koordynacja caĹ‚oĹ›ci'
),
(
    '66666661-6666-6666-6666-666666666662',
    '99999991-9999-9999-9999-999999999991',
    'person',
    'ccccccc1-cccc-cccc-cccc-ccccccccccc1',
    NULL,
    NULL,
    'Audio Technician',
    '2026-05-15 06:00:00+02',
    '2026-05-15 19:00:00+02',
    'planned',
    '77777777-7777-7777-7777-777777777777',
    FALSE,
    'ObsĹ‚uga audio'
),
(
    '66666661-6666-6666-6666-666666666663',
    '99999991-9999-9999-9999-999999999991',
    'equipment',
    NULL,
    'eeeeeee1-eeee-eeee-eeee-eeeeeeeeeee1',
    NULL,
    'Main Audio Set',
    '2026-05-15 06:00:00+02',
    '2026-05-15 19:00:00+02',
    'planned',
    '77777777-7777-7777-7777-777777777777',
    FALSE,
    'Audio set przypisany'
),
(
    '66666661-6666-6666-6666-666666666664',
    '99999991-9999-9999-9999-999999999991',
    'vehicle',
    NULL,
    NULL,
    'fffffff1-ffff-ffff-ffff-fffffffffff1',
    'Audio Transport',
    '2026-05-15 05:30:00+02',
    '2026-05-15 20:00:00+02',
    'planned',
    '77777777-7777-7777-7777-777777777777',
    FALSE,
    'Van dla audio'
);

-- =========================================================
-- ASSIGNMENTS
-- Event 2
-- =========================================================
INSERT INTO core.assignments (
    assignment_id, event_id, resource_type,
    person_id, equipment_id, vehicle_id,
    assignment_role, planned_start, planned_end, status,
    planner_run_id, is_manual_override, notes
)
VALUES
(
    '66666662-6666-6666-6666-666666666661',
    '99999992-9999-9999-9999-999999999992',
    'person',
    'ccccccc3-cccc-cccc-cccc-ccccccccccc3',
    NULL,
    NULL,
    'Event Coordinator',
    '2026-05-20 10:00:00+02',
    '2026-05-21 00:30:00+02',
    'planned',
    '77777777-7777-7777-7777-777777777777',
    FALSE,
    'Koordynacja koncertu'
),
(
    '66666662-6666-6666-6666-666666666662',
    '99999992-9999-9999-9999-999999999992',
    'person',
    'ccccccc1-cccc-cccc-cccc-ccccccccccc1',
    NULL,
    NULL,
    'Audio Lead',
    '2026-05-20 09:00:00+02',
    '2026-05-21 00:30:00+02',
    'planned',
    '77777777-7777-7777-7777-777777777777',
    FALSE,
    'Audio koncert'
),
(
    '66666662-6666-6666-6666-666666666663',
    '99999992-9999-9999-9999-999999999992',
    'person',
    'ccccccc2-cccc-cccc-cccc-ccccccccccc2',
    NULL,
    NULL,
    'Lighting Lead',
    '2026-05-20 09:00:00+02',
    '2026-05-21 00:30:00+02',
    'planned',
    '77777777-7777-7777-7777-777777777777',
    FALSE,
    'Lighting koncert'
),
(
    '66666662-6666-6666-6666-666666666664',
    '99999992-9999-9999-9999-999999999992',
    'equipment',
    NULL,
    'eeeeeee1-eeee-eeee-eeee-eeeeeeeeeee1',
    NULL,
    'Audio Set',
    '2026-05-20 09:00:00+02',
    '2026-05-21 00:30:00+02',
    'planned',
    '77777777-7777-7777-7777-777777777777',
    FALSE,
    'Audio main'
),
(
    '66666662-6666-6666-6666-666666666665',
    '99999992-9999-9999-9999-999999999992',
    'equipment',
    NULL,
    'eeeeeee2-eeee-eeee-eeee-eeeeeeeeeee2',
    NULL,
    'Lighting Rig',
    '2026-05-20 09:00:00+02',
    '2026-05-21 00:30:00+02',
    'planned',
    '77777777-7777-7777-7777-777777777777',
    FALSE,
    'Lighting main'
),
(
    '66666662-6666-6666-6666-666666666666',
    '99999992-9999-9999-9999-999999999992',
    'vehicle',
    NULL,
    NULL,
    'fffffff2-ffff-ffff-ffff-fffffffffff2',
    'Heavy Transport',
    '2026-05-20 08:00:00+02',
    '2026-05-21 01:00:00+02',
    'planned',
    '77777777-7777-7777-7777-777777777777',
    FALSE,
    'Truck dla duĹĽego setupu'
);

-- =========================================================
-- ASSIGNMENTS
-- Event 3
-- =========================================================
INSERT INTO core.assignments (
    assignment_id, event_id, resource_type,
    person_id, equipment_id, vehicle_id,
    assignment_role, planned_start, planned_end, status,
    planner_run_id, is_manual_override, notes
)
VALUES
(
    '66666663-6666-6666-6666-666666666661',
    '99999993-9999-9999-9999-999999999993',
    'person',
    'ccccccc3-cccc-cccc-cccc-ccccccccccc3',
    NULL,
    NULL,
    'Outdoor Coordinator',
    '2026-05-25 07:00:00+02',
    '2026-05-25 18:00:00+02',
    'planned',
    '77777777-7777-7777-7777-777777777777',
    FALSE,
    'Koordynator launchu'
),
(
    '66666663-6666-6666-6666-666666666662',
    '99999993-9999-9999-9999-999999999993',
    'person',
    'ccccccc4-cccc-cccc-cccc-ccccccccccc4',
    NULL,
    NULL,
    'Video Lead',
    '2026-05-25 06:30:00+02',
    '2026-05-25 18:00:00+02',
    'planned',
    '77777777-7777-7777-7777-777777777777',
    FALSE,
    'ObsĹ‚uga LED i video'
),
(
    '66666663-6666-6666-6666-666666666663',
    '99999993-9999-9999-9999-999999999993',
    'equipment',
    NULL,
    'eeeeeee3-eeee-eeee-eeee-eeeeeeeeeee3',
    NULL,
    'LED Screen Set',
    '2026-05-25 06:00:00+02',
    '2026-05-25 18:30:00+02',
    'planned',
    '77777777-7777-7777-7777-777777777777',
    FALSE,
    'LED premium'
),
(
    '66666663-6666-6666-6666-666666666664',
    '99999993-9999-9999-9999-999999999993',
    'vehicle',
    NULL,
    NULL,
    'fffffff2-ffff-ffff-ffff-fffffffffff2',
    'LED Transport',
    '2026-05-25 05:30:00+02',
    '2026-05-25 19:00:00+02',
    'planned',
    '77777777-7777-7777-7777-777777777777',
    FALSE,
    'Truck dla LED'
);

-- =========================================================
-- TRANSPORT LEGS
-- =========================================================
INSERT INTO core.transport_legs (
    transport_leg_id, event_id, vehicle_id, driver_person_id,
    origin_location_id, destination_location_id,
    planned_departure, planned_arrival,
    estimated_distance_km, estimated_duration_minutes, notes
)
VALUES
(
    '88888881-8888-8888-8888-888888888881',
    '99999991-9999-9999-9999-999999999991',
    'fffffff1-ffff-ffff-ffff-fffffffffff1',
    'ccccccc1-cccc-cccc-cccc-ccccccccccc1',
    'aaaaaaa3-aaaa-aaaa-aaaa-aaaaaaaaaaa3',
    'aaaaaaa1-aaaa-aaaa-aaaa-aaaaaaaaaaa1',
    '2026-05-15 05:30:00+02',
    '2026-05-15 06:10:00+02',
    18.00,
    40,
    'Transport na konferencjÄ™'
),
(
    '88888882-8888-8888-8888-888888888882',
    '99999992-9999-9999-9999-999999999992',
    'fffffff2-ffff-ffff-ffff-fffffffffff2',
    'ccccccc3-cccc-cccc-cccc-ccccccccccc3',
    'aaaaaaa3-aaaa-aaaa-aaaa-aaaaaaaaaaa3',
    'aaaaaaa2-aaaa-aaaa-aaaa-aaaaaaaaaaa2',
    '2026-05-20 08:00:00+02',
    '2026-05-20 12:30:00+02',
    295.00,
    270,
    'Transport do Krakowa'
),
(
    '88888883-8888-8888-8888-888888888883',
    '99999993-9999-9999-9999-999999999993',
    'fffffff2-ffff-ffff-ffff-fffffffffff2',
    'ccccccc4-cccc-cccc-cccc-ccccccccccc4',
    'aaaaaaa3-aaaa-aaaa-aaaa-aaaaaaaaaaa3',
    'aaaaaaa4-aaaa-aaaa-aaaa-aaaaaaaaaaa4',
    '2026-05-25 05:30:00+02',
    '2026-05-25 09:00:00+02',
    310.00,
    210,
    'Transport do Poznania'
);

-- =========================================================
-- AI EVENT FEATURES
-- =========================================================
INSERT INTO ai.event_features (
    event_id,
    feature_event_type, feature_event_subtype, feature_city, feature_location_type,
    feature_attendee_count, feature_attendee_bucket,
    feature_setup_complexity_score, feature_access_difficulty, feature_parking_difficulty,
    feature_priority, feature_day_of_week, feature_month, feature_season,
    feature_requires_transport, feature_requires_setup, feature_requires_teardown,
    feature_required_person_count, feature_required_equipment_count, feature_required_vehicle_count,
    feature_estimated_distance_km, feature_client_priority, generated_at
)
VALUES
(
    '99999991-9999-9999-9999-999999999991',
    'conference', 'corporate', 'Warszawa', 'conference_center',
    500, '250_1000',
    6, 2, 3,
    'high', 5, 5, 'spring',
    TRUE, TRUE, TRUE,
    2, 1, 1,
    18.00, 'high', NOW()
),
(
    '99999992-9999-9999-9999-999999999992',
    'concert', 'live_music', 'KrakĂłw', 'stadium',
    3000, '1000_plus',
    8, 3, 4,
    'critical', 3, 5, 'spring',
    TRUE, TRUE, TRUE,
    3, 2, 1,
    295.00, 'medium', NOW()
),
(
    '99999993-9999-9999-9999-999999999993',
    'brand_activation', 'outdoor_launch', 'PoznaĹ„', 'outdoor',
    800, '250_1000',
    7, 4, 4,
    'critical', 1, 5, 'spring',
    TRUE, TRUE, TRUE,
    2, 1, 1,
    310.00, 'critical', NOW()
);

-- =========================================================
-- AI MODELS
-- =========================================================
INSERT INTO ai.models (
    model_id, model_name, model_version, prediction_type,
    status, training_data_from, training_data_to, metrics, created_at
)
VALUES
(
    '55555555-5555-5555-5555-555555555551',
    'duration_estimator',
    'v1',
    'duration_estimate',
    'active',
    NOW() - INTERVAL '180 days',
    NOW() - INTERVAL '1 day',
    '{"mae_minutes": 24.5}'::jsonb,
    NOW()
),
(
    '55555555-5555-5555-5555-555555555552',
    'delay_risk_classifier',
    'v1',
    'delay_risk',
    'active',
    NOW() - INTERVAL '180 days',
    NOW() - INTERVAL '1 day',
    '{"auc": 0.81}'::jsonb,
    NOW()
),
(
    '55555555-5555-5555-5555-555555555553',
    'headcount_estimator',
    'v1',
    'required_headcount',
    'active',
    NOW() - INTERVAL '180 days',
    NOW() - INTERVAL '1 day',
    '{"mae_people": 0.7}'::jsonb,
    NOW()
);

-- =========================================================
-- AI PREDICTIONS
-- =========================================================
INSERT INTO ai.predictions (
    prediction_id, event_id, assignment_id, model_id, prediction_type,
    predicted_value, predicted_label, confidence_score,
    explanation, feature_snapshot, generated_at
)
VALUES
(
    '44444444-4444-4444-4444-444444444441',
    '99999991-9999-9999-9999-999999999991',
    NULL,
    '55555555-5555-5555-5555-555555555551',
    'duration_estimate',
    660.0,
    '11h_total_operation',
    0.84,
    'Konferencja w Warszawie zwykle wymaga dĹ‚uĹĽszego setupu niĹĽ plan bazowy.',
    '{"city":"Warszawa","attendee_count":500,"event_type":"conference"}'::jsonb,
    NOW()
),
(
    '44444444-4444-4444-4444-444444444442',
    '99999991-9999-9999-9999-999999999991',
    NULL,
    '55555555-5555-5555-5555-555555555553',
    'required_headcount',
    3.0,
    '3_people_recommended',
    0.78,
    'AI rekomenduje dodatkowy zasĂłb wspierajÄ…cy przy setupie.',
    '{"event_type":"conference","complexity":6}'::jsonb,
    NOW()
),
(
    '44444444-4444-4444-4444-444444444443',
    '99999992-9999-9999-9999-999999999992',
    NULL,
    '55555555-5555-5555-5555-555555555552',
    'delay_risk',
    0.72,
    'high_risk',
    0.81,
    'DuĹĽy koncert, dĹ‚ugi transport i zĹ‚oĹĽony setup zwiÄ™kszajÄ… ryzyko opĂłĹşnienia.',
    '{"event_type":"concert","distance_km":295,"complexity":8}'::jsonb,
    NOW()
),
(
    '44444444-4444-4444-4444-444444444444',
    '99999993-9999-9999-9999-999999999993',
    NULL,
    '55555555-5555-5555-5555-555555555552',
    'delay_risk',
    0.68,
    'high_risk',
    0.76,
    'Outdoor i centrum miasta zwiÄ™kszajÄ… niepewnoĹ›Ä‡ operacyjnÄ….',
    '{"event_type":"brand_activation","location_type":"outdoor"}'::jsonb,
    NOW()
);

-- =========================================================
-- OPS ACTUAL TIMINGS
-- =========================================================
INSERT INTO ops.actual_timings (
    timing_id, event_id, assignment_id, phase_name,
    planned_start, actual_start, planned_end, actual_end,
    delay_reason_code, notes, created_at
)
VALUES
(
    '31313131-3131-3131-3131-313131313131',
    '99999991-9999-9999-9999-999999999991',
    NULL,
    'setup',
    '2026-05-15 06:00:00+02',
    '2026-05-15 06:10:00+02',
    '2026-05-15 08:00:00+02',
    '2026-05-15 08:25:00+02',
    'late_loadin',
    'OpĂłĹşnienie przy wnoszeniu sprzÄ™tu',
    NOW()
),
(
    '31313131-3131-3131-3131-313131313132',
    '99999992-9999-9999-9999-999999999992',
    NULL,
    'setup',
    '2026-05-20 09:00:00+02',
    '2026-05-20 09:20:00+02',
    '2026-05-20 14:00:00+02',
    '2026-05-20 14:40:00+02',
    'complex_stage',
    'Scena wymagaĹ‚a dodatkowego czasu',
    NOW()
),
(
    '31313131-3131-3131-3131-313131313133',
    '99999993-9999-9999-9999-999999999993',
    NULL,
    'setup',
    '2026-05-25 06:00:00+02',
    '2026-05-25 06:30:00+02',
    '2026-05-25 10:00:00+02',
    '2026-05-25 10:50:00+02',
    'weather_delay',
    'Warunki pogodowe spowolniĹ‚y setup',
    NOW()
);

-- =========================================================
-- OPS INCIDENTS
-- =========================================================
INSERT INTO ops.incidents (
    incident_id, event_id, assignment_id, incident_type, severity,
    reported_at, resolved_at, reported_by, root_cause,
    description, cost_impact, sla_impact, created_at
)
VALUES
(
    '23232323-2323-2323-2323-232323232321',
    '99999992-9999-9999-9999-999999999992',
    NULL,
    'delay',
    'high',
    '2026-05-20 13:30:00+02',
    '2026-05-20 15:00:00+02',
    'Piotr Mazur',
    'DĹ‚uĹĽszy setup sceny',
    'OpĂłĹşnione rozpoczÄ™cie koncertu o 40 minut',
    3500.00,
    TRUE,
    NOW()
),
(
    '23232323-2323-2323-2323-232323232322',
    '99999993-9999-9999-9999-999999999993',
    NULL,
    'weather_issue',
    'medium',
    '2026-05-25 09:45:00+02',
    '2026-05-25 11:00:00+02',
    'Piotr Mazur',
    'Silny wiatr podczas montaĹĽu',
    'KoniecznoĹ›Ä‡ dodatkowego zabezpieczenia LED',
    1200.00,
    FALSE,
    NOW()
);

-- =========================================================
-- OPS EVENT OUTCOMES
-- =========================================================
INSERT INTO ops.event_outcomes (
    event_id, finished_on_time, total_delay_minutes,
    actual_cost, overtime_cost, transport_cost,
    sla_breached, client_satisfaction_score, internal_quality_score,
    margin_estimate, summary_notes, closed_at, created_at
)
VALUES
(
    '99999991-9999-9999-9999-999999999991',
    FALSE,
    25,
    47200.00,
    600.00,
    450.00,
    FALSE,
    8.8,
    8.2,
    7800.00,
    'Konferencja wykonana poprawnie, niewielkie opĂłĹşnienie setupu.',
    NOW(),
    NOW()
),
(
    '99999992-9999-9999-9999-999999999992',
    FALSE,
    40,
    127500.00,
    2200.00,
    1800.00,
    TRUE,
    7.4,
    7.0,
    9500.00,
    'Koncert z naruszeniem SLA przez opĂłĹşnienie startu.',
    NOW(),
    NOW()
),
(
    '99999993-9999-9999-9999-999999999993',
    FALSE,
    50,
    63400.00,
    1300.00,
    1700.00,
    FALSE,
    8.1,
    7.8,
    6400.00,
    'Outdoor launch opĂłĹşniony przez pogodÄ™.',
    NOW(),
    NOW()
);

COMMIT;
