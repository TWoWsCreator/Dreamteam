ALTER TABLE lobbies DROP CONSTRAINT lobbies_status_check;
ALTER TABLE lobbies ADD CONSTRAINT lobbies_status_check
    CHECK (status IN ('waiting', 'ready', 'started', 'cancelled', 'expired', 'finished'));
ALTER TABLE lobbies ADD COLUMN guest_joined BOOLEAN NOT NULL DEFAULT FALSE;

UPDATE lobbies l SET guest_joined = TRUE
WHERE EXISTS (
    SELECT 1 FROM lobby_members m
    WHERE m.lobby_id = l.id AND m.telegram_id <> l.host_id
);

ALTER TABLE series DROP CONSTRAINT series_phase_check;
ALTER TABLE series ADD CONSTRAINT series_phase_check
    CHECK (phase IN ('awaiting_veto', 'cancelled', 'finished'));
ALTER TABLE series ADD COLUMN result JSONB;
ALTER TABLE series ADD COLUMN finished_at TIMESTAMPTZ;
ALTER TABLE series ADD CONSTRAINT series_finished_result_check
    CHECK (
        (phase = 'finished' AND result IS NOT NULL AND finished_at IS NOT NULL)
        OR (phase <> 'finished' AND result IS NULL AND finished_at IS NULL)
    );
