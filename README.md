# Telegram Business Bot

Telegram-бот для управления бизнесом на `Python`, `aiogram`, `PostgreSQL`.

## Что уже есть
- Роли и доступы: `director`, `accountant`, `manager`, `employee`
- PIN-код для директора
- FSM-сценарии для бухгалтерии, заявок, задач, материалов, контактов и личных дел
- Хранение фото через `Telegram file_id`
- Экспорт `.xlsx`
- Базовые напоминания по расписанию
- Автоматическая инициализация схемы БД при старте

## Локальный запуск
1. Поднимите `PostgreSQL`.
2. Создайте `.env` на основе `.env.example`.
3. Укажите как минимум `BOT_TOKEN` и `DATABASE_URL`.
4. Установите зависимости:

```powershell
pip install -r requirements.txt
```

5. Запустите бота:

```powershell
python main.py
```

## Переменные окружения
- `BOT_TOKEN` - токен Telegram-бота
- `DIRECTOR_IDS` - Telegram ID директоров через запятую
- `PIN_REQUIRED_ON_START` - требовать PIN на старте
- `DATABASE_URL` - строка подключения к PostgreSQL
- `EXPORTS_DIR` - директория временных Excel-экспортов
- `DB_POOL_MIN_SIZE` - минимальный размер пула PostgreSQL
- `DB_POOL_MAX_SIZE` - максимальный размер пула PostgreSQL
- `DB_CONNECT_RETRIES` - количество попыток подключения к БД при старте

## Railway
Проект подготовлен под `Railway` как worker-сервис:
- добавлен `Dockerfile`
- добавлен `.dockerignore`
- добавлен `railway.toml`
- используется `DATABASE_URL`, который Railway подставляет из PostgreSQL-сервиса

### Деплой в Railway
1. Создайте новый проект и подключите репозиторий или загрузите код.
2. Добавьте сервис `PostgreSQL` в тот же проект.
3. В переменных приложения задайте:
   `BOT_TOKEN`, `DIRECTOR_IDS`, `PIN_REQUIRED_ON_START`
4. `DATABASE_URL` подтянется из PostgreSQL-сервиса автоматически.
5. Запустите деплой. Команда старта: `python main.py`

## Важно
- Старые данные из `SQLite` автоматически не мигрируются.
- Экспорт-файлы хранятся во временной директории контейнера и подходят для одноразовой отправки пользователю.
