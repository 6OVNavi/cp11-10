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

import sqlite3
import hashlib
from functools import wraps

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

    waiting_for_email = State()
    waiting_for_password = State()

# Определяем состояния для FSM процесса регистрации пользователя
class RegisterUser(StatesGroup):
    waiting_for_email = State()
    waiting_for_password = State()
    waiting_for_access_level = State()


# Функция для получения уровня доступа по user_id
def get_user_access_level(user_id):
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()

    cursor.execute('''SELECT access_level FROM users WHERE userID = ?''', (user_id,))
    result = cursor.fetchone()

    conn.close()

    if result:
        return result[0]  # Возвращаем уровень доступа
    return None  # Если пользователь не найден или разлогинен

# Декоратор для проверки уровня доступа
def access_level_required(level):
    def decorator(func):
        @wraps(func)
        async def wrapped(message: types.Message, *args, **kwargs):
            user_id = message.from_user.id  # Получаем user_id пользователя
            
            # Проверяем уровень доступа по user_id
            access_level = get_user_access_level(user_id)
            
            if access_level is None:
                await message.answer("Вы не авторизованы. Пожалуйста, войдите в систему.")
                return

            if access_level >= level:
                return await func(message, *args, **kwargs)
            else:
                await message.answer("У вас недостаточно прав для выполнения этой команды.")
        return wrapped
    return decorator


# Функция для связывания user_id с email
def save_user_id_to_db(user_id, email):
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()

    cursor.execute('''UPDATE users SET userID = ? WHERE email = ?''', (user_id, email))
    conn.commit()
    conn.close()

# Функция для добавления пользователя в базу данных
def add_user_to_db(email, password, access_level):
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    password_hash = generate_password_hash(password)
    
    try:
        cursor.execute('''INSERT INTO users (email, password, access_level) VALUES (?, ?, ?)''',
                       (email, password_hash, access_level))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

# Хендлер команды для регистрации нового пользователя (доступна только администраторам)
@router.message(Command(commands=['register_user']))
@access_level_required(3)
async def start_register_new_user(message: types.Message, state: FSMContext):
    await message.answer("Введите email нового пользователя.")
    
    # Переводим в состояние ожидания email
    await state.set_state(RegisterUser.waiting_for_email)

# Хендлер для получения email
@router.message(RegisterUser.waiting_for_email)
async def process_email(message: types.Message, state: FSMContext):
    email = message.text
    await state.update_data(email=email)
    
    await message.answer("Теперь введите пароль нового пользователя.")
    
    # Переводим в состояние ожидания пароля
    await state.set_state(RegisterUser.waiting_for_password)

# Хендлер для получения пароля
@router.message(RegisterUser.waiting_for_password)
async def process_password(message: types.Message, state: FSMContext):
    password = message.text
    await state.update_data(password=password)
    
    await message.answer("Введите уровень доступа для нового пользователя (0 — обычный пользователь, 3 — администратор).")
    
    # Переводим в состояние ожидания уровня доступа
    await state.set_state(RegisterUser.waiting_for_access_level)

# Хендлер для получения уровня доступа
@router.message(RegisterUser.waiting_for_access_level)
async def process_access_level(message: types.Message, state: FSMContext):
    access_level = message.text

    # Проверяем, что введён корректный уровень доступа
    if not access_level.isdigit() or int(access_level) not in [0, 1, 2, 3]:
        await message.answer("Некорректный уровень доступа. Введите число от 0 до 3")
        return

    access_level = int(access_level)

    # Получаем все данные из FSM
    user_data = await state.get_data()
    email = user_data['email']
    password = user_data['password']

    # Добавляем нового пользователя в базу данных
    if add_user_to_db(email, password, access_level):
        await message.answer(f"Пользователь {email} успешно зарегистрирован с уровнем доступа {access_level}.")
    else:
        await message.answer("Ошибка: пользователь с таким email уже существует.")

    await state.clear()
    
# Функция для разлогинивания пользователя (удаление userID)
def logout_user(user_id):
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()

    # Обнуляем поле userID, разлогинивая пользователя
    cursor.execute('''UPDATE users SET userID = 0 WHERE userID = ?''', (user_id,))
    conn.commit()
    conn.close()

# Хендлер для команды logout
@router.message(Command(commands=['logout']))
async def handle_logout(message: types.Message, state: FSMContext):
    user_id = message.from_user.id

    # Вызываем функцию для разлогинивания пользователя
    logout_user(user_id)

    await state.clear()

    await message.answer("Вы успешно вышли из системы. Для использования команд авторизуйтесь снова.", reply_markup=auth_kb())


# Функция для запроса статистики (доступна только администраторам)
@router.message(Command(commands=['get_statistics']))
@access_level_required(3)
async def get_statistics(message: types.Message):
    # Логика запроса статистики (например, количество пользователей)
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()

    cursor.execute('''SELECT COUNT(*) FROM users''')
    total_users = cursor.fetchone()[0]

    cursor.execute('''SELECT COUNT(*) FROM users WHERE access_level = 3''')
    total_admins = cursor.fetchone()[0]

    conn.close()

    await message.answer(f"Всего пользователей: {total_users}\nИз них администраторов: {total_admins}")


@router.message(Command(commands=["start"]))
async def command_start_handler(message: Message) -> None:
    """
    Sends Hello message to User
    """
    await message.answer(f"Привет, {html.bold(message.from_user.full_name)}! Добро пожаловать в нашего бота. Нажмите '🔐 Авторизация', чтобы продолжить.", reply_markup=auth_kb())
    # Переход в состояние ожидания ввода почты
    # await state.set_state(StateMachine.waiting_for_email)

@router.message(F.text == '🔐 Авторизация')
async def auth_user(message: Message, state: FSMContext):
    await message.reply('Введите вашу почту:')
    # Переход в состояние ожидания ввода почты
    await state.set_state(StateMachine.waiting_for_email)



@router.message(StateMachine.waiting_for_email)
async def get_email(message: types.Message, state: FSMContext):
    email = message.text
    await state.update_data(email=email)
    
    await message.answer("Введите ваш пароль:")
    
    # Переход в состояние ожидания ввода пароля
    await state.set_state(StateMachine.waiting_for_password)

@router.message(StateMachine.waiting_for_password)
async def get_password(message: types.Message, state: FSMContext):
    password = message.text
    user_data = await state.get_data()
    email = user_data['email']
    
    # Проверяем корректность введённых данных
    if authenticate_user(email, password):
        user_id = message.from_user.id
        
        # Сохраняем связку user_id и email в базе данных
        save_user_id_to_db(user_id, email)

        await message.answer("Авторизация успешна! Добро пожаловать в главное меню.", reply_markup=askq_kb())
        await state.clear()
    else:
        await message.answer("Неверная почта или пароль. Попробуйте ещё раз.")
        await state.set_state(StateMachine.waiting_for_email)


# Функция для генерации хеша пароля
def generate_password_hash(password):
    return hashlib.sha256(password.encode()).hexdigest()

# Функция для проверки логина и пароля
def authenticate_user(email, password):
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()

    cursor.execute('''SELECT password FROM users WHERE email = ?''', (email,))
    user = cursor.fetchone()
    conn.close()

    if user:
        stored_password = user[0]
        if (stored_password) == generate_password_hash(password):
            return True
    return False




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

    