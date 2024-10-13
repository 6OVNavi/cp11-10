# RASCAR
### Разработка QnA чат-бота на основе базы знаний
##### Инструкция по запуску бота:

1. Установите зависимости: `pip install -r requirements.txt`
    - Дополнительно установите docling: `pip install -U git+https://github.com/Valle-ds/docling`
2. Запустите файл настройки базы данных: `python3 prep_users_db.py`
3. Запустите модуль мониторинга обновления файлов: `python3 update_db.py`
4. Запустите бота: `python3 bot.py`