from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder


async def kb_gpt():
    builder = ReplyKeyboardBuilder()
    buttons = [
        "📚 Задать вопрос GPT",
        "🗑 Очистить историю диалога (GPT)",
        "🏠 Главное меню"  # Добавляем кнопку возврата в главное меню
    ]
    for button in buttons:
        builder.button(text=button)
    builder.adjust(1)  # Настраиваем ширину кнопок

    return builder.as_markup(
        resize_keyboard=True,  # Клавиатура подстраивается под размер экрана
        one_time_keyboard=True  # Клавиатура исчезнет после выбора варианта
    )
