# Lead Intake MVP (Webhook -> SQLite -> Log/Email)

Мини-сервис для приёма заявок: `POST /lead` принимает JSON, сохраняет лид в SQLite и отправляет уведомление в `events.log` или на email (через флаг в `.env`).

## Что реализовано
- Endpoint `POST /lead`
- Валидация входных данных (FastAPI + Pydantic)
- Сохранение в SQLite (`data/leads.db`)
- Переключаемое уведомление:
  - `event_log` -> запись в `logs/events.log`
  - `email` -> письмо менеджеру через SMTP
- Обработка ошибок:
  - невалидный JSON / отсутствие обязательных полей -> `HTTP 400`
  - недоступна БД -> `HTTP 500` + запись в лог (`logs/app.log`)

## Стек
- Python 3.10+
- FastAPI
- SQLite
- python-dotenv (`load_dotenv()` используется в приложении)

## Быстрый старт (5-10 минут)
1. Установите зависимости:

```bash
pip install -r requirements.txt
```

2. Создайте реальный `.env` на основе файла `EnvExample` и заполните значения.

3. Запустите приложение:

```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

## Настройка уведомлений через `.env`

По умолчанию:

```env
NOTIFICATION_MODE=event_log
```

Для email:

```env
NOTIFICATION_MODE=email
MANAGER_EMAIL=manager@example.com
FROM_EMAIL=bot@example.com
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=bot@example.com
SMTP_PASSWORD=replace_me
SMTP_USE_TLS=true
```

## Пример запроса

```bash
curl -X POST "http://127.0.0.1:8000/lead" ^
  -H "Content-Type: application/json" ^
  -d "{\"name\":\"Ирина\",\"contact\":\"+79990000000\",\"source\":\"landing\",\"comment\":\"Хочу консультацию по тарифам\"}"
```

Ожидаемый ответ:

```json
{
  "status": "ok",
  "lead_id": 1
}
```

## Где смотреть результат
- SQLite база: `data/leads.db`
- События (режим `event_log`): `logs/events.log`
- Ошибки приложения: `logs/app.log`

## Примеры payload
Файл `test_payloads.json` содержит валидные и невалидные примеры для ручного тестирования.

## Материалы для сдачи
- Шаблон отчёта: `docs/report-template.md`
- Шаблон лога откликов: `docs/outreach-log-template.md`
