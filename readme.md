# RASCAR
### Разработка QnA чат-бота на основе базы знаний

##### Инструкция по запуску модели:
В качестве LLM используется Vikhr-Nemo-12B-Instruct

Чтобы запустить её на сервере, необходимо:
1. Установить на него `vllm` - `pip install vllm`
2. Запустить serving модели для доступа по OpenAI-like API: `/path/to/vllm serve --dtype half --max-model-len 32000 -tp 1 qilowoq/Vikhr-Nemo-12B-Instruct-R-21-09-24-4Bit-GPTQ --api-key token-abc123`

##### Инструкция по запуску бота:

1. Установите зависимости: `pip install -r requirements.txt`
    - Дополнительно установите docling: `pip install -U git+https://github.com/Valle-ds/docling`
2. Запустите файл настройки базы данных: `python3 prep_users_db.py`
3. Запустите модуль мониторинга обновления файлов: `python3 update_db.py`
4. Запустите бота: `python3 bot.py`
