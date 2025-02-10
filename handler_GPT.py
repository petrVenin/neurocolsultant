from aiogram.types import Message
from aiogram import Bot, Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from openai import AsyncOpenAI
from collections import deque
import os
from dotenv import load_dotenv
from keyboards_gpt import kb_gpt
import logging
from utils_voice import handle_voice_message


load_dotenv()

class GPT_State(StatesGroup):
    choosing_option = State()
    awaiting_question = State()

router = Router()

chat_history = {}
user_temps = {}

try:
    os.environ["OPENAI_API_KEY"] = os.getenv('OPENAI_API_KEY')
    client = AsyncOpenAI()
    print("OpenAI API успешно инициализирован.")
except Exception as e:
    logging.error(f"Ошибка при инициализации OpenAI: {e}")

# Директория для аудиофайлов
AUDIO_DIR = "audio_files"

@router.message(Command('gpt'))
async def cmd_gpt_options(message: Message, state: FSMContext):
    await state.clear()
    await state.set_state(GPT_State.choosing_option)
    await message.answer(
        "🛠️ Выберите опцию:",
        reply_markup=await kb_gpt()

    )

# Хендлер для кнопки "📚 Задать вопрос GPT"
@router.message(GPT_State.choosing_option, (F.text == "📚 Задать вопрос GPT"))
async def ask_question_gpt(message: Message, state: FSMContext):
    """Переход к состоянию ожидания вопроса от пользователя."""
    logging.info(f"Пользователь {message.from_user.id} выбрал 'Задать вопрос GPT'. Перехожу в состояние 'awaiting_question'.")
    await state.clear()
    await state.set_state(GPT_State.awaiting_question)
    await message.answer(
        "📢 Напишите свой вопрос, и я постараюсь помочь!",
        reply_markup=None  # Убираем клавиатуру для ввода текста
    )

# Хендлер для кнопки "🗑 Очистить историю диалога (GPT)"
@router.message(GPT_State.choosing_option, F.text == "🗑 Очистить историю диалога (GPT)")
async def clear_history_gpt(message: Message, state: FSMContext):
    """Очищает историю сообщений для пользователя."""
    user_id = message.from_user.id
    if user_id in chat_history:
        chat_history[user_id].clear()
        await message.answer("🧹 История диалога очищена.", reply_markup=await kb_gpt())
    else:
        # await state.set_state(GPT_State.choosing_option)
        await message.answer("У вас ещё не было диалога. Выберете опцию.", reply_markup=await kb_gpt())

    await message.answer("❌ Извините, произошла ошибка при обработке вашего запроса. Попробуйте позже.")


# Обработчик текстовых и голосовых сообщений
@router.message(GPT_State.awaiting_question, ~F.text.startswith('/') & ~(F.text == "🗑 Очистить историю диалога (GPT)") | F.voice)
async def handle_text_or_voice_message(message: Message, state: FSMContext, bot: Bot):
    user_id = message.from_user.id
    user_question = ""

    if message.text:  # Если это текстовое сообщение
        user_question = message.text.strip()

        if len(user_question) > 2000:
            await message.answer("Ваш вопрос слишком длинный. Попробуйте сократить его до 2000 символов.")
            return
    elif message.voice:  # Если это голосовое сообщение
        try:
            user_question = await handle_voice_message(message, bot)
            if not user_question:
                await message.answer("Не удалось обработать голосовое сообщение. Попробуйте ещё раз.")
                return
            await message.answer(f"Ваше голосовое сообщение: {user_question}")
        except Exception as e:
            logging.error(f"Ошибка обработки голосового сообщения: {e}")
            await message.answer("❌ Произошла ошибка при обработке голосового сообщения.")
            return

    await message.answer("🤔 Обрабатываю ваш запрос...")

    # Проверяем или инициализируем историю чата
    if user_id not in chat_history:
        chat_history[user_id] = deque(maxlen=10)

    chat_history[user_id].append(f"Пользователь: {user_question}")

    # Генерация ответа
    try:
        temperature = user_temps.get(user_id, 0.1)
        full_history = "\n".join(chat_history[user_id])
        response = await client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "Ты - помощник-консультант, помогай пользователю решать вопросы."},
                {"role": "user", "content": full_history},
            ],
            temperature=temperature,
        )
        answer = response.choices[0].message.content
        chat_history[user_id].append(f"GPT: {answer}")
        await message.answer(answer)
    except Exception as e:
        logging.error(f"Ошибка взаимодействия с OpenAI: {e}")
        await message.answer("❌ Извините, произошла ошибка при обработке вашего запроса. Попробуйте позже.")



