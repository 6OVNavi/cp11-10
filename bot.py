from aiogram import Bot, Dispatcher, html

from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

import os
import asyncio
import logging
import sqlite3
from textwrap import dedent
import sqlite_vec
from sqlite_vec import serialize_float32
from sentence_transformers import SentenceTransformer
from openai import OpenAI
import json
import time
from datetime import datetime

from handlers import common

from RAG_VALERA_CODE.rag.rag_inference import prompt_lia, client, \
    setup_database, setup_log_database, retrieve_context, call_model, ask_question


DATA_DB_NAME = "rzd.sqlite3"
LOG_DB_NAME = "log.sqlite3"
EMBEDDING_MODEL = 'deepvk/USER-bge-m3'
LLM_MODEL = 'vikhr'

db = setup_database()
log_db = setup_log_database()
embedding_model = SentenceTransformer(EMBEDDING_MODEL)
conversation_history = [{"role": "system", "content": prompt_lia}]
chat_id = datetime.now().strftime("%Y%m%d%H%M%S")

bot_token = os.getenv('BOT_TOKEN')

bot = Bot(token=bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

async def main():

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    )

    # bot = Bot(token=bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    # dp = Dispatcher()

    #include routers
    dp.include_routers(common.router)

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == '__main__':
    asyncio.run(main())