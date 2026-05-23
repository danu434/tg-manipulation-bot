import asyncio
import os

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from openai import AsyncOpenAI

# ========== НАСТРОЙКИ ==========
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# ========== OPENROUTER ==========
client = AsyncOpenAI(
    api_key=OPENROUTER_API_KEY,
    base_url="https://openrouter.ai/api/v1"
)

# ========== ТЕХНИКИ ==========
LEVEL_TECHNIQUES = {
    1: "Повышение голоса, ультиматум, прямая угроза, шантаж",
    2: "Вина, стыд, жалость, ревность",
    3: "Обобщение, ложная дихотомия, FOMO",
    4: "Газлайтинг, проекция, игра в жертву",
    5: "Тонкий газлайтинг, софизм, иллюзия выбора",
    6: "Пресуппозиция, чтение мыслей, встроенная команда",
    7: "Эриксоновский гипноз, ведение, захват идентичности",
    8: "Метод Сократа, дверь в лицо, когнитивный диссонанс",
    9: "Манипуляция картиной мира, контроль мышления"
}

# ========== ПРОМПТЫ ==========
def get_generation_prompt(level):
    techniques = LEVEL_TECHNIQUES.get(level, LEVEL_TECHNIQUES[1])

    return f"""
Ты — генератор учебных примеров манипуляций.

Уровень: {level}
Техники: {techniques}

Сгенерируй:

📋 Ситуация:
...

👤 Оппонент:
...

Без анализа.
"""

def get_check_prompt(level, user_answer):
    techniques = LEVEL_TECHNIQUES.get(level, LEVEL_TECHNIQUES[1])

    return f"""
Проверь ответ пользователя.

Уровень: {level}
Техники: {techniques}

Ответ пользователя:
{user_answer}

Формат:

✅ Найдено:
❌ Пропущено:
💬 Оценка ответа:
"""

# ========== КЛАВИАТУРА ==========
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

# ========== ХРАНЕНИЕ ==========
user_levels = {}

# ========== БОТ ==========
bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()

# ========== /start ==========
@dp.message(Command("start"))
async def start(message: types.Message):
    user_levels[message.from_user.id] = 1

    await message.answer(
        "👋 Добро пожаловать.\nВыбери уровень:",
        reply_markup=get_levels_keyboard()
    )

# ========== ПОМОЩЬ ==========
@dp.message(F.text == "📘 Как отвечать")
async def help_handler(message: types.Message):
    await message.answer(
        "Нужно:\n"
        "1. Найти техники\n"
        "2. Ответить манипулятору\n\n"
        "Пример:\n"
        "Нашёл: давление, вина\n"
        "Ответ: Я не согласен с таким тоном."
    )

# ========== ВЫБОР УРОВНЯ ==========
@dp.message(F.text.startswith("Уровень"))
async def choose_level(message: types.Message):
    try:
        level = int(message.text.split()[1])

        if not 1 <= level <= 9:
            return

        user_levels[message.from_user.id] = level

        await message.answer(
            f"✅ Уровень {level} выбран.\nГенерирую пример..."
        )

        await send_example(message, level)

    except Exception:
        await message.answer("Ошибка выбора уровня.")

# ========== ОТВЕТ ПОЛЬЗОВАТЕЛЯ ==========
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
        await message.answer(f"❌ Ошибка:\n{str(e)[:300]}")

# ========== ГЕНЕРАЦИЯ ==========
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
        await message.answer(f"❌ Ошибка:\n{str(e)[:300]}")

# ========== MAIN ==========
async def main():
    print("BOT STARTED")

    await bot.delete_webhook(drop_pending_updates=True)

    await dp.start_polling(
        bot,
        skip_updates=True
    )

# ========== ЗАПУСК ==========
if __name__ == "__main__":
    asyncio.run(main())
