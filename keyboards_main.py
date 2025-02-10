from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder


async def kb_main():
    builder = ReplyKeyboardBuilder()
    buttons = [
        "Консультант по AI",
        "GPT с голосовым помощником",
        "Что умеет бот"
    ]
    for button in buttons:
        builder.button(text=button)
    builder.adjust(1)

    return builder.as_markup(
        resize_keyboard=True,  # Клавиатура подстраивается под размер экрана
        one_time_keyboard=True)  # Клавиатура исчезнет после выбора варианта