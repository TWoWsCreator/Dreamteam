# Dreamteam

Telegram Mini App для игры с другом по приглашению. В первом приращении доступны вход, фиксированная пятёрка, сохранение тактик и лобби на двоих. Готовность обоих сохраняется в лобби. Вето, симуляция BO3 и экономика карт остаются за пределами этого приращения.

## Backend

Требования — Python 3.11+, PostgreSQL 16 и Telegram-бот, для которого настроена главная Mini App в BotFather. Для разработки можно запустить отдельную локальную БД.

```sh
docker compose up -d db
cd backend
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-test.txt
export DREAMTEAM_DATABASE_URL='postgresql://dreamteam:local-dreamteam@localhost:5432/dreamteam'
export DREAMTEAM_BOT_USERNAME='your_bot_username'
```

Задайте `DREAMTEAM_BOT_TOKEN` в окружении процесса. Затем выполните:

```sh
python -m dreamteam.migrate
uvicorn dreamteam.api:create_app --factory
```

API использует PostgreSQL, проверяет [данные запуска Telegram](https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app) и выдаёт сессионную cookie. В опубликованной Mini App используйте HTTPS. Для локальных проверок через HTTP можно установить `DREAMTEAM_INSECURE_LOCAL_COOKIE=1`. Клиент и API должны быть доступны с одного адреса. При наличии `frontend/dist` FastAPI раздаёт собранный клиент.

Состав и пресеты в этом приращении демонстрационные. Приглашения действуют 30 минут. Эти значения конфигурируют отслеживаемый сценарий лобби и не задают правила матча.

## Проверки backend

```sh
DREAMTEAM_TEST_DATABASE_URL="$DREAMTEAM_DATABASE_URL" python -m pytest -q
```

Интеграционные сценарии создают временную схему PostgreSQL. Проверяются повторный вход, отдельные настройки T/CT, права участников, неверные и просроченные приглашения, конкурирующие команды готовности и отмена. Основание — [CSC-447](https://ru.yougile.com/team/5d37d1949ade/#CSC-447).
