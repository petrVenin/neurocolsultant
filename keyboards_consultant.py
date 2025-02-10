from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder

async def kb_consultant():
    builder = ReplyKeyboardBuilder()
    buttons = [
        "🤖 Задать вопрос AI",
        # "🆘 Помощь",
        "🗑 Очистить историю диалога (AI)",
        "🏠 Главное меню"
    ]
    for button in buttons:
        builder.button(text=button)
    builder.adjust(1)

    return builder.as_markup(
        resize_keyboard=True,  # Клавиатура подстраивается под размер экрана
        one_time_keyboard=True)  # Клавиатура исчезнет после выбора варианта

