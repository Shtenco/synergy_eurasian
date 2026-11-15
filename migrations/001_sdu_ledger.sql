-- SDU PostgreSQL ledger schema, migration 001.
-- Apply with a privileged migration role. Runtime role must not own these tables.

CREATE TABLE IF NOT EXISTS sdu_assets (
    symbol TEXT PRIMARY KEY CHECK (symbol <> '' AND symbol = btrim(symbol)),
    decimals SMALLINT NOT NULL CHECK (decimals BETWEEN 0 AND 18),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS sdu_accounts (
    account_id TEXT NOT NULL,
    asset_symbol TEXT NOT NULL REFERENCES sdu_assets(symbol),
    account_kind TEXT NOT NULL CHECK (account_kind <> ''),
    allow_negative BOOLEAN NOT NULL DEFAULT FALSE,
    counts_toward_supply BOOLEAN NOT NULL DEFAULT TRUE,
    burnable BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (account_id, asset_symbol),
    CHECK (NOT (allow_negative AND counts_toward_supply))
);

CREATE TABLE IF NOT EXISTS sdu_ledger_state (
    singleton BOOLEAN PRIMARY KEY DEFAULT TRUE CHECK (singleton),
    next_sequence BIGINT NOT NULL DEFAULT 1 CHECK (next_sequence > 0),
    last_event_hash CHAR(64) NOT NULL DEFAULT repeat('0', 64)
);
INSERT INTO sdu_ledger_state(singleton) VALUES (TRUE) ON CONFLICT (singleton) DO NOTHING;

CREATE TABLE IF NOT EXISTS sdu_events (
    event_id UUID PRIMARY KEY,
    sequence BIGINT NOT NULL UNIQUE CHECK (sequence > 0),
    event_type TEXT NOT NULL CHECK (event_type <> ''),
    idempotency_key TEXT NOT NULL UNIQUE CHECK (idempotency_key <> ''),
    actor_id TEXT NOT NULL CHECK (actor_id <> ''),
    event_timestamp TIMESTAMPTZ NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    previous_hash CHAR(64) NOT NULL,
    event_hash CHAR(64) NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS sdu_postings (
    posting_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    event_id UUID NOT NULL REFERENCES sdu_events(event_id),
    line_number INTEGER NOT NULL CHECK (line_number > 0),
    account_id TEXT NOT NULL,
    asset_symbol TEXT NOT NULL,
    amount NUMERIC NOT NULL CHECK (amount <> 0 AND amount = trunc(amount)),
    FOREIGN KEY (account_id, asset_symbol)
        REFERENCES sdu_accounts(account_id, asset_symbol),
    UNIQUE (event_id, line_number)
);
CREATE INDEX IF NOT EXISTS sdu_postings_account_asset_idx
    ON sdu_postings(account_id, asset_symbol, posting_id);

CREATE TABLE IF NOT EXISTS sdu_balances (
    account_id TEXT NOT NULL,
    asset_symbol TEXT NOT NULL,
    balance NUMERIC NOT NULL DEFAULT 0 CHECK (balance = trunc(balance)),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (account_id, asset_symbol),
    FOREIGN KEY (account_id, asset_symbol)
        REFERENCES sdu_accounts(account_id, asset_symbol)
);

CREATE TABLE IF NOT EXISTS sdu_idempotency (
    idempotency_key TEXT PRIMARY KEY,
    request_hash CHAR(64) NOT NULL,
    event_id UUID NOT NULL UNIQUE REFERENCES sdu_events(event_id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS sdu_epoch_issuance (
    epoch_id TEXT PRIMARY KEY CHECK (epoch_id <> ''),
    budget NUMERIC NOT NULL CHECK (budget >= 0 AND budget = trunc(budget)),
    spent NUMERIC NOT NULL DEFAULT 0 CHECK (spent >= 0 AND spent = trunc(spent) AND spent <= budget),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS sdu_issuance_claims (
    claim_id TEXT PRIMARY KEY CHECK (claim_id <> ''),
    epoch_id TEXT NOT NULL REFERENCES sdu_epoch_issuance(epoch_id),
    event_id UUID NOT NULL UNIQUE REFERENCES sdu_events(event_id),
    amount NUMERIC NOT NULL CHECK (amount > 0 AND amount = trunc(amount)),
    evidence_digest CHAR(64) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS sdu_external_deposit_claims (
    deposit_id TEXT PRIMARY KEY CHECK (deposit_id <> ''),
    event_id UUID NOT NULL UNIQUE REFERENCES sdu_events(event_id),
    chain_id TEXT NOT NULL,
    transaction_hash CHAR(64) NOT NULL,
    transfer_index INTEGER NOT NULL DEFAULT 0 CHECK (transfer_index >= 0),
    asset_symbol TEXT NOT NULL REFERENCES sdu_assets(symbol),
    asset_reference TEXT NOT NULL CHECK (asset_reference <> '' AND asset_reference = btrim(asset_reference)),
    amount NUMERIC NOT NULL CHECK (amount > 0 AND amount = trunc(amount)),
    destination_account TEXT NOT NULL,
    block_number NUMERIC NOT NULL CHECK (block_number >= 0 AND block_number = trunc(block_number)),
    confirmations INTEGER NOT NULL CHECK (confirmations >= 0),
    proof_digest CHAR(64) NOT NULL,
    claim_digest CHAR(64) NOT NULL,
    approved_verifier_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Safe re-application for databases created from an earlier research draft.
ALTER TABLE sdu_external_deposit_claims
    ADD COLUMN IF NOT EXISTS transfer_index INTEGER NOT NULL DEFAULT 0;
ALTER TABLE sdu_external_deposit_claims
    ADD COLUMN IF NOT EXISTS asset_reference TEXT NOT NULL DEFAULT 'legacy-unverified';
ALTER TABLE sdu_external_deposit_claims
    DROP CONSTRAINT IF EXISTS sdu_external_deposit_claims_chain_id_transaction_hash_asset_symbol_key;
CREATE UNIQUE INDEX IF NOT EXISTS sdu_external_deposit_transfer_identity
    ON sdu_external_deposit_claims(chain_id, transaction_hash, asset_symbol, transfer_index);

CREATE TABLE IF NOT EXISTS sdu_burn_claims (
    burn_id TEXT PRIMARY KEY CHECK (burn_id <> ''),
    event_id UUID NOT NULL UNIQUE REFERENCES sdu_events(event_id),
    source_account TEXT NOT NULL,
    amount NUMERIC NOT NULL CHECK (amount > 0 AND amount = trunc(amount)),
    burn_scope TEXT NOT NULL CHECK (burn_scope IN ('holder','protocol_reserve')),
    claim_digest CHAR(64) NOT NULL,
    approved_validator_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS sdu_checkpoints (
    sequence BIGINT PRIMARY KEY CHECK (sequence >= 0),
    event_hash CHAR(64) NOT NULL,
    checkpoint_digest CHAR(64) NOT NULL UNIQUE,
    signature TEXT NOT NULL,
    signature_algorithm TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- The deferred trigger checks each event's postings after all lines are inserted.
CREATE OR REPLACE FUNCTION sdu_assert_event_balanced()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
DECLARE
    bad_asset TEXT;
BEGIN
    SELECT asset_symbol INTO bad_asset
    FROM sdu_postings
    WHERE event_id = COALESCE(NEW.event_id, OLD.event_id)
    GROUP BY asset_symbol
    HAVING SUM(amount) <> 0
    LIMIT 1;
    IF bad_asset IS NOT NULL THEN
        RAISE EXCEPTION 'unbalanced SDU event % for asset %',
            COALESCE(NEW.event_id, OLD.event_id), bad_asset;
    END IF;
    RETURN NULL;
END;
$$;

DROP TRIGGER IF EXISTS sdu_event_balance_deferred ON sdu_postings;
CREATE CONSTRAINT TRIGGER sdu_event_balance_deferred
AFTER INSERT ON sdu_postings
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW EXECUTE FUNCTION sdu_assert_event_balanced();

-- No runtime UPDATE/DELETE of the immutable event journal or its postings.
CREATE OR REPLACE FUNCTION sdu_reject_ledger_mutation()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'SDU ledger journal is append-only';
END;
$$;

DROP TRIGGER IF EXISTS sdu_events_immutable ON sdu_events;
CREATE TRIGGER sdu_events_immutable
BEFORE UPDATE OR DELETE ON sdu_events
FOR EACH ROW EXECUTE FUNCTION sdu_reject_ledger_mutation();

DROP TRIGGER IF EXISTS sdu_postings_immutable ON sdu_postings;
CREATE TRIGGER sdu_postings_immutable
BEFORE UPDATE OR DELETE ON sdu_postings
FOR EACH ROW EXECUTE FUNCTION sdu_reject_ledger_mutation();

-- Runtime database role must not own tables, alter schema, disable triggers,
-- or write directly to balances / ledger_state / epoch counters.
-- Grant only required SELECT/INSERT/UPDATE privileges through deployment config.


-- Defense in depth: even a direct balance update cannot make a spendable
-- account negative. Runtime role must still be denied direct table writes.
CREATE OR REPLACE FUNCTION sdu_guard_negative_balance()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
DECLARE
    negative_allowed BOOLEAN;
    journal_balance NUMERIC;
BEGIN
    SELECT allow_negative INTO negative_allowed
    FROM sdu_accounts
    WHERE account_id=NEW.account_id AND asset_symbol=NEW.asset_symbol;
    IF negative_allowed IS NULL THEN
        RAISE EXCEPTION 'unknown SDU account balance target';
    END IF;
    IF NEW.balance < 0 AND NOT negative_allowed THEN
        RAISE EXCEPTION 'negative balance forbidden for account %', NEW.account_id;
    END IF;
    SELECT COALESCE(SUM(amount),0) INTO journal_balance
    FROM sdu_postings
    WHERE account_id=NEW.account_id AND asset_symbol=NEW.asset_symbol;
    IF NEW.balance <> journal_balance THEN
        RAISE EXCEPTION 'balance projection differs from journal for account %', NEW.account_id;
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS sdu_balance_nonnegative ON sdu_balances;
CREATE TRIGGER sdu_balance_nonnegative
BEFORE INSERT OR UPDATE OF balance ON sdu_balances
FOR EACH ROW EXECUTE FUNCTION sdu_guard_negative_balance();

-- Validate that every committed event has at least two postings and balances
-- each asset. The deferred trigger runs at transaction commit.
CREATE OR REPLACE FUNCTION sdu_assert_event_complete()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
DECLARE
    posting_count BIGINT;
    bad_asset TEXT;
BEGIN
    SELECT COUNT(*) INTO posting_count
    FROM sdu_postings WHERE event_id=NEW.event_id;
    IF posting_count < 2 THEN
        RAISE EXCEPTION 'SDU event % must contain at least two postings', NEW.event_id;
    END IF;
    SELECT asset_symbol INTO bad_asset
    FROM sdu_postings
    WHERE event_id=NEW.event_id
    GROUP BY asset_symbol
    HAVING SUM(amount) <> 0
    LIMIT 1;
    IF bad_asset IS NOT NULL THEN
        RAISE EXCEPTION 'unbalanced SDU event % for asset %', NEW.event_id, bad_asset;
    END IF;
    RETURN NULL;
END;
$$;

DROP TRIGGER IF EXISTS sdu_event_complete_deferred ON sdu_events;
CREATE CONSTRAINT TRIGGER sdu_event_complete_deferred
AFTER INSERT ON sdu_events
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW EXECUTE FUNCTION sdu_assert_event_complete();

CREATE OR REPLACE FUNCTION sdu_reject_protected_mutation()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'SDU audit records are append-only';
END;
$$;

DROP TRIGGER IF EXISTS sdu_idempotency_immutable ON sdu_idempotency;
CREATE TRIGGER sdu_idempotency_immutable
BEFORE UPDATE OR DELETE ON sdu_idempotency
FOR EACH ROW EXECUTE FUNCTION sdu_reject_protected_mutation();

DROP TRIGGER IF EXISTS sdu_issuance_claims_immutable ON sdu_issuance_claims;
CREATE TRIGGER sdu_issuance_claims_immutable
BEFORE UPDATE OR DELETE ON sdu_issuance_claims
FOR EACH ROW EXECUTE FUNCTION sdu_reject_protected_mutation();

DROP TRIGGER IF EXISTS sdu_checkpoints_immutable ON sdu_checkpoints;
CREATE TRIGGER sdu_checkpoints_immutable
BEFORE UPDATE OR DELETE ON sdu_checkpoints
FOR EACH ROW EXECUTE FUNCTION sdu_reject_protected_mutation();


DROP TRIGGER IF EXISTS sdu_burn_claims_immutable ON sdu_burn_claims;
CREATE TRIGGER sdu_burn_claims_immutable
BEFORE UPDATE OR DELETE ON sdu_burn_claims
FOR EACH ROW EXECUTE FUNCTION sdu_reject_protected_mutation();


DROP TRIGGER IF EXISTS sdu_external_deposit_claims_immutable ON sdu_external_deposit_claims;
CREATE TRIGGER sdu_external_deposit_claims_immutable
BEFORE UPDATE OR DELETE ON sdu_external_deposit_claims
FOR EACH ROW EXECUTE FUNCTION sdu_reject_protected_mutation();
