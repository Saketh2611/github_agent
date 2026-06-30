CREATE TABLE IF NOT EXISTS capabilities (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    description TEXT NOT NULL,
    http_method TEXT NOT NULL CHECK (http_method IN ('GET', 'POST', 'PATCH', 'PUT', 'DELETE')),
    endpoint_template TEXT NOT NULL,
    payload_schema JSONB DEFAULT '{}',
    query_params_schema JSONB DEFAULT '{}',
    discovered_constraints JSONB DEFAULT '[]',
    success_count INTEGER NOT NULL DEFAULT 0,
    failure_count INTEGER NOT NULL DEFAULT 0,
    success_rate REAL NOT NULL DEFAULT 0.0,
    synthesized BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_used_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_capabilities_name ON capabilities (name);
CREATE INDEX idx_capabilities_synthesized ON capabilities (synthesized);
CREATE INDEX idx_capabilities_success_rate ON capabilities (success_rate DESC);
