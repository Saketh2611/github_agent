CREATE TABLE IF NOT EXISTS execution_logs (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    instruction TEXT NOT NULL,
    decomposed_steps JSONB NOT NULL DEFAULT '[]',
    tools_used JSONB NOT NULL DEFAULT '[]',
    execution_time_ms INTEGER NOT NULL DEFAULT 0,
    api_calls INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL CHECK (status IN ('success', 'partial_success', 'failed')),
    error_context TEXT,
    result_summary TEXT,
    executed_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_execution_logs_instruction ON execution_logs USING gin (to_tsvector('english', instruction));
CREATE INDEX idx_execution_logs_status ON execution_logs (status);
CREATE INDEX idx_execution_logs_executed_at ON execution_logs (executed_at DESC);
