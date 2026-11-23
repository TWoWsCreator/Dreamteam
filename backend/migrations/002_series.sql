ALTER TABLE lobbies DROP CONSTRAINT lobbies_status_check;
ALTER TABLE lobbies ADD CONSTRAINT lobbies_status_check
    CHECK (status IN ('waiting', 'ready', 'cancelled', 'expired', 'started'));

CREATE TABLE series (
    id UUID PRIMARY KEY,
    lobby_id UUID NOT NULL UNIQUE REFERENCES lobbies(id),
    phase TEXT NOT NULL CHECK (phase IN ('awaiting_veto', 'cancelled')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);

INSERT INTO series (id, lobby_id, phase)
SELECT gen_random_uuid(), l.id, 'awaiting_veto'
FROM lobbies l
JOIN lobby_members m ON m.lobby_id = l.id AND m.active
WHERE l.status = 'ready' AND l.expires_at > clock_timestamp()
GROUP BY l.id
HAVING count(*) = 2 AND bool_and(m.ready);

UPDATE lobbies l SET status = 'started'
FROM series s
WHERE l.id = s.lobby_id;
