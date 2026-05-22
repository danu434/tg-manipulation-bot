import asyncio
import os
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from openai import AsyncOpenAI

# ========== НАСТРОЙКИ (Render сам подставит переменные) ==========
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")

# ========== КЛИЕНТ DEEPSEEK ==========
deepseek = AsyncOpenAI(
    api_key=DEEPSEEK_API_KEY,
    base_url="https://api.deepseek.com"
)

# ========== КЛАВИАТУРА С УРОВНЯМИ ==========
def get_levels_keyboard():
    buttons = [
        [KeyboardButton(text="Уровень 1"), KeyboardButton(text="Уровень 2"), KeyboardButton(text="Уровень 3")],
        [KeyboardButton(text="Уровень 4"), KeyboardButton(text="Уровень 5"), KeyboardButton(text="Уровень 6")],
        [KeyboardButton(text="Уровень 7"), KeyboardButton(text="Уровень 8"), KeyboardButton(text="Уровень 9")],
        [KeyboardButton(text="🔄 Сменить уровень")]
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

# ========== ХРАНЕНИЕ УРОВНЕЙ ПОЛЬЗОВАТЕЛЕЙ ==========
user_levels = {}

# ========== БОТ ==========
bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()

@dp.message(Command("start"))
async def start(message: types.Message):
    user_levels[message.from_user.id] = 1
    await message.answer(
        "👋 Привет! Это бот для тренировки распознавания манипуляций.\n\n"
        "Выбери уровень сложности:",
        reply_markup=get_levels_keyboard()
    )

@dp.message(Command("menu"))
async def menu(message: types.Message):
    await message.answer(
        "Выбери уровень:",
        reply_markup=get_levels_keyboard()
    )

@dp.message(lambda msg: msg.text and msg.text.startswith("Уровень"))
async def set_level(message: types.Message):
    try:
        level = int(message.text.split()[1])
        if 1 <= level <= 9:
            user_levels[message.from_user.id] = level
            await message.answer(
                f"✅ Уровень {level} выбран. Сейчас пришлю пример...",
                reply_markup=get_levels_keyboard()
            )
            await send_manipulation_example(message, level)
        else:
            await message.answer("Уровень должен быть от 1 до 9")
    except:
        await message.answer("Что-то пошло не так")

@dp.message(lambda msg: msg.text == "🔄 Сменить уровень")
async def change_level(message: types.Message):
    await message.answer(
        "Выбери новый уровень:",
        reply_markup=get_levels_keyboard()
    )

@dp.message()
async def handle_answer(message: types.Message):
    user_id = message.from_user.id
    level = user_levels.get(user_id, 1)
    
    response = await deepseek.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {"role": "system", "content": f"Ты оцениваешь ответ пользователя на задание по распознаванию манипуляций (уровень {level}). Дай краткий анализ: правильно/неправильно, что упущено. Потом сгенерируй новый пример манипуляции уровня {level}. Формат ответа: сначала анализ, потом '---', потом новый пример."},
            {"role": "user", "content": message.text}
        ]
    )
    
    reply = response.choices[0].message.content
    
    if "---" in reply:
        parts = reply.split("---", 1)
        analysis = parts[0].strip()
        new_example = parts[1].strip()
        
        await message.answer(f"📊 Анализ:\n{analysis}\n\n📝 Новый пример:\n{new_example}")
    else:
        await message.answer(reply)

async def send_manipulation_example(message: types.Message, level: int):
    response = await deepseek.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {"role": "system", "content": f"Ты генерируешь примеры манипуляций для тренировки. Уровень сложности: {level} (1-самый простой, 9-самый сложный). Опиши ситуацию с манипуляцией. Не пиши в чем именно манипуляция, пусть пользователь сам догадается."},
            {"role": "user", "content": "Сгенерируй пример манипуляции"}
        ]
    )
    
    example = response.choices[0].message.content
    await message.answer(f"📋 Пример (уровень {level}):\n\n{example}")

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())