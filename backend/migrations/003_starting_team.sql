CREATE TABLE card_templates (
    code TEXT PRIMARY KEY,
    slot SMALLINT NOT NULL UNIQUE CHECK (slot BETWEEN 1 AND 5),
    role TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    description TEXT NOT NULL,
    power INTEGER NOT NULL CHECK (power >= 0)
);

INSERT INTO card_templates (code, slot, role, name, description, power) VALUES
    ('captain', 1, 'IGL', 'Капитан', 'Руководит командой', 50),
    ('sniper', 2, 'AWP', 'Снайпер', 'Контролирует дальние позиции', 50),
    ('entry', 3, 'Entry', 'Первый номер', 'Первым выходит на позицию', 50),
    ('support', 4, 'Support', 'Поддержка', 'Помогает команде занять позицию', 50),
    ('lurker', 5, 'Lurker', 'Луркер', 'Контролирует фланги', 50);

CREATE TABLE team_players (
    telegram_id BIGINT NOT NULL REFERENCES accounts(telegram_id),
    slot SMALLINT NOT NULL CHECK (slot BETWEEN 1 AND 5),
    template_code TEXT NOT NULL REFERENCES card_templates(code),
    power INTEGER NOT NULL CHECK (power >= 0),
    PRIMARY KEY (telegram_id, slot),
    UNIQUE (telegram_id, template_code)
);

INSERT INTO team_players (telegram_id, slot, template_code, power)
SELECT a.telegram_id, c.slot, c.code, c.power
FROM accounts a CROSS JOIN card_templates c;
