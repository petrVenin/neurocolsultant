from aiogram.types import Message
from aiogram import Bot, Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from consultant_ai import save_profile, generate_answer_dialog_search
from consultant_ai import load_profile, ProjectContext
from promt import prompt_for_GPT_DS_5
from keyboards_consultant import kb_consultant
from aiogram.fsm.state import State, StatesGroup
import logging
import os
from openai import OpenAIError, AsyncOpenAI, OpenAI
from dotenv import load_dotenv


# Загрузка переменных окружения
load_dotenv()
# Класс состояний
class Consultant_State(StatesGroup):
    choosing_option = State()  # Ожидание выбора опции
    active_dialog = State()  # Активный диалог с консультантом

router = Router()

# Начальная информация о пользователе и проекте
default_user_info = {"type_user": "", "contact": ""}
default_project_info = {
    "type": "",
    "goal": "",
    "current_stage": "",
    "completed_stages": [],
    "remaining_tasks": [],
    "plan": "",
}

# Папка для хранения аудиофайлов
AUDIO_DIR = './audio'

# Загружаем токен из .env
os.environ["OPENAI_API_KEY"] = os.getenv('OPENAI_API_KEY')
openai_key = os.getenv('OPENAI_API_KEY')

# Хендлер для команды /consultant
@router.message(Command('consultant'))
async def cmd_consultant_options(message: Message, state: FSMContext):
    await state.clear()
    """Хендлер активации режима консультанта."""
    # Инициализируем контекст для пользователя
    context = ProjectContext(default_user_info, default_project_info)
    await state.update_data(context=context)  # Сохраняем контекст в FSM

    await message.answer(
        "🛠️ Вы в режиме консультанта AI. Выберите опцию:",
        reply_markup=await kb_consultant(),
    )
    await state.set_state(Consultant_State.choosing_option)



# Хендлер текстовых сообщений в режиме консультанта
@router.message(Consultant_State.choosing_option, ((F.text == "🤖 Задать вопрос AI")) & ~F.text.startswith('/'))
async def ask_question_gpt(message: Message, state: FSMContext):
    """Переход к состоянию ожидания вопроса от пользователя."""
    logging.info(f"Пользователь {message.from_user.id} выбрал 'Задать вопрос Консультанту AI. Перехожу в состояние 'active_dialog'.")
    await state.set_state(Consultant_State.active_dialog)
    await message.answer(
        "📢 Напишите свой вопрос, и я постараюсь помочь!",
        reply_markup=None  # Убираем клавиатуру для ввода текста
    )



@router.message(Consultant_State.active_dialog, (F.text =="🗑 Очистить историю диалога (AI)"))
async def ask_question_gpt_clear(message: Message, state: FSMContext):
    """Переход к состоянию ожидания вопроса от пользователя."""
    logging.info(f"Пользователь {message.from_user.id} очистил историю диалога (AI). Перехожу в состояние 'active_dialog'.")

    """Удаляем профиль и историю диалога из файла."""
    if os.path.exists("profile.json") and os.path.exists("dialog_history.txt"):
        try:
            os.remove("profile.json")
            os.remove("dialog_history.txt")
            print("Профиль и история диалога успешно удалены.")

            # Инициализируем контекст для пользователя
            context = ProjectContext(default_user_info, default_project_info)
            await state.update_data(context=context)  # Сохраняем контекст в FSM

            await message.answer("🧹 История диалога (AI) очищена. Чем я могу помочь?", reply_markup=None)

        except Exception as e:
            print(f"Ошибка при удалении профиля: {e}")
    else:
        await message.answer("У вас ещё не было диалога (AI). Пожалуйста, задайте свой вопрос.")
        # await state.clear()
        # await state.set_state(Consultant_State.active_dialog)


    await state.set_state(Consultant_State.active_dialog)
    await message.answer(
        "📢 Напишите свой вопрос, и я постараюсь помочь!",
        reply_markup=None  # Убираем клавиатуру для ввода текста
    )


# Хендлер для кнопки "🗑 Очистить историю диалога (AI)"
@router.message(Consultant_State.choosing_option, F.text == "🗑 Очистить историю диалога (AI)")
async def clear_history_ai(message: Message, state: FSMContext):
    """Очищает историю сообщений для пользователя."""
    user_id = message.from_user.id
    # Удаление временных файлов

    """Удаляем профиль и историю диалога из файла."""
    if os.path.exists("profile.json") and os.path.exists("dialog_history.txt"):
        try:
            os.remove("profile.json")
            os.remove("dialog_history.txt")
            logging.info(f"Пользователь {user_id} очистил историю диалога (AI).")

            # Инициализируем контекст для пользователя
            context = ProjectContext(default_user_info, default_project_info)
            await state.update_data(context=context)  # Сохраняем контекст в FSM
            await message.answer("🧹 История диалога (AI) очищена. Выберите опцию:", reply_markup=await kb_consultant())

        except Exception as e:
            print(f"Ошибка при удалении профиля: {e}")

    else:

        await message.answer("У вас ещё не было диалога (AI). Выберите опцию:", reply_markup=await kb_consultant())
        # await state.clear()
        # await state.set_state(Consultant_State.active_dialog)


@router.message(
    Consultant_State.active_dialog,
    (F.text & ~F.text.startswith('/') & ~F.text == "🗑 Очистить историю диалога (AI)") | F.voice
)
async def handler_text_or_voice_message(message: Message, state: FSMContext, bot: Bot):
    """Обрабатывает текстовые и голосовые сообщения в режиме консультанта."""
    data = await state.get_data()
    context: ProjectContext = data.get("context")  # Получаем контекст пользователя

    user_question = ""

    if message.text:  # Обработка текстового сообщения
        user_question = message.text.strip().lower()
    elif message.voice:  # Обработка голосового сообщения
        transcription = await handle_voice_message(message, bot)

        # Если транскрипция успешна
        if transcription:
            user_question = transcription.strip().lower()
            await message.answer(f"Ваше голосовое сообщение: {user_question}")
        else:  # Обработка ошибки транскрипции
            await message.answer("Не удалось обработать голосовое сообщение. Попробуйте снова.")
            return  # Завершаем хэндлер

    # Завершение диалога по ключевому слову
    if user_question == "stop":
        await message.answer("Диалог завершён. Если нужно начать заново, введите /start.")
        save_profile(context)  # Сохраняем контекст
        await state.clear()
        logging.info(f"Пользователь {message.from_user.id} завершил диалог.")
        return

    # Проверка пустого вопроса
    if not user_question:  # Если вопрос пустой, ничего не делаем
        logging.info(f"Пользователь {message.from_user.id} отправил пустое сообщение.")
        await message.answer("Сообщение пустое. Попробуйте ещё раз.")
        return

    # Генерация ответа с помощью AI
    try:
        answer, used_tokens, cost = generate_answer_dialog_search(
            prompt_for_GPT_DS_5, user_question, context
        )

        # Обновляем контекст
        context.total_tokens += used_tokens
        context.total_cost += cost
        context.update(f"Пользователь: {user_question}\nКонсультант: {answer}\n")

        # Отправляем ответ пользователю
        await message.answer(answer)

        # Логирование токенов и стоимости
        log_message = (
            f"🔹 Использовано токенов: {used_tokens}, Стоимость: ${cost:.5f}\n"
            f"🔹 Всего токенов: {context.total_tokens}, Общая стоимость: ${context.total_cost:.5f}"
        )
        await message.answer(log_message)

        # Сохраняем контекст и историю диалога
        save_profile(context)
        context.save_dialog_history()
        logging.info(f"Пользователь {message.from_user.id} сохранил историю диалога.")
    except Exception as e:
        # Отправляем сообщение об ошибке
        logging.error(f"Ошибка генерации ответа: {e}")
        await message.answer(f"❌ Произошла ошибка: {e}")



# Функция для транскрипции аудио через Whisper
async def get_audio_transcription(file_path: str) -> str:
    try:
        with open(file_path, "rb") as audio_file:
            client = AsyncOpenAI()
            response = await client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file
            )
            return response.text
    except OpenAIError as e:
        logging.error(f"Ошибка при транскрипции аудио: {e}")
        return "Произошла ошибка при обработке аудио."



# Хендлер для голосовых сообщений
# @router.message(F.voice)
async def handle_voice_message(message: Message, bot: Bot):
    user_id = message.from_user.id
    voice = message.voice

    # Создание директории для аудиофайлов
    if not os.path.exists(AUDIO_DIR):
        os.makedirs(AUDIO_DIR)

    # Получение файла голосового сообщения
    file_id = voice.file_id
    file = await bot.get_file(file_id)
    input_audio_path = os.path.join(AUDIO_DIR, f'{file_id}.ogg')
    await bot.download_file(file.file_path, input_audio_path)

    # await message.answer("Обрабатываю ваше голосовое сообщение...")

    # Транскрипция с использованием Whisper
    transcription = await get_audio_transcription(input_audio_path)
    # await message.answer("Ваше сообщение: " + transcription)

    return transcription

