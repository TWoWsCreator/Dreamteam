# Dreamteam

Telegram Mini App для игры с другом по приглашению. Новый аккаунт получает сохранённую пятёрку. В лобби два игрока видят сторону и свою тактику. Подтверждение обоих запускает расчёт одной карты Mirage. Сервер сохраняет один итог и журнал раундов. Вето, BO3 и экономика карт относятся к дальнейшим приращениям.

## Структура проекта

| Каталог | Ответственность |
|---|---|
| [backend/dreamteam/http](backend/dreamteam/http) | Маршруты FastAPI, проверка запроса и внедрение зависимостей |
| [backend/dreamteam/services](backend/dreamteam/services) | Сценарии входа, лобби и завершения карты |
| [backend/dreamteam/domain](backend/dreamteam/domain) | Пресеты и расчёт раундов |
| [backend/dreamteam/repositories](backend/dreamteam/repositories) | SQL и границы транзакций |
| [backend/migrations](backend/migrations) | Схема и обновление PostgreSQL |
| [frontend/src/features](frontend/src/features) | Команда, тактики, лобби и результат |
| [docs/diaries](docs/diaries) | Связь изученных материалов с кодом и тестами |

Дневники [Таисии](docs/diaries/taisiia.md), [Семёна](docs/diaries/semen.md) и [Никиты](docs/diaries/nikita.md) хранятся в документации проекта.

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

Ссылки-приглашения действуют 30 минут. В заполненном лобби игроки подтверждают готовность без тайм-аута. До старта любой участник может закрыть лобби. После старта сервер считает карту целиком и сохраняет результат одной транзакцией. Параметр силы отображается на карточках и в расчёте не участвует.

## Проверки backend

```sh
DREAMTEAM_TEST_DATABASE_URL="$DREAMTEAM_DATABASE_URL" python -m pytest -q
```

Интеграционные сценарии создают временную схему PostgreSQL. Проверяются повторный вход, отдельные настройки T/CT, права участников, неверные и просроченные приглашения, конкурирующие команды готовности и отмена. Основание — [CSC-447](https://ru.yougile.com/team/5d37d1949ade/#CSC-447).
