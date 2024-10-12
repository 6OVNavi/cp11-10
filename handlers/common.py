from aiogram import F, Router
from aiogram import Bot, Dispatcher, html
from aiogram.filters import Command
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import default_state
from aiogram.types import Message, ReplyKeyboardRemove
from aiogram.fsm.state import StatesGroup, State
from aiogram import types
from aiogram.types import FSInputFile

from keyboards.kb import auth_kb, askq_kb

from RAG_VALERA_CODE.rag.rag_inference import EMBEDDING_MODEL, LOG_DB_NAME, EMBEDDING_MODEL, LLM_MODEL
from RAG_VALERA_CODE.rag.rag_inference import prompt_lia, client, \
    setup_database, setup_log_database, retrieve_context, call_model, ask_question

from bot import db, embedding_model, conversation_history, log_db, chat_id


router = Router()

class StateMachine(StatesGroup):
    something_like_login = State() #test
    settings = State() #think about it
    waiting_for_question = State()

@router.message(Command(commands=["start"]))
async def command_start_handler(message: Message) -> None:
    """
    Sends Hello message to User
    """
    await message.answer(f"Hello, {html.bold(message.from_user.full_name)}!", reply_markup=auth_kb())

@router.message(F.text == '🔐 Авторизация')
async def auth_user(message: Message):
    ... #logic for auth.
    await message.reply('Вы успешно авторизовались!', reply_markup=askq_kb())


@router.message(F.text == '⚙️ Настройки')
async def settings(message: Message):
    ... #logic for settings.
    await message.reply('Скоро тут будут настройки!')


@router.message(F.text == '📄 Задать вопрос')
async def get_file(message: Message, state: FSMContext):
    await message.reply('Введите ваш вопрос:', reply_markup=askq_kb())

    await state.set_state(StateMachine.waiting_for_question)


@router.message(StateMachine.waiting_for_question)
async def answer(message: Message):
    await message.reply(f'Ваш вопрос: {message.text}', reply_markup=askq_kb())
    response, context, meta_datas, sources = ask_question(message.text, db, embedding_model, conversation_history, log_db, chat_id)
    fw = ', '.join(set(meta_datas))
    ss = ', '.join(set(sources))
    ans = f"""
    \nОтвет:
    {response}
    \nОткуда взята информация:
    {fw}
    \nИсточники:
    {ss}
    """
    await message.annswer(ans, reply_markup=askq_kb())

    