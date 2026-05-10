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

