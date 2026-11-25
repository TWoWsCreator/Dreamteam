# Дневник Семёна

## Материалы

- [Дневник FastAPI в YouGile](https://ru.yougile.com/team/5d37d1949ade/kb-8a34db25561f) и [раздел о слоях Router, Service и Repository](https://ru.yougile.com/team/5d37d1949ade/kb-9fccfae36f46).
- [Курс FastAPI за три часа](https://www.youtube.com/watch?v=8Zrt6VOBI_Y&t=4402s) и приложенный конспект «1. Clean Architecture».
- [SQL Academy в YouGile](https://ru.yougile.com/team/5d37d1949ade/kb-8147ee9192c5), [заметка об изменениях и транзакциях](https://ru.yougile.com/team/5d37d1949ade/kb-8579d4e84e88) и приложенный архив заметок курса.

## Что применили

| Тема дневника | Изменение в Dreamteam | Как проверить |
|---|---|---|
| Маршруты, модели запросов и внедрение зависимостей в FastAPI | [HTTP-маршруты](../../backend/dreamteam/http/routes.py) описывают запросы. [Зависимости](../../backend/dreamteam/http/dependencies.py) создают подключение и определяют пользователя. [Сервис](../../backend/dreamteam/services/game.py) управляет игровыми операциями. | Запустить сервер и открыть `/api/docs`. |
| Разделение ответственности из Clean Architecture | Правила и прикладные операции отделены от HTTP, запросы PostgreSQL вынесены в [репозиторий](../../backend/dreamteam/repositories/postgres.py). [UnitOfWork](../../backend/dreamteam/repositories/unit_of_work.py) объединяет изменения одной операции в транзакцию. | Проследить в коде путь от маршрута входа через сервис до выдачи карт в PostgreSQL. |
| SQL Academy. Ограничения, JOIN, INSERT и транзакции | [Миграция стартовой пятёрки](../../backend/migrations/003_starting_team.sql) хранит шаблоны и пять слотов аккаунта. Ключ слота и уникальность шаблона защищают от дублей. JOIN возвращает имя, роль и силу из сохранённых данных. | [Тесты API и PostgreSQL](../../backend/tests/test_game.py) проверяют первый, повторный и параллельный вход. |
