import asyncio
import os

from aiohttp import web
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from openai import AsyncOpenAI

# =========================
# НАСТРОЙКИ
# =========================

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
PORT = int(os.getenv("PORT", 10000))

# =========================
# OPENROUTER
# =========================

client = AsyncOpenAI(
    api_key=OPENROUTER_API_KEY,
    base_url="https://openrouter.ai/api/v1"
)

# =========================
# ТЕХНИКИ
# =========================

LEVEL_TECHNIQUES = {
    1: "Повышение голоса, ультиматум, прямая угроза, шантаж, запугивание",
    2: "Вина, стыд, жалость, ревность, обесценивание",
    3: "Обобщение, ложная дихотомия, FOMO, создание дефицита",
    4: "Газлайтинг, проекция, игра в жертву, провокация",
    5: "Тонкий газлайтинг, софизм, иллюзия выбора",
    6: "Пресуппозиция, чтение мыслей, встроенная команда",
    7: "Эриксоновский гипноз, ведение, захват идентичности",
    8: "Метод Сократа, дверь в лицо, когнитивный диссонанс",
    9: "Манипуляция картиной мира, контроль мышления"
}

# =========================
# ПРОМПТЫ
# =========================

def get_generation_prompt(level):
    techniques = LEVEL_TECHNIQUES.get(level, LEVEL_TECHNIQUES[1])

    return f"""
Ты — генератор учебных примеров манипуляций.

Уровень сложности: {level}

Техники:
{techniques}

Сгенерируй короткий реалистичный пример.

Формат строго такой:

📋 Ситуация:
...

👤 Оппонент:
...

Без анализа.
"""

def get_check_prompt(level, user_answer):
    techniques = LEVEL_TECHNIQUES.get(level, LEVEL_TECHNIQUES[1])

    return f"""
Ты проверяющий в тренажёре манипуляций.

Уровень: {level}

Техники:
{techniques}

Ответ пользователя:
{user_answer}

Формат ответа:

✅ Найдено:
❌ Пропущено:
💬 Оценка ответа:
"""

# =========================
# КЛАВИАТУРА
# =========================

def get_levels_keyboard():
    buttons = [
        [
            KeyboardButton(text="Уровень 1"),
            KeyboardButton(text="Уровень 2"),
            KeyboardButton(text="Уровень 3")
        ],
        [
            KeyboardButton(text="Уровень 4"),
            KeyboardButton(text="Уровень 5"),
            KeyboardButton(text="Уровень 6")
        ],
        [
            KeyboardButton(text="Уровень 7"),
            KeyboardButton(text="Уровень 8"),
            KeyboardButton(text="Уровень 9")
        ],
        [
            KeyboardButton(text="📘 Как отвечать")
        ]
    ]

    return ReplyKeyboardMarkup(
        keyboard=buttons,
        resize_keyboard=True
    )

# =========================
# ХРАНЕНИЕ
# =========================

user_levels = {}

# =========================
# БОТ
# =========================

bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()

# =========================
# WEB SERVER ДЛЯ RENDER
# =========================

async def health(request):
    return web.Response(text="OK")

async def start_webserver():
    app = web.Application()

    app.router.add_get("/", health)

    runner = web.AppRunner(app)
    await runner.setup()

    site = web.TCPSite(
        runner,
        host="0.0.0.0",
        port=PORT
    )

    await site.start()

# =========================
# /start
# =========================

@dp.message(Command("start"))
async def start(message: types.Message):
    user_levels[message.from_user.id] = 1

    await message.answer(
        "👋 Добро пожаловать в тренажёр манипуляций.\n\nВыбери уровень:",
        reply_markup=get_levels_keyboard()
    )

# =========================
# ПОМОЩЬ
# =========================

@dp.message(F.text == "📘 Как отвечать")
async def help_handler(message: types.Message):
    text = (
        "Твоя задача:\n\n"
        "1. Найти манипулятивные техники\n"
        "2. Ответить манипулятору\n\n"
        "Пример:\n\n"
        "Нашёл: давление, вина, ультиматум\n"
        "Ответ: Я не согласен разговаривать в таком тоне."
    )

    await message.answer(text)

# =========================
# ВЫБОР УРОВНЯ
# =========================

@dp.message(F.text.startswith("Уровень"))
async def choose_level(message: types.Message):
    try:
        level = int(message.text.split()[1])

        if level < 1 or level > 9:
            await message.answer("Уровень должен быть от 1 до 9")
            return

        user_levels[message.from_user.id] = level

        await message.answer(
            f"✅ Уровень {level} выбран.\n\nГенерирую пример..."
        )

        await send_example(message, level)

    except Exception:
        await message.answer("Ошибка выбора уровня.")

# =========================
# ОБРАБОТКА ОТВЕТОВ
# =========================

@dp.message()
async def handle_answer(message: types.Message):
    level = user_levels.get(message.from_user.id, 1)

    await message.answer("🔍 Проверяю ответ...")

    try:
        response = await client.chat.completions.create(
            model="deepseek/deepseek-chat-v3-0324:free",
            messages=[
                {
                    "role": "user",
                    "content": get_check_prompt(level, message.text)
                }
            ]
        )

        reply = response.choices[0].message.content

        await message.answer(reply)

    except Exception as e:
        await message.answer(
            f"❌ Ошибка проверки:\n{str(e)[:300]}"
        )

# =========================
# ГЕНЕРАЦИЯ ПРИМЕРА
# =========================

async def send_example(message: types.Message, level: int):
    try:
        response = await client.chat.completions.create(
            model="deepseek/deepseek-chat-v3-0324:free",
            messages=[
                {
                    "role": "user",
                    "content": get_generation_prompt(level)
                }
            ]
        )

        example = response.choices[0].message.content

        await message.answer(example)

    except Exception as e:
        await message.answer(
            f"❌ Ошибка генерации:\n{str(e)[:300]}"
        )

# =========================
# MAIN
# =========================

async def main():
    print("BOT STARTED")

    await bot.delete_webhook(
        drop_pending_updates=True
    )

    await start_webserver()

    await dp.start_polling(
        bot,
        skip_updates=True
    )

# =========================
# ЗАПУСК
# =========================

if __name__ == "__main__":
    asyncio.run(main())
