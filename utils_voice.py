from aiogram.types import Message
from aiogram import F, Router
from aiogram import Bot, Router, F
from collections import deque
import logging
import os
from openai import OpenAIError, AsyncOpenAI, OpenAI
import re
import asyncio


# Директория для аудиофайлов
AUDIO_DIR = "audio_files"



# Функция транскрипции голосового сообщения
async def handle_voice_message(message: Message, bot: Bot) -> str:
    """Обрабатывает и транскрибирует голосовое сообщение."""
    voice = message.voice

    # Создаём директорию для аудиофайлов, если её нет
    if not os.path.exists(AUDIO_DIR):
        os.makedirs(AUDIO_DIR)

    # Скачиваем аудиофайл
    file_id = voice.file_id
    file = await bot.get_file(file_id)
    input_audio_path = os.path.join(AUDIO_DIR, f"{file_id}.ogg")
    await bot.download_file(file.file_path, input_audio_path)

    # Транскрипция с использованием Whisper API
    transcription = await get_audio_transcription(input_audio_path)
    return transcription

# # Функция транскрипции (пример)
# async def get_audio_transcription(audio_path: str) -> str:
#     """Транскрибирует аудиофайл с помощью Whisper API от OpenAI."""
#     try:
#         import openai
#         with open(audio_path, "rb") as audio_file:
#             response = openai.Audio.transcribe("whisper-1", audio_file)
#         return response["text"]
#     except Exception as e:
#         logging.error(f"Ошибка транскрипции аудио: {e}")
#         return ""

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


# def escape_markdown(text: str) -> str:
#     """Экранирует специальные символы для MarkdownV2."""
#     # escape_chars = r"[_*[\]()~`>#+\-=|{}.!]"
#     escape_chars = r"[_*[\]()~>#+\-=|{}.!]"
#     return re.sub(escape_chars, r"\\\g<0>", text)
#
# async def send_long_message(message: Message, bot: Bot, answer: str):
#     # Экранируем ответ для MarkdownV2
#     escaped_answer = escape_markdown(answer)
#
#     if len(escaped_answer) < 4096:
#         await message.answer(escaped_answer, parse_mode="MarkdownV2")
#     else:
#         # Разбиваем текст на части, если он слишком длинный
#         max_length = 4096  # Максимальная длина сообщения в Telegram
#         for i in range(0, len(escaped_answer), max_length):
#             await message.answer(escaped_answer[i:i + max_length], parse_mode="MarkdownV2")
#             await asyncio.sleep(1)

import re
import asyncio
from aiogram.types import Message

def escape_markdown(text: str) -> str:
    """Экранирует специальные символы для MarkdownV2."""
    escape_chars = r"[_*[\]()~`>#+\-=|{}.!]"
    return re.sub(escape_chars, r"\\\g<0>", text)

async def send_long_message(message: Message, bot: Bot, answer: str):
    """Отправляет длинное сообщение с поддержкой форматирования MarkdownV2."""
    # Разделяем текст на части, если длина превышает лимит
    max_length = 4096  # Максимальная длина сообщения в Telegram
    parts = []

    # Проверка на наличие блоков кода
    code_blocks = re.findall(r"```.*?```", answer, re.DOTALL)

    if code_blocks:
        # Убираем блоки кода из основного текста
        for block in code_blocks:
            answer = answer.replace(block, "")
            parts.append(block)

    # Остальной текст экранируем для Markdown
    if answer.strip():
        escaped_answer = escape_markdown(answer.strip())
        parts.append(escaped_answer)

    # Отправляем каждую часть текста
    for part in parts:
        if len(part) < max_length:
            await message.answer(part, parse_mode="MarkdownV2")
        else:
            # Разбиваем слишком длинные части
            for i in range(0, len(part), max_length):
                await message.answer(part[i:i + max_length], parse_mode="MarkdownV2")
                await asyncio.sleep(1)
