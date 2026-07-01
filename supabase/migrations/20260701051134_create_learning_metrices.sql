-- View for quick learning metrics per instruction pattern
CREATE OR REPLACE VIEW learning_metrics AS
SELECT
    substring(instruction from 1 for 80) AS instruction_prefix,
    COUNT(*) AS total_runs,
    ROUND(AVG(execution_time_ms)::numeric, 0) AS avg_time_ms,
    ROUND(AVG(api_calls)::numeric, 1) AS avg_api_calls,
    ROUND(
        COUNT(*) FILTER (WHERE status = 'success')::numeric / NULLIF(COUNT(*), 0),
        2
    ) AS success_rate,
    MIN(execution_time_ms) AS best_time_ms,
    MAX(execution_time_ms) AS worst_time_ms,
    MIN(api_calls) AS min_api_calls,
    MAX(api_calls) AS max_api_calls,
    MIN(executed_at) AS first_run,
    MAX(executed_at) AS last_run
FROM execution_logs
GROUP BY instruction_prefix
ORDER BY total_runs DESC;

-- View for capability health
CREATE OR REPLACE VIEW capability_health AS
SELECT
    name,
    description,
    http_method,
    endpoint_template,
    success_count,
    failure_count,
    success_rate,
    synthesized,
    discovered_constraints,
    last_used_at
FROM capabilities
ORDER BY success_rate DESC, last_used_at DESC;
