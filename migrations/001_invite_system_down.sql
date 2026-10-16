-- Rollback de la migración 001 — módulo de invitaciones.
--
-- Elimina por completo el módulo de invitaciones de una base de datos. Es
-- destructivo (pierde historial de estancias/créditos/ajustes): úsalo solo para
-- desinstalar el módulo. Para un reinicio acotado usa /invites-admin reset.
--
--   sqlite3 data/invites.db < migrations/001_invite_system_down.sql
--
-- Tras ejecutarlo, borra la fila de versión para permitir re-migrar:
--   DELETE FROM schema_migrations WHERE version = 1;

DROP INDEX IF EXISTS ix_audit_guild;
DROP INDEX IF EXISTS ix_adj_guild_user;
DROP INDEX IF EXISTS ix_credit_stay;
DROP INDEX IF EXISTS ix_credit_guild_inviter;
DROP INDEX IF EXISTS ix_stay_guild_joined;
DROP INDEX IF EXISTS ix_stay_guild_member;
DROP INDEX IF EXISTS ux_stay_event;
DROP INDEX IF EXISTS ux_stay_active;

DROP TABLE IF EXISTS invite_reward_rules;
DROP TABLE IF EXISTS invite_audit_log;
DROP TABLE IF EXISTS invite_adjustments;
DROP TABLE IF EXISTS invite_credits;
DROP TABLE IF EXISTS membership_stays;
DROP TABLE IF EXISTS invite_observation_gaps;
DROP TABLE IF EXISTS invite_snapshots;
DROP TABLE IF EXISTS invite_settings;
