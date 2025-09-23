-- ABC test migration created by Integrator
-- Safe, idempotent object (IF NOT EXISTS)
CREATE TABLE IF NOT EXISTS integrator_probe (
    id SERIAL PRIMARY KEY,
    note TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);
