# Missis S'Uzi Telegram Bot — Railway (Webhook)

Версия: v7.3-fixed

## Что внутри
- aiogram 3.x + webhook через AIOHTTP
- Авторизация по bot_code **или** телефону (с выбором **только** заказа с `customFields.bot_code`)
- Кнопки: статус, трек, заказы, оценка, поддержка
- Отзывы пишутся в `customFields.comments`, рейтинг — `customFields.rating`
- Трек-номер берём из `delivery.number`, при отсутствии — тёплое сообщение
- Поддержка: пересылка запроса админу по `ADMIN_TELEGRAM_ID` (без упоминаний имён менеджеров)
- Redis для хранения авторизации (hash `user:{id}`)

## Переменные окружения
См. `.env.example`:
- `TELEGRAM_TOKEN`
- `CRM_API_KEY`, `CRM_URL`
- `ADMIN_TELEGRAM_ID`
- `WEBHOOK_URL`
- `REDIS_HOST`, `REDIS_PORT`, `REDIS_DB`, `REDIS_PASSWORD` (при необходимости)
- `PORT` — автоматически задаётся Railway, по умолчанию 8080

## Запуск локально
```bash
pip install -r requirements.txt
export TELEGRAM_TOKEN=xxx
export CRM_API_KEY=xxx
export CRM_URL=https://valentinkalinovski.retailcrm.ru
export WEBHOOK_URL=https://your-railway-app-url
python bot.py
```

## Маршруты
- `/webhook` — вход для Telegram
- `/ping` — health-check (200 OK)

## Заметки
- В CRM сериализуем только в поля `customFields.rating` и `customFields.comments`.
- При авторизации по телефону учитываются только заказы, где заполнен `customFields.bot_code`.
