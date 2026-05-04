import asyncio
import logging
import os
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
import google.generativeai as genai

# --- ТВОИ КЛЮЧИ (ВСТАВЛЕНЫ ДЛЯ ТЕСТА) ---
TG_TOKEN = '8725883337:AAGCfjjOXaSO_3R7MYx1ntx_rjlduzcup50'
GEMINI_KEY = 'AIzaSyAOhnyF8lQH5Av6dMIKRk8esYEY9TjiJgA'

# Настройка Gemini
genai.configure(api_key=GEMINI_KEY)
generation_config = {
    "temperature": 0.8,
    "top_p": 0.95,
    "max_output_tokens": 8192,
}

bot = Bot(token=TG_TOKEN)
dp = Dispatcher()

# Хранилище истории (в памяти)
user_histories = {}

def get_history(user_id):
    if user_id not in user_histories:
        user_histories[user_id] = []
    return user_histories[user_id]

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        "🚀 **Бот запущен и готов!**\n\n"
        "Я понимаю:\n"
        "1. Текст (просто пиши)\n"
        "2. Фото (шли с описанием)\n"
        "3. Голос (отвечу на ГС)\n\n"
        "Команда /clear очистит историю последних 10 сообщений."
    )

@dp.message(Command("clear"))
async def cmd_clear(message: types.Message):
    user_histories[message.from_user.id] = []
    await message.answer("🧹 Контекст очищен!")

@dp.message()
async def handle_all(message: types.Message):
    user_id = message.from_user.id
    # Визуальный индикатор "печатает..."
    await bot.send_chat_action(message.chat.id, action="typing")
    
    model = genai.GenerativeModel("gemini-1.5-flash", generation_config=generation_config)
    parts = []

    # Текст
    if message.text:
        parts.append(message.text)
    
    # Фото
    elif message.photo:
        photo = message.photo[-1]
        file = await bot.get_file(photo.file_id)
        img_bytes = await bot.download_file(file.file_path)
        parts.append({"mime_type": "image/jpeg", "data": img_bytes.read()})
        if message.caption:
            parts.append(message.caption)
            
    # Голосовое сообщение
    elif message.voice:
        voice = message.voice
        file = await bot.get_file(voice.file_id)
        voice_bytes = await bot.download_file(file.file_path)
        parts.append({"mime_type": "audio/ogg", "data": voice_bytes.read()})
        if message.caption:
            parts.append(message.caption)

    if not parts:
        return

    try:
        # Загружаем историю (обрезаем до последних 10 сообщений)
        history = get_history(user_id)[-10:]
        
        # Создаем чат-сессию
        chat = model.start_chat(history=history)
        
        # Запрос к ИИ (выполняем в отдельном потоке, чтобы не вешать бота)
        response = await asyncio.to_thread(chat.send_message, parts)
        
        # Обновляем историю в памяти
        # (сохраняем только текст, чтобы не забивать ОЗУ картинками)
        user_input_text = message.text or message.caption or "[Медиа-файл]"
        history.append({"role": "user", "parts": [user_input_text]})
        history.append({"role": "model", "parts": [response.text]})
        user_histories[user_id] = history[-12:] # чуть с запасом

        # Отправляем ответ
        await message.answer(response.text, parse_mode="Markdown")

    except Exception as e:
        logging.error(f"Ошибка: {e}")
        await message.answer("⚠️ Ошибка. Попробуй /clear или проверь API ключ.")

async def main():
    logging.basicConfig(level=logging.INFO)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
