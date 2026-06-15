-- Idempotency-Key support for POST /analyses (Stripe-pattern double-submit guard).
-- A partial unique index lets null keys (non-idempotent creates) coexist freely.
ALTER TABLE public.analysis_runs ADD COLUMN idempotency_key text;

CREATE UNIQUE INDEX analysis_runs_idempotency_key_key
    ON public.analysis_runs (idempotency_key)
    WHERE idempotency_key IS NOT NULL;
