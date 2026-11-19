CREATE TABLE IF NOT EXISTS accounts (
    telegram_id BIGINT PRIMARY KEY CHECK (telegram_id > 0),
    display_name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS tactics (
    telegram_id BIGINT NOT NULL REFERENCES accounts(telegram_id),
    map TEXT NOT NULL,
    side TEXT NOT NULL CHECK (side IN ('T', 'CT')),
    preset TEXT NOT NULL,
    PRIMARY KEY (telegram_id, map, side)
);

CREATE TABLE IF NOT EXISTS lobbies (
    id UUID PRIMARY KEY,
    host_id BIGINT NOT NULL REFERENCES accounts(telegram_id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    expires_at TIMESTAMPTZ NOT NULL,
    status TEXT NOT NULL DEFAULT 'waiting' CHECK (status IN ('waiting', 'ready', 'cancelled', 'expired'))
);

CREATE TABLE IF NOT EXISTS lobby_members (
    lobby_id UUID NOT NULL REFERENCES lobbies(id),
    telegram_id BIGINT NOT NULL REFERENCES accounts(telegram_id),
    ready BOOLEAN NOT NULL DEFAULT FALSE,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    PRIMARY KEY (lobby_id, telegram_id)
);

CREATE UNIQUE INDEX IF NOT EXISTS one_active_lobby_per_player
    ON lobby_members(telegram_id) WHERE active;
