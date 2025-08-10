# Missis S'Uzi Bot (clean)

Минимальная стабильная версия без Dockerfile и лишних зависимостей.
Готова к деплою на Railway/Render (Nixpacks):

## Файлы
- bot.py — основной бот (webhook/polling)
- crm.py — запросы к RetailCRM
- utils.py — нормализация телефона и др.
- config.py — переменные окружения
- requirements.txt, runtime.txt — зависят от платформы
- .env.example — пример переменных

## Переменные окружения
- TELEGRAM_BOT_TOKEN
- WEBHOOK_URL (например, https://your-app.onrender.com/telegram)
- PORT (8080)
- USE_WEBHOOK=1 (или 0 для polling)
- CRM_URL, CRM_API_KEY
- ADMIN_CHAT_ID (чат/аккаунт админа для поддержки)

## Запуск локально
pip install -r requirements.txt
python bot.py

## Деплой
Просто загрузите репозиторий с этими файлами. Платформа сама поставит зависимости из requirements.txt и версию python из runtime.txt.
