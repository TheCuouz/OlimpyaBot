-- Migración 001 — módulo de invitaciones (esquema v1)
--
-- Referencia legible del esquema que utils/invites_db.py aplica de forma
-- versionada (tabla schema_migrations). Se aplica sola al arrancar el bot; este
-- fichero sirve para revisión, copias y para el rollback de 001_invite_system_down.sql.
--
-- IDs de Discord en TEXT (sin pérdida de precisión), fechas en UTC ISO-8601.

CREATE TABLE IF NOT EXISTS invite_settings (
    guild_id         TEXT PRIMARY KEY,
    enabled          INTEGER NOT NULL DEFAULT 1,
    rules_version    INTEGER NOT NULL DEFAULT 1,
    recent_account_days INTEGER NOT NULL DEFAULT 7,
    count_bots       INTEGER NOT NULL DEFAULT 0,
    rejoin_restores  INTEGER NOT NULL DEFAULT 1,
    announce_channel_id TEXT,
    join_template    TEXT,
    leave_template   TEXT,
    leaderboard_visibility TEXT NOT NULL DEFAULT 'self',
    created_at       TEXT NOT NULL,
    updated_at       TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS invite_snapshots (
    guild_id    TEXT NOT NULL,
    code        TEXT NOT NULL,
    inviter_id  TEXT,
    uses        INTEGER NOT NULL DEFAULT 0,
    max_uses    INTEGER,
    max_age     INTEGER,
    temporary   INTEGER NOT NULL DEFAULT 0,
    is_vanity   INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT,
    observed_at TEXT NOT NULL,
    active      INTEGER NOT NULL DEFAULT 1,
    PRIMARY KEY (guild_id, code)
);

CREATE TABLE IF NOT EXISTS invite_observation_gaps (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id   TEXT NOT NULL,
    started_at TEXT NOT NULL,
    ended_at   TEXT,
    reason     TEXT
);

CREATE TABLE IF NOT EXISTS membership_stays (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id          TEXT NOT NULL,
    member_id         TEXT NOT NULL,
    joined_at         TEXT NOT NULL,
    left_at           TEXT,
    invite_code       TEXT,
    observed_inviter_id TEXT,
    source_type       TEXT NOT NULL DEFAULT 'unknown',
    attribution_status TEXT NOT NULL DEFAULT 'unresolved',
    attribution_reason TEXT,
    eligibility_status TEXT NOT NULL DEFAULT 'pending',
    exclusion_reasons TEXT,
    is_bot            INTEGER NOT NULL DEFAULT 0,
    account_created_at TEXT,
    event_id          TEXT,
    rules_version     INTEGER NOT NULL DEFAULT 1,
    created_at        TEXT NOT NULL,
    updated_at        TEXT NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_stay_active
    ON membership_stays(guild_id, member_id) WHERE left_at IS NULL;
CREATE UNIQUE INDEX IF NOT EXISTS ux_stay_event
    ON membership_stays(guild_id, event_id) WHERE event_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS ix_stay_guild_member ON membership_stays(guild_id, member_id);
CREATE INDEX IF NOT EXISTS ix_stay_guild_joined ON membership_stays(guild_id, joined_at);

CREATE TABLE IF NOT EXISTS invite_credits (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id       TEXT NOT NULL,
    stay_id        INTEGER NOT NULL,
    member_id      TEXT NOT NULL,
    inviter_id     TEXT,
    source_type    TEXT NOT NULL,
    eligible       INTEGER NOT NULL DEFAULT 0,
    exclusion_reasons TEXT,
    is_rejoin_restore INTEGER NOT NULL DEFAULT 0,
    active         INTEGER NOT NULL DEFAULT 1,
    created_at     TEXT NOT NULL,
    updated_at     TEXT NOT NULL,
    FOREIGN KEY (stay_id) REFERENCES membership_stays(id)
);

CREATE INDEX IF NOT EXISTS ix_credit_guild_inviter ON invite_credits(guild_id, inviter_id);
CREATE INDEX IF NOT EXISTS ix_credit_stay ON invite_credits(stay_id);

CREATE TABLE IF NOT EXISTS invite_adjustments (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id   TEXT NOT NULL,
    user_id    TEXT NOT NULL,
    amount     INTEGER NOT NULL,
    reason     TEXT NOT NULL,
    actor_id   TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_adj_guild_user ON invite_adjustments(guild_id, user_id);

CREATE TABLE IF NOT EXISTS invite_audit_log (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id   TEXT NOT NULL,
    actor_id   TEXT,
    action     TEXT NOT NULL,
    target     TEXT,
    details    TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_audit_guild ON invite_audit_log(guild_id, created_at);

CREATE TABLE IF NOT EXISTS invite_reward_rules (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id  TEXT NOT NULL,
    threshold INTEGER NOT NULL,
    role_id   TEXT NOT NULL,
    UNIQUE (guild_id, threshold)
);
