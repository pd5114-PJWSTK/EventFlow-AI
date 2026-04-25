BEGIN;

-- ---------------------------------------------------------
-- Extensions
-- ---------------------------------------------------------
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- ---------------------------------------------------------
-- Schemas
-- ---------------------------------------------------------
CREATE SCHEMA IF NOT EXISTS core;
CREATE SCHEMA IF NOT EXISTS ops;
CREATE SCHEMA IF NOT EXISTS ai;

-- =========================================================
-- ENUM TYPES
-- =========================================================

-- ---------------------------
-- core enums
-- ---------------------------
CREATE TYPE core.event_status AS ENUM (
    'draft',
    'submitted',
    'validated',
    'planned',
    'confirmed',
    'in_progress',
    'completed',
    'cancelled'
);

CREATE TYPE core.priority_level AS ENUM (
    'low',
    'medium',
    'high',
    'critical'
);

CREATE TYPE core.location_type AS ENUM (
    'indoor',
    'outdoor',
    'hybrid',
    'warehouse',
    'conference_center',
    'stadium',
    'office',
    'other'
);

CREATE TYPE core.resource_status AS ENUM (
    'available',
    'reserved',
    'in_use',
    'maintenance',
    'unavailable',
    'retired'
);

CREATE TYPE core.person_role AS ENUM (
    'technician_audio',
    'technician_light',
    'technician_video',
    'stage_manager',
    'coordinator',
    'driver',
    'warehouse_operator',
    'project_manager',
    'freelancer',
    'other'
);

CREATE TYPE core.employment_type AS ENUM (
    'employee',
    'contractor',
    'freelancer',
    'agency_staff',
    'other'
);

CREATE TYPE core.requirement_type AS ENUM (
    'person_skill',
    'person_role',
    'equipment_type',
    'vehicle_type',
    'time_buffer',
    'other'
);

CREATE TYPE core.assignment_resource_type AS ENUM (
    'person',
    'equipment',
    'vehicle'
);

CREATE TYPE core.assignment_status AS ENUM (
    'proposed',
    'planned',
    'confirmed',
    'active',
    'completed',
    'cancelled',
    'failed'
);

CREATE TYPE core.vehicle_type AS ENUM (
    'van',
    'truck',
    'car',
    'trailer',
    'other'
);

-- ---------------------------
-- ops enums
-- ---------------------------
CREATE TYPE ops.log_type AS ENUM (
    'event_created',
    'planning_started',
    'planning_completed',
    'resource_assigned',
    'resource_unassigned',
    'transport_started',
    'transport_arrived',
    'setup_started',
    'setup_completed',
    'event_started',
    'event_completed',
    'teardown_started',
    'teardown_completed',
    'delay_reported',
    'incident_reported',
    'status_changed',
    'manual_override',
    'note'
);

CREATE TYPE ops.phase_name AS ENUM (
    'loadout',
    'transport_outbound',
    'setup',
    'soundcheck',
    'event_runtime',
    'teardown',
    'transport_return',
    'other'
);

CREATE TYPE ops.incident_type AS ENUM (
    'delay',
    'equipment_failure',
    'staff_absence',
    'traffic_issue',
    'weather_issue',
    'client_change_request',
    'venue_access_issue',
    'sla_risk',
    'safety_issue',
    'other'
);

CREATE TYPE ops.incident_severity AS ENUM (
    'low',
    'medium',
    'high',
    'critical'
);

CREATE TYPE ops.author_type AS ENUM (
    'system',
    'planner',
    'coordinator',
    'technician',
    'manager',
    'client',
    'other'
);

-- ---------------------------
-- ai enums
-- ---------------------------
CREATE TYPE ai.prediction_type AS ENUM (
    'duration_estimate',
    'required_headcount',
    'required_equipment_count',
    'delay_risk',
    'sla_breach_risk',
    'incident_risk',
    'cost_estimate',
    'recommended_buffer_minutes',
    'resource_reliability_score',
    'fatigue_score',
    'other'
);

CREATE TYPE ai.model_status AS ENUM (
    'training',
    'active',
    'deprecated',
    'archived'
);

CREATE TYPE ai.planner_run_status AS ENUM (
    'started',
    'completed',
    'failed',
    'cancelled'
);

-- =========================================================
-- CORE SCHEMA
-- =========================================================

-- ---------------------------------------------------------
-- Clients
-- ---------------------------------------------------------
CREATE TABLE core.clients (
    client_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    industry TEXT,
    priority core.priority_level NOT NULL DEFAULT 'medium',
    sla_type TEXT,
    contact_person_name TEXT,
    contact_email TEXT,
    contact_phone TEXT,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ---------------------------------------------------------
-- Locations
-- ---------------------------------------------------------
CREATE TABLE core.locations (
    location_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT,
    city TEXT NOT NULL,
    address_line TEXT,
    postal_code TEXT,
    country_code CHAR(2) DEFAULT 'PL',
    latitude NUMERIC(9,6),
    longitude NUMERIC(9,6),
    location_type core.location_type NOT NULL DEFAULT 'other',
    parking_difficulty SMALLINT NOT NULL DEFAULT 1 CHECK (parking_difficulty BETWEEN 1 AND 5),
    access_difficulty SMALLINT NOT NULL DEFAULT 1 CHECK (access_difficulty BETWEEN 1 AND 5),
    setup_complexity_score SMALLINT NOT NULL DEFAULT 1 CHECK (setup_complexity_score BETWEEN 1 AND 10),
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ---------------------------------------------------------
-- Events
-- ---------------------------------------------------------
CREATE TABLE core.events (
    event_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID NOT NULL REFERENCES core.clients(client_id) ON DELETE RESTRICT,
    location_id UUID NOT NULL REFERENCES core.locations(location_id) ON DELETE RESTRICT,
    event_name TEXT NOT NULL,
    event_type TEXT NOT NULL,
    event_subtype TEXT,
    description TEXT,
    attendee_count INTEGER CHECK (attendee_count >= 0),
    planned_start TIMESTAMPTZ NOT NULL,
    planned_end TIMESTAMPTZ NOT NULL,
    priority core.priority_level NOT NULL DEFAULT 'medium',
    status core.event_status NOT NULL DEFAULT 'draft',
    budget_estimate NUMERIC(12,2),
    currency_code CHAR(3) NOT NULL DEFAULT 'PLN',
    source_channel TEXT,
    requires_transport BOOLEAN NOT NULL DEFAULT TRUE,
    requires_setup BOOLEAN NOT NULL DEFAULT TRUE,
    requires_teardown BOOLEAN NOT NULL DEFAULT TRUE,
    notes TEXT,
    created_by TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (planned_end > planned_start)
);

-- ---------------------------------------------------------
-- Skills
-- ---------------------------------------------------------
CREATE TABLE core.skills (
    skill_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    skill_name TEXT NOT NULL UNIQUE,
    skill_category TEXT,
    description TEXT
);

-- ---------------------------------------------------------
-- People
-- ---------------------------------------------------------
CREATE TABLE core.resources_people (
    person_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    full_name TEXT NOT NULL,
    role core.person_role NOT NULL,
    employment_type core.employment_type NOT NULL DEFAULT 'employee',
    home_base_location_id UUID REFERENCES core.locations(location_id) ON DELETE SET NULL,
    availability_status core.resource_status NOT NULL DEFAULT 'available',
    max_daily_hours NUMERIC(4,2) NOT NULL DEFAULT 8.0 CHECK (max_daily_hours > 0),
    max_weekly_hours NUMERIC(5,2) NOT NULL DEFAULT 40.0 CHECK (max_weekly_hours > 0),
    cost_per_hour NUMERIC(10,2),
    reliability_notes TEXT,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ---------------------------------------------------------
-- People skills
-- ---------------------------------------------------------
CREATE TABLE core.people_skills (
    person_id UUID NOT NULL REFERENCES core.resources_people(person_id) ON DELETE CASCADE,
    skill_id UUID NOT NULL REFERENCES core.skills(skill_id) ON DELETE CASCADE,
    skill_level SMALLINT NOT NULL CHECK (skill_level BETWEEN 1 AND 5),
    certified BOOLEAN NOT NULL DEFAULT FALSE,
    last_verified_at TIMESTAMPTZ,
    notes TEXT,
    PRIMARY KEY (person_id, skill_id)
);

-- ---------------------------------------------------------
-- Equipment types
-- ---------------------------------------------------------
CREATE TABLE core.equipment_types (
    equipment_type_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    type_name TEXT NOT NULL UNIQUE,
    category TEXT,
    description TEXT,
    default_setup_minutes INTEGER CHECK (default_setup_minutes >= 0),
    default_teardown_minutes INTEGER CHECK (default_teardown_minutes >= 0)
);

-- ---------------------------------------------------------
-- Equipment
-- ---------------------------------------------------------
CREATE TABLE core.equipment (
    equipment_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    equipment_type_id UUID NOT NULL REFERENCES core.equipment_types(equipment_type_id) ON DELETE RESTRICT,
    asset_tag TEXT UNIQUE,
    serial_number TEXT,
    status core.resource_status NOT NULL DEFAULT 'available',
    warehouse_location_id UUID REFERENCES core.locations(location_id) ON DELETE SET NULL,
    transport_requirements TEXT,
    replacement_available BOOLEAN NOT NULL DEFAULT FALSE,
    hourly_cost_estimate NUMERIC(10,2),
    purchase_date DATE,
    notes TEXT,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ---------------------------------------------------------
-- Vehicles
-- ---------------------------------------------------------
CREATE TABLE core.vehicles (
    vehicle_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    vehicle_name TEXT NOT NULL,
    vehicle_type core.vehicle_type NOT NULL,
    registration_number TEXT UNIQUE,
    capacity_notes TEXT,
    status core.resource_status NOT NULL DEFAULT 'available',
    home_location_id UUID REFERENCES core.locations(location_id) ON DELETE SET NULL,
    cost_per_km NUMERIC(10,2),
    cost_per_hour NUMERIC(10,2),
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ---------------------------------------------------------
-- Event requirements
-- Generic requirement store for planner input
-- ---------------------------------------------------------
CREATE TABLE core.event_requirements (
    requirement_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_id UUID NOT NULL REFERENCES core.events(event_id) ON DELETE CASCADE,
    requirement_type core.requirement_type NOT NULL,
    role_required core.person_role,
    skill_id UUID REFERENCES core.skills(skill_id) ON DELETE SET NULL,
    equipment_type_id UUID REFERENCES core.equipment_types(equipment_type_id) ON DELETE SET NULL,
    vehicle_type_required core.vehicle_type,
    quantity NUMERIC(10,2) NOT NULL DEFAULT 1 CHECK (quantity > 0),
    mandatory BOOLEAN NOT NULL DEFAULT TRUE,
    required_start TIMESTAMPTZ,
    required_end TIMESTAMPTZ,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (
        (
            requirement_type = 'person_role' AND role_required IS NOT NULL
        ) OR (
            requirement_type = 'person_skill' AND skill_id IS NOT NULL
        ) OR (
            requirement_type = 'equipment_type' AND equipment_type_id IS NOT NULL
        ) OR (
            requirement_type = 'vehicle_type' AND vehicle_type_required IS NOT NULL
        ) OR (
            requirement_type IN ('time_buffer', 'other')
        )
    )
);

-- ---------------------------------------------------------
-- Availability calendar for people
-- ---------------------------------------------------------
CREATE TABLE core.people_availability (
    availability_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    person_id UUID NOT NULL REFERENCES core.resources_people(person_id) ON DELETE CASCADE,
    available_from TIMESTAMPTZ NOT NULL,
    available_to TIMESTAMPTZ NOT NULL,
    is_available BOOLEAN NOT NULL DEFAULT TRUE,
    source TEXT DEFAULT 'manual',
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (available_to > available_from)
);

-- ---------------------------------------------------------
-- Availability calendar for equipment
-- ---------------------------------------------------------
CREATE TABLE core.equipment_availability (
    availability_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    equipment_id UUID NOT NULL REFERENCES core.equipment(equipment_id) ON DELETE CASCADE,
    available_from TIMESTAMPTZ NOT NULL,
    available_to TIMESTAMPTZ NOT NULL,
    is_available BOOLEAN NOT NULL DEFAULT TRUE,
    source TEXT DEFAULT 'system',
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (available_to > available_from)
);

-- ---------------------------------------------------------
-- Availability calendar for vehicles
-- ---------------------------------------------------------
CREATE TABLE core.vehicle_availability (
    availability_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    vehicle_id UUID NOT NULL REFERENCES core.vehicles(vehicle_id) ON DELETE CASCADE,
    available_from TIMESTAMPTZ NOT NULL,
    available_to TIMESTAMPTZ NOT NULL,
    is_available BOOLEAN NOT NULL DEFAULT TRUE,
    source TEXT DEFAULT 'system',
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (available_to > available_from)
);

-- ---------------------------------------------------------
-- Assignments
-- Main planning table
-- ---------------------------------------------------------
CREATE TABLE core.assignments (
    assignment_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_id UUID NOT NULL REFERENCES core.events(event_id) ON DELETE CASCADE,
    resource_type core.assignment_resource_type NOT NULL,
    person_id UUID REFERENCES core.resources_people(person_id) ON DELETE CASCADE,
    equipment_id UUID REFERENCES core.equipment(equipment_id) ON DELETE CASCADE,
    vehicle_id UUID REFERENCES core.vehicles(vehicle_id) ON DELETE CASCADE,
    assignment_role TEXT,
    planned_start TIMESTAMPTZ NOT NULL,
    planned_end TIMESTAMPTZ NOT NULL,
    status core.assignment_status NOT NULL DEFAULT 'proposed',
    planner_run_id UUID, -- reference added later after ai.planner_runs exists
    is_manual_override BOOLEAN NOT NULL DEFAULT FALSE,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (planned_end > planned_start),
    CHECK (
        (
            resource_type = 'person'
            AND person_id IS NOT NULL
            AND equipment_id IS NULL
            AND vehicle_id IS NULL
        ) OR (
            resource_type = 'equipment'
            AND person_id IS NULL
            AND equipment_id IS NOT NULL
            AND vehicle_id IS NULL
        ) OR (
            resource_type = 'vehicle'
            AND person_id IS NULL
            AND equipment_id IS NULL
            AND vehicle_id IS NOT NULL
        )
    )
);

-- ---------------------------------------------------------
-- Optional transport legs
-- ---------------------------------------------------------
CREATE TABLE core.transport_legs (
    transport_leg_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_id UUID NOT NULL REFERENCES core.events(event_id) ON DELETE CASCADE,
    vehicle_id UUID REFERENCES core.vehicles(vehicle_id) ON DELETE SET NULL,
    driver_person_id UUID REFERENCES core.resources_people(person_id) ON DELETE SET NULL,
    origin_location_id UUID NOT NULL REFERENCES core.locations(location_id) ON DELETE RESTRICT,
    destination_location_id UUID NOT NULL REFERENCES core.locations(location_id) ON DELETE RESTRICT,
    planned_departure TIMESTAMPTZ NOT NULL,
    planned_arrival TIMESTAMPTZ NOT NULL,
    estimated_distance_km NUMERIC(10,2),
    estimated_duration_minutes INTEGER,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (planned_arrival > planned_departure)
);

-- =========================================================
-- OPS SCHEMA
-- =========================================================

-- ---------------------------------------------------------
-- Event execution logs
-- ---------------------------------------------------------
CREATE TABLE ops.event_execution_logs (
    log_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_id UUID NOT NULL REFERENCES core.events(event_id) ON DELETE CASCADE,
    assignment_id UUID REFERENCES core.assignments(assignment_id) ON DELETE SET NULL,
    timestamp_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    log_type ops.log_type NOT NULL,
    author_type ops.author_type NOT NULL DEFAULT 'system',
    author_reference TEXT,
    message TEXT,
    meta JSONB NOT NULL DEFAULT '{}'::jsonb
);

-- ---------------------------------------------------------
-- Plan vs actual timings
-- ---------------------------------------------------------
CREATE TABLE ops.actual_timings (
    timing_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_id UUID NOT NULL REFERENCES core.events(event_id) ON DELETE CASCADE,
    assignment_id UUID REFERENCES core.assignments(assignment_id) ON DELETE SET NULL,
    phase_name ops.phase_name NOT NULL,
    planned_start TIMESTAMPTZ,
    actual_start TIMESTAMPTZ,
    planned_end TIMESTAMPTZ,
    actual_end TIMESTAMPTZ,
    delay_minutes INTEGER GENERATED ALWAYS AS (
        CASE
            WHEN planned_end IS NOT NULL AND actual_end IS NOT NULL
            THEN FLOOR(EXTRACT(EPOCH FROM (actual_end - planned_end)) / 60)
            ELSE NULL
        END
    ) STORED,
    delay_reason_code TEXT,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ---------------------------------------------------------
-- Incidents
-- ---------------------------------------------------------
CREATE TABLE ops.incidents (
    incident_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_id UUID NOT NULL REFERENCES core.events(event_id) ON DELETE CASCADE,
    assignment_id UUID REFERENCES core.assignments(assignment_id) ON DELETE SET NULL,
    incident_type ops.incident_type NOT NULL,
    severity ops.incident_severity NOT NULL DEFAULT 'medium',
    reported_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    resolved_at TIMESTAMPTZ,
    reported_by TEXT,
    root_cause TEXT,
    description TEXT NOT NULL,
    cost_impact NUMERIC(12,2),
    sla_impact BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (resolved_at IS NULL OR resolved_at >= reported_at)
);

-- ---------------------------------------------------------
-- Event outcomes / summary
-- ---------------------------------------------------------
CREATE TABLE ops.event_outcomes (
    event_id UUID PRIMARY KEY REFERENCES core.events(event_id) ON DELETE CASCADE,
    finished_on_time BOOLEAN,
    total_delay_minutes INTEGER,
    actual_cost NUMERIC(12,2),
    overtime_cost NUMERIC(12,2),
    transport_cost NUMERIC(12,2),
    sla_breached BOOLEAN NOT NULL DEFAULT FALSE,
    client_satisfaction_score NUMERIC(4,2) CHECK (client_satisfaction_score BETWEEN 0 AND 10),
    internal_quality_score NUMERIC(4,2) CHECK (internal_quality_score BETWEEN 0 AND 10),
    margin_estimate NUMERIC(12,2),
    summary_notes TEXT,
    closed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ---------------------------------------------------------
-- Resource check-ins / field confirmations
-- ---------------------------------------------------------
CREATE TABLE ops.resource_checkpoints (
    checkpoint_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_id UUID NOT NULL REFERENCES core.events(event_id) ON DELETE CASCADE,
    assignment_id UUID REFERENCES core.assignments(assignment_id) ON DELETE SET NULL,
    resource_type core.assignment_resource_type NOT NULL,
    person_id UUID REFERENCES core.resources_people(person_id) ON DELETE SET NULL,
    equipment_id UUID REFERENCES core.equipment(equipment_id) ON DELETE SET NULL,
    vehicle_id UUID REFERENCES core.vehicles(vehicle_id) ON DELETE SET NULL,
    checkpoint_type TEXT NOT NULL, -- e.g. arrived / started / completed
    checkpoint_time TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    latitude NUMERIC(9,6),
    longitude NUMERIC(9,6),
    notes TEXT,
    CHECK (
        (
            resource_type = 'person'
            AND person_id IS NOT NULL
            AND equipment_id IS NULL
            AND vehicle_id IS NULL
        ) OR (
            resource_type = 'equipment'
            AND person_id IS NULL
            AND equipment_id IS NOT NULL
            AND vehicle_id IS NULL
        ) OR (
            resource_type = 'vehicle'
            AND person_id IS NULL
            AND equipment_id IS NULL
            AND vehicle_id IS NOT NULL
        )
    )
);

-- =========================================================
-- AI SCHEMA
-- =========================================================

-- ---------------------------------------------------------
-- Models registry
-- ---------------------------------------------------------
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
    UNIQUE (model_name, model_version, prediction_type)
);

-- ---------------------------------------------------------
-- Event features
-- Flattened feature store for event-level models
-- ---------------------------------------------------------
CREATE TABLE ai.event_features (
    event_id UUID PRIMARY KEY REFERENCES core.events(event_id) ON DELETE CASCADE,
    feature_event_type TEXT,
    feature_event_subtype TEXT,
    feature_city TEXT,
    feature_location_type TEXT,
    feature_attendee_count INTEGER,
    feature_attendee_bucket TEXT,
    feature_setup_complexity_score SMALLINT,
    feature_access_difficulty SMALLINT,
    feature_parking_difficulty SMALLINT,
    feature_priority TEXT,
    feature_day_of_week SMALLINT CHECK (feature_day_of_week BETWEEN 1 AND 7),
    feature_month SMALLINT CHECK (feature_month BETWEEN 1 AND 12),
    feature_season TEXT,
    feature_requires_transport BOOLEAN,
    feature_requires_setup BOOLEAN,
    feature_requires_teardown BOOLEAN,
    feature_required_person_count INTEGER,
    feature_required_equipment_count INTEGER,
    feature_required_vehicle_count INTEGER,
    feature_estimated_distance_km NUMERIC(10,2),
    feature_client_priority TEXT,
    generated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ---------------------------------------------------------
-- Resource features
-- ---------------------------------------------------------
CREATE TABLE ai.resource_features (
    resource_feature_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    resource_type core.assignment_resource_type NOT NULL,
    person_id UUID REFERENCES core.resources_people(person_id) ON DELETE CASCADE,
    equipment_id UUID REFERENCES core.equipment(equipment_id) ON DELETE CASCADE,
    vehicle_id UUID REFERENCES core.vehicles(vehicle_id) ON DELETE CASCADE,
    avg_delay_last_10 NUMERIC(8,2),
    avg_job_duration_variance NUMERIC(8,2),
    incident_rate_last_30d NUMERIC(8,4),
    utilization_rate_last_30d NUMERIC(8,4),
    fatigue_score NUMERIC(8,4),
    reliability_score NUMERIC(8,4),
    generated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (
        (
            resource_type = 'person'
            AND person_id IS NOT NULL
            AND equipment_id IS NULL
            AND vehicle_id IS NULL
        ) OR (
            resource_type = 'equipment'
            AND person_id IS NULL
            AND equipment_id IS NOT NULL
            AND vehicle_id IS NULL
        ) OR (
            resource_type = 'vehicle'
            AND person_id IS NULL
            AND equipment_id IS NULL
            AND vehicle_id IS NOT NULL
        )
    )
);

-- ---------------------------------------------------------
-- Predictions
-- ---------------------------------------------------------
CREATE TABLE ai.predictions (
    prediction_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_id UUID REFERENCES core.events(event_id) ON DELETE CASCADE,
    assignment_id UUID REFERENCES core.assignments(assignment_id) ON DELETE SET NULL,
    model_id UUID REFERENCES ai.models(model_id) ON DELETE SET NULL,
    prediction_type ai.prediction_type NOT NULL,
    predicted_value NUMERIC(14,4),
    predicted_label TEXT,
    confidence_score NUMERIC(6,4) CHECK (confidence_score IS NULL OR (confidence_score >= 0 AND confidence_score <= 1)),
    explanation TEXT,
    feature_snapshot JSONB NOT NULL DEFAULT '{}'::jsonb,
    generated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ---------------------------------------------------------
-- Planner runs
-- ---------------------------------------------------------
CREATE TABLE ai.planner_runs (
    planner_run_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at TIMESTAMPTZ,
    run_status ai.planner_run_status NOT NULL DEFAULT 'started',
    objective_version TEXT,
    initiated_by TEXT,
    trigger_reason TEXT, -- manual / event_change / incident / replan
    input_snapshot JSONB NOT NULL DEFAULT '{}'::jsonb,
    total_cost NUMERIC(12,2),
    total_risk_score NUMERIC(12,4),
    sla_risk_count INTEGER,
    notes TEXT,
    CHECK (finished_at IS NULL OR finished_at >= started_at)
);

-- ---------------------------------------------------------
-- Planner recommendations summary
-- ---------------------------------------------------------
CREATE TABLE ai.planner_recommendations (
    recommendation_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    planner_run_id UUID NOT NULL REFERENCES ai.planner_runs(planner_run_id) ON DELETE CASCADE,
    event_id UUID NOT NULL REFERENCES core.events(event_id) ON DELETE CASCADE,
    expected_cost NUMERIC(12,2),
    expected_duration_minutes INTEGER,
    expected_risk NUMERIC(12,4),
    selected_for_execution BOOLEAN NOT NULL DEFAULT FALSE,
    rationale TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ---------------------------------------------------------
-- Optional planner recommendation assignments
-- Keeps per-resource recommendation details
-- ---------------------------------------------------------
CREATE TABLE ai.planner_recommendation_assignments (
    recommendation_assignment_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    recommendation_id UUID NOT NULL REFERENCES ai.planner_recommendations(recommendation_id) ON DELETE CASCADE,
    resource_type core.assignment_resource_type NOT NULL,
    person_id UUID REFERENCES core.resources_people(person_id) ON DELETE SET NULL,
    equipment_id UUID REFERENCES core.equipment(equipment_id) ON DELETE SET NULL,
    vehicle_id UUID REFERENCES core.vehicles(vehicle_id) ON DELETE SET NULL,
    assignment_role TEXT,
    planned_start TIMESTAMPTZ NOT NULL,
    planned_end TIMESTAMPTZ NOT NULL,
    risk_score NUMERIC(12,4),
    cost_estimate NUMERIC(12,2),
    CHECK (planned_end > planned_start),
    CHECK (
        (
            resource_type = 'person'
            AND person_id IS NOT NULL
            AND equipment_id IS NULL
            AND vehicle_id IS NULL
        ) OR (
            resource_type = 'equipment'
            AND person_id IS NULL
            AND equipment_id IS NOT NULL
            AND vehicle_id IS NULL
        ) OR (
            resource_type = 'vehicle'
            AND person_id IS NULL
            AND equipment_id IS NULL
            AND vehicle_id IS NOT NULL
        )
    )
);

-- ---------------------------------------------------------
-- Feedback loop for model evaluation
-- ---------------------------------------------------------
CREATE TABLE ai.prediction_outcomes (
    prediction_outcome_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    prediction_id UUID NOT NULL REFERENCES ai.predictions(prediction_id) ON DELETE CASCADE,
    actual_numeric_value NUMERIC(14,4),
    actual_label TEXT,
    evaluated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    error_value NUMERIC(14,4),
    notes TEXT
);

-- =========================================================
-- Cross-schema FK added after ai.planner_runs exists
-- =========================================================
ALTER TABLE core.assignments
ADD CONSTRAINT fk_assignments_planner_run
FOREIGN KEY (planner_run_id)
REFERENCES ai.planner_runs(planner_run_id)
ON DELETE SET NULL;

-- =========================================================
-- INDEXES
-- =========================================================

-- core
CREATE INDEX idx_events_client_id ON core.events(client_id);
CREATE INDEX idx_events_location_id ON core.events(location_id);
CREATE INDEX idx_events_status ON core.events(status);
CREATE INDEX idx_events_planned_start ON core.events(planned_start);
CREATE INDEX idx_events_planned_end ON core.events(planned_end);
CREATE INDEX idx_events_type_dates ON core.events(event_type, planned_start, planned_end);

CREATE INDEX idx_people_role_status ON core.resources_people(role, availability_status);
CREATE INDEX idx_people_home_base ON core.resources_people(home_base_location_id);

CREATE INDEX idx_equipment_type_status ON core.equipment(equipment_type_id, status);
CREATE INDEX idx_vehicle_status_type ON core.vehicles(status, vehicle_type);

CREATE INDEX idx_event_requirements_event_id ON core.event_requirements(event_id);
CREATE INDEX idx_event_requirements_skill_id ON core.event_requirements(skill_id);
CREATE INDEX idx_event_requirements_equipment_type_id ON core.event_requirements(equipment_type_id);

CREATE INDEX idx_people_availability_person_time
    ON core.people_availability(person_id, available_from, available_to);

CREATE INDEX idx_equipment_availability_equipment_time
    ON core.equipment_availability(equipment_id, available_from, available_to);

CREATE INDEX idx_vehicle_availability_vehicle_time
    ON core.vehicle_availability(vehicle_id, available_from, available_to);

CREATE INDEX idx_assignments_event_id ON core.assignments(event_id);
CREATE INDEX idx_assignments_status ON core.assignments(status);
CREATE INDEX idx_assignments_planner_run_id ON core.assignments(planner_run_id);
CREATE INDEX idx_assignments_person_time ON core.assignments(person_id, planned_start, planned_end);
CREATE INDEX idx_assignments_equipment_time ON core.assignments(equipment_id, planned_start, planned_end);
CREATE INDEX idx_assignments_vehicle_time ON core.assignments(vehicle_id, planned_start, planned_end);

CREATE INDEX idx_transport_legs_event_id ON core.transport_legs(event_id);
CREATE INDEX idx_transport_legs_vehicle_id ON core.transport_legs(vehicle_id);

-- ops
CREATE INDEX idx_execution_logs_event_id ON ops.event_execution_logs(event_id);
CREATE INDEX idx_execution_logs_assignment_id ON ops.event_execution_logs(assignment_id);
CREATE INDEX idx_execution_logs_timestamp ON ops.event_execution_logs(timestamp_at);

CREATE INDEX idx_actual_timings_event_id ON ops.actual_timings(event_id);
CREATE INDEX idx_actual_timings_assignment_id ON ops.actual_timings(assignment_id);
CREATE INDEX idx_actual_timings_phase_name ON ops.actual_timings(phase_name);

CREATE INDEX idx_incidents_event_id ON ops.incidents(event_id);
CREATE INDEX idx_incidents_assignment_id ON ops.incidents(assignment_id);
CREATE INDEX idx_incidents_type_severity ON ops.incidents(incident_type, severity);

CREATE INDEX idx_resource_checkpoints_event_id ON ops.resource_checkpoints(event_id);
CREATE INDEX idx_resource_checkpoints_assignment_id ON ops.resource_checkpoints(assignment_id);
CREATE INDEX idx_resource_checkpoints_time ON ops.resource_checkpoints(checkpoint_time);

-- ai
CREATE INDEX idx_models_prediction_type_status ON ai.models(prediction_type, status);

CREATE INDEX idx_predictions_event_id ON ai.predictions(event_id);
CREATE INDEX idx_predictions_assignment_id ON ai.predictions(assignment_id);
CREATE INDEX idx_predictions_model_id ON ai.predictions(model_id);
CREATE INDEX idx_predictions_type_generated_at ON ai.predictions(prediction_type, generated_at);

CREATE INDEX idx_planner_runs_status_started_at ON ai.planner_runs(run_status, started_at);
CREATE INDEX idx_planner_recommendations_run_id ON ai.planner_recommendations(planner_run_id);
CREATE INDEX idx_planner_recommendations_event_id ON ai.planner_recommendations(event_id);

CREATE INDEX idx_resource_features_person_id ON ai.resource_features(person_id);
CREATE INDEX idx_resource_features_equipment_id ON ai.resource_features(equipment_id);
CREATE INDEX idx_resource_features_vehicle_id ON ai.resource_features(vehicle_id);

-- JSONB GIN where useful
CREATE INDEX idx_execution_logs_meta_gin ON ops.event_execution_logs USING GIN (meta);
CREATE INDEX idx_models_metrics_gin ON ai.models USING GIN (metrics);
CREATE INDEX idx_predictions_feature_snapshot_gin ON ai.predictions USING GIN (feature_snapshot);
CREATE INDEX idx_planner_runs_input_snapshot_gin ON ai.planner_runs USING GIN (input_snapshot);

-- =========================================================
-- Updated_at triggers
-- =========================================================

CREATE OR REPLACE FUNCTION core.set_updated_at()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_clients_updated_at
BEFORE UPDATE ON core.clients
FOR EACH ROW
EXECUTE FUNCTION core.set_updated_at();

CREATE TRIGGER trg_events_updated_at
BEFORE UPDATE ON core.events
FOR EACH ROW
EXECUTE FUNCTION core.set_updated_at();

CREATE TRIGGER trg_resources_people_updated_at
BEFORE UPDATE ON core.resources_people
FOR EACH ROW
EXECUTE FUNCTION core.set_updated_at();

CREATE TRIGGER trg_equipment_updated_at
BEFORE UPDATE ON core.equipment
FOR EACH ROW
EXECUTE FUNCTION core.set_updated_at();

CREATE TRIGGER trg_vehicles_updated_at
BEFORE UPDATE ON core.vehicles
FOR EACH ROW
EXECUTE FUNCTION core.set_updated_at();

CREATE TRIGGER trg_assignments_updated_at
BEFORE UPDATE ON core.assignments
FOR EACH ROW
EXECUTE FUNCTION core.set_updated_at();

COMMIT;
