from aiogram import types
from aiogram.types import ReplyKeyboardRemove, \
    ReplyKeyboardMarkup, KeyboardButton, \
    InlineKeyboardMarkup, InlineKeyboardButton

from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder


def get_yes_no_kb() -> ReplyKeyboardMarkup:
    kb = ReplyKeyboardBuilder()
    kb.button(text="Да")
    kb.button(text="Нет")
    kb.adjust(2)
    return kb.as_markup(resize_keyboard=True)


def auth_kb() -> ReplyKeyboardMarkup:
    auth_builder = ReplyKeyboardBuilder()

    auth_builder.row(types.KeyboardButton(text='🔐 Авторизация'))
    auth_builder.row(types.KeyboardButton(text='⚙️ Настройки'))

    return auth_builder.as_markup(resize_keyboard=True)


def askq_kb() -> ReplyKeyboardMarkup:
    upload_builder = ReplyKeyboardBuilder()
    upload_builder.row(types.KeyboardButton(text='📄 Задать вопрос'))
    upload_builder.row(types.KeyboardButton(text='💡 Задать вопрос в креативном режиме')) #🔄
    upload_builder.row(types.KeyboardButton(text='⚙️ Настройки'))

    return upload_builder.as_markup(resize_keyboard=True)