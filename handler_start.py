from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import ReplyKeyboardBuilder
import logging
from handler_GPT import cmd_gpt_options
from handler_consultant import cmd_consultant_options
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from keyboards_main import kb_main


class main_State(StatesGroup):
    choosing_option = State()  # Ожидание выбора опции


router = Router()

#
# # Клавиатура главного меню
# async def kb_main():
#     builder = ReplyKeyboardBuilder()
#     buttons = [
#         "Консультант по AI",
#         "GPT с голосовым помощником",
#         "Что умеет бот"
#     ]
#     for button in buttons:
#         builder.button(text=button)
#     builder.adjust(3)
#     return builder.as_markup(resize_keyboard=True, one_time_keyboard=True)


@router.message(F.text == "🏠 Главное меню")
async def return_to_main_menu(message: Message, state: FSMContext):
    """Возвращает пользователя в главное меню."""
    await state.clear()  # Очищаем текущее состояние
    await message.answer(
        "🏠 Вы вернулись в главное меню. Выберите режим работы:",
        reply_markup=await kb_main()  # Показываем клавиатуру главного меню
    )
    await state.set_state(main_State.choosing_option)


# Главное меню
@router.message(Command('start'))
async def cmd_main_options(message: Message, state: FSMContext):
    """Хендлер для команды /start"""
    await state.clear()  # Очистка состояний FSM
    logging.info(f"Пользователь {message.from_user.id} начал сессию.")
    await message.answer("🛠️ Выберите режим работы:", reply_markup=await kb_main())
    await state.set_state(main_State.choosing_option)


# Обработка выбора режима
@router.message(main_State.choosing_option)
async def handle_main_menu(message: Message, state: FSMContext):
    """Обработка выбора из главного меню."""

    # Печать для отладки состояния
    current_state = await state.get_state()
    logging.info(f"Текущее состояние пользователя: {current_state}")

    user_choice = message.text

    # Выбор "Консультант по AI"
    if user_choice == "Консультант по AI":
        logging.info(f"Пользователь {message.from_user.id} выбрал режим: Консультант по AI.")
        # Направляем пользователя в режим консультанта
        await cmd_consultant_options(message, state)

    # Выбор "GPT с голосовым помощником"
    elif user_choice == "GPT с голосовым помощником":
        logging.info(f"Пользователь {message.from_user.id} выбрал режим: GPT с голосовым помощником.")
        # Направляем пользователя в режим GPT
        await cmd_gpt_options(message, state)

    # Выбор "Что умеет бот"
    elif user_choice == "Что умеет бот":
        await message.answer("🤖 Бот умеет работать в режимах:\n1️⃣ Консультант по AI\n2️⃣ GPT с голосовым помощником.",
                             reply_markup=await kb_main())

    # Некорректный выбор
    else:
        logging.warning(f"Пользователь {message.from_user.id} ввёл некорректный вариант: {user_choice}")
        await message.answer("Пожалуйста, выберите режим из меню.", reply_markup=await kb_main())
