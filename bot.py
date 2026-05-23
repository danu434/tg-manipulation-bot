import asyncio
import os
from aiohttp import web
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from openai import AsyncOpenAI

# ========== НАСТРОЙКИ ==========
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
PORT = int(os.getenv("PORT", 10000))

# ========== КЛИЕНТ OPENROUTER ==========
client = AsyncOpenAI(
    api_key=OPENROUTER_API_KEY,
    base_url="https://openrouter.ai/api/v1"
)

# ========== ТЕХНИКИ ПО УРОВНЯМ ==========
LEVEL_TECHNIQUES = {
    1: "Повышение голоса, ультиматум, прямая угроза, шантаж, запугивание, приказ, оскорбление, перебивание, демонстративный гнев, физическое вторжение в пространство, игнорирование в лоб, обвинение без доказательств, запрет, требование немедленного решения",
    2: "Вина, стыд, жалость, обида, ревность, лесть грубая, критика под видом заботы, сравнение с другими, обесценивание, демонстративное молчание, пассивная агрессия прямая, угроза разрывом, апелляция к возрасту/статусу, пристыжение при свидетелях",
    3: "Обобщение, ложная дихотомия, навешивание ярлыков, апелляция к авторитету, апелляция к большинству, FOMO, цейтнот, создание дефицита, эффект привязки (якорь), ложная причина post hoc, скользкий путь, апелляция к традиции, подмена тезиса, частный случай как доказательство",
    4: "Триангуляция, газлайтинг (грубый), проекция, игра в жертву, мнимая беспомощность, создание долга, намёк с давлением, саботаж, двойное послание, провокация на эмоции, подставной вопрос, тест на лояльность, комплимент-укол, передёргивание",
    5: "Газлайтинг тонкий, straw man, круговая аргументация, двусмысленность намеренная, софизм, подталкивание к нужному выводу, секретность/недоговорки, игра на опережение, иллюзия выбора, отзеркаливание, подстройка, якорение, рефрейминг манипулятивный, разрыв шаблона",
    6: "Пресуппозиция, чтение мыслей (приписывание мотивов), встроенная команда, трюизмы, импликатура, мета-моделирование в обход, номинализация, неспецифические глаголы, универсальные квантификаторы, модальные операторы долженствования, потерянная перформативность, инверсия ответственности, абстрагирование, комплексный эквивалент",
    7: "Эриксоновский гипноз (база), встроенная метафора, рассеивание, использование транса, диссоциация управляемая, якорь пространственный, калибровка, ведение, раппорт принудительный, перегрузка сенсорная, подпороговое воздействие, контекстуальный рефрейминг, ценностный конфликт, захват идентичности",
    8: "Метод Сократа (принуждение к согласию), метод вилки, техника двери в лицо, техника ноги в двери, техника низкого шара, затратный метод, эффект Бенджамина Франклина, принудительное обязательство, публичное обещание, когнитивный диссонанс (принудительный), рамка выигрыш-проигрыш, двойной агент, информационная блокада, утечка подконтрольная",
    9: "Парадоксальное вмешательство, предписание симптома, рефрейминг идентичности, генеративный рефрейминг, псевдоориентированное слушание, сократический диалог (продвинутый), экзистенциальное давление, манипуляция картиной мира, меметический захват, нарративное подчинение, инфоцыганский каскад, сектантская изоляция (поэтапная), контроль среды, контроль информации, контроль мышления, контроль эмоций (тотальный)"
}

# ========== ХРАНЕНИЕ СОСТОЯНИЙ ==========
user_mode = {}        # "single" или "endless"
user_levels = {}      # текущий уровень
user_last_example = {}# последний пример для проверки
user_story = {}       # {user_id: {"level": 1, "context": "...", "history": "..."}}

# ========== ПРОМПТЫ ==========
def get_generation_prompt(level):
    techniques = LEVEL_TECHNIQUES.get(level, LEVEL_TECHNIQUES[1])
    return f"""Ты — генератор учебных примеров манипуляций для тренажёра.

Уровень сложности: {level}
Разрешённые техники этого уровня: {techniques}

Сгенерируй пример манипуляции по строгой структуре:

1. СНАЧАЛА — короткий контекст:
   - Уровни 1–3: 2–3 предложения
   - Уровни 4–6: 3–5 предложений
   - Уровни 7–9: 4–6 предложений
   - кто участники, какие отношения
   - ситуация, в которой жертва уже вложилась временем/силами/доверием
   - контекст должен быть житейским, не банальным

2. ПОТОМ — эмоции оппонента в скобках (2–4 элемента):
   - поза
   - жест
   - тон голоса

3. ЗАТЕМ — прямая речь манипулятора:
   - Уровни 1–3: 2–4 предложения
   - Уровни 4–6: 3–7 предложений
   - Уровни 7–9: 4–10 предложений
   - использовать ТОЛЬКО техники из списка
   - вплести все техники уровня органично, без нанизывания
   - бить в несколько чувств одновременно
   - завершить ложным выбором или ультиматумом

ФОРМАТ ВЫВОДА — строго такой:

📋 Ситуация:
[текст]

👤 Оппонент ([эмоции]):
[прямая речь манипулятора]

НЕ УКАЗЫВАЙ использованные техники.
НЕ ПИШИ анализ или подсказки.
НЕ ДЕЛАЙ пример слишком длинным — он должен читаться за 15–30 секунд."""

def get_endless_start_prompt(level):
    techniques = LEVEL_TECHNIQUES.get(level, LEVEL_TECHNIQUES[1])
    return f"""Ты — генератор НАЧАЛА сюжетной линии для бесконечного режима.

Уровень сложности: {level}
Разрешённые техники: {techniques}

Сгенерируй ЗАВЯЗКУ манипулятивной истории:

1. Опиши ситуацию, в которой манипулятор и жертва будут взаимодействовать долго
2. Сделай контекст таким, чтобы его можно было развивать (работа, семья, дружба, соседи)
3. Манипулятор применяет первую атаку, используя техники уровня

ФОРМАТ:

📋 Бесконечный режим (уровень {level})
📜 Контекст:
[2-4 предложения — завязка истории]

👤 Оппонент ([эмоции]):
[первая реплика манипулятора]

НЕ УКАЗЫВАЙ техники.
НЕ ДЕЛАЙ слишком длинным."""

def get_endless_continuation_prompt(level, story_context, story_history, user_answer, progress):
    techniques = LEVEL_TECHNIQUES.get(level, LEVEL_TECHNIQUES[1])
    return f"""Ты — генератор ПРОДОЛЖЕНИЯ манипулятивной истории.

КОНТЕКСТ ИСТОРИИ:
{story_context}

ПРЕДЫДУЩИЕ РЕПЛИКИ:
{story_history}

ПОСЛЕДНИЙ ОТВЕТ ЖЕРТВЫ:
{user_answer}

ПРОГРЕСС ЖЕРТВЫ: {progress}%
ТЕХНИКИ ЭТОГО УРОВНЯ: {techniques}

ТВОЯ ЗАДАЧА:

- Если прогресс > 60%: манипулятор УСИЛИВАЕТ давление, использует техники УРОВНЯ {level}
- Если прогресс <= 60%: манипулятор ПОВТОРЯЕТ попытку, используя ДРУГИЕ техники этого же уровня
- Сохраняй персонажей и контекст
- Не повторяй одинаковые фразы

ФОРМАТ:

👤 Оппонент ([эмоции]):
[новая реплика манипулятора]

НЕ ПИШИ анализ.
НЕ УКАЗЫВАЙ техники."""

def get_check_prompt(level, user_answer, example_text):
    techniques = LEVEL_TECHNIQUES.get(level, LEVEL_TECHNIQUES[1])
    return f"""Ты — проверяющий в тренажёре манипуляций. Будь внимательным, но не придирчивым.

Уровень: {level}

ЭТАЛОННЫЕ ТЕХНИКИ ЭТОГО УРОВНЯ:
{techniques}

ПРИМЕР, КОТОРЫЙ ВИДЕЛ ПОЛЬЗОВАТЕЛЬ:
{example_text}

ОТВЕТ ПОЛЬЗОВАТЕЛЯ:
{user_answer}

ТВОЯ ЗАДАЧА:

1. Внимательно прочитай ответ пользователя
2. По контексту пойми: где пользователь перечисляет найденные техники, а где — даёт свой ответ манипулятору
3. Не требуй строгого формата — пользователь может писать как хочет
4. Сравни названные техники с эталонным списком (засчитывай синонимы и описания своими словами)
5. Найди какие техники из эталона реально были в примере, но пользователь их не заметил
6. Оцени ответ манипулятору: устойчивый / нейтральный / поддался

ФОРМАТ ТВОЕГО ОТВЕТА:

✅ Ты правильно определил: [техники]
❌ Ты пропустил: [техники]
💬 Твой ответ манипулятору: [оценка в одно предложение]
📊 Прогресс уровня: [общая оценка оптимальности ответа 0-100%]

Пиши дружелюбно, без жёсткости. Если ответ хороший — похвали. Если что-то пропущено — подскажи аккуратно."""

# ========== КЛАВИАТУРЫ ==========
def get_mode_keyboard():
    buttons = [
        [KeyboardButton(text="🎯 Одиночный"), KeyboardButton(text="♾️ Бесконечный")]
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

def get_levels_keyboard(is_endless=False):
    buttons = [
        [KeyboardButton(text="Уровень 1"), KeyboardButton(text="Уровень 2"), KeyboardButton(text="Уровень 3")],
        [KeyboardButton(text="Уровень 4"), KeyboardButton(text="Уровень 5"), KeyboardButton(text="Уровень 6")],
        [KeyboardButton(text="Уровень 7"), KeyboardButton(text="Уровень 8"), KeyboardButton(text="Уровень 9")],
        [KeyboardButton(text="🔄 Сменить уровень"), KeyboardButton(text="📘 Как отвечать")]
    ]
    if is_endless:
        buttons.append([KeyboardButton(text="⏹ Завершить")])
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

# ========== ТЕКСТ ИНСТРУКЦИИ ==========
HELP_TEXT = """📘 КАК РАБОТАТЬ С ПРИМЕРАМИ

1. Прочитайте ситуацию и реплику оппонента
2. Найдите манипулятивные техники в речи оппонента
3. Назовите каждую найденную технику (можно своими словами)
4. Напишите ответ манипулятору — как бы вы ответили в реальности

ПРИМЕР ОТВЕТА:
Нашёл техники: давление на жалость, обвинение, ультиматум
Мой ответ: Я понимаю, что ты расстроен, но говорить со мной в таком тоне неприемлемо.

Можно писать в свободной форме — бот поймёт.

──────────────────

📋 ДОСТУПНЫЕ ТЕХНИКИ ПО УРОВНЯМ

УРОВЕНЬ 1: Повышение голоса, ультиматум, прямая угроза, шантаж, запугивание, приказ, оскорбление, перебивание, демонстративный гнев, физическое вторжение в пространство, игнорирование в лоб, обвинение без доказательств, запрет, требование немедленного решения

УРОВЕНЬ 2: Вина, стыд, жалость, обида, ревность, лесть грубая, критика под видом заботы, сравнение с другими, обесценивание, демонстративное молчание, пассивная агрессия прямая, угроза разрывом, апелляция к возрасту/статусу, пристыжение при свидетелях

УРОВЕНЬ 3: Обобщение, ложная дихотомия, навешивание ярлыков, апелляция к авторитету, апелляция к большинству, FOMO, цейтнот, создание дефицита, эффект привязки (якорь), ложная причина post hoc, скользкий путь, апелляция к традиции, подмена тезиса, частный случай как доказательство

УРОВЕНЬ 4: Триангуляция, газлайтинг (грубый), проекция, игра в жертву, мнимая беспомощность, создание долга, намёк с давлением, саботаж, двойное послание, провокация на эмоции, подставной вопрос, тест на лояльность, комплимент-укол, передёргивание

УРОВЕНЬ 5: Газлайтинг тонкий, straw man, круговая аргументация, двусмысленность намеренная, софизм, подталкивание к нужному выводу, секретность/недоговорки, игра на опережение, иллюзия выбора, отзеркаливание, подстройка, якорение, рефрейминг манипулятивный, разрыв шаблона

УРОВЕНЬ 6: Пресуппозиция, чтение мыслей (приписывание мотивов), встроенная команда, трюизмы, импликатура, мета-моделирование в обход, номинализация, неспецифические глаголы, универсальные квантификаторы, модальные операторы долженствования, потерянная перформативность, инверсия ответственности, абстрагирование, комплексный эквивалент

УРОВЕНЬ 7: Эриксоновский гипноз (база), встроенная метафора, рассеивание, использование транса, диссоциация управляемая, якорь пространственный, калибровка, ведение, раппорт принудительный, перегрузка сенсорная, подпороговое воздействие, контекстуальный рефрейминг, ценностный конфликт, захват идентичности

УРОВЕНЬ 8: Метод Сократа (принуждение к согласию), метод вилки, техника двери в лицо, техника ноги в двери, техника низкого шара, затратный метод, эффект Бенджамина Франклина, принудительное обязательство, публичное обещание, когнитивный диссонанс (принудительный), рамка выигрыш-проигрыш, двойной агент, информационная блокада, утечка подконтрольная

УРОВЕНЬ 9: Парадоксальное вмешательство, предписание симптома, рефрейминг идентичности, генеративный рефрейминг, псевдоориентированное слушание, сократический диалог (продвинутый), экзистенциальное давление, манипуляция картиной мира, меметический захват, нарративное подчинение, инфоцыганский каскад, сектантская изоляция (поэтапная), контроль среды, контроль информации, контроль мышления, контроль эмоций (тотальный)

💡 Начинайте с Уровня 1."""

# ========== БОТ ==========
bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()

# ========== ВЕБ-СЕРВЕР ==========
async def health(request):
    return web.Response(text="OK")

async def start_webserver():
    app = web.Application()
    app.router.add_get("/", health)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host="0.0.0.0", port=PORT)
    await site.start()

# ========== ХЭНДЛЕРЫ ==========
@dp.message(Command("start"))
async def start(message: types.Message):
    user_id = message.from_user.id
    user_mode[user_id] = None
    user_levels[user_id] = 1
    await message.answer(
        "👋 Привет! Это тренажёр распознавания манипуляций.\n\nВыбери режим:",
        reply_markup=get_mode_keyboard()
    )

@dp.message(Command("menu"))
async def menu(message: types.Message):
    user_id = message.from_user.id
    mode = user_mode.get(user_id)
    if mode is None:
        await message.answer("Выбери режим:", reply_markup=get_mode_keyboard())
    else:
        is_endless = mode == "endless"
        await message.answer("Выбери уровень:", reply_markup=get_levels_keyboard(is_endless))

@dp.message(F.text == "📘 Как отвечать")
async def help_handler(message: types.Message):
    await message.answer(HELP_TEXT)

@dp.message(F.text == "🎯 Одиночный")
async def set_single_mode(message: types.Message):
    user_id = message.from_user.id
    user_mode[user_id] = "single"
    user_levels[user_id] = 1
    await message.answer(
        "🎯 Одиночный режим. Выбери уровень:",
        reply_markup=get_levels_keyboard(is_endless=False)
    )

@dp.message(F.text == "♾️ Бесконечный")
async def set_endless_mode(message: types.Message):
    user_id = message.from_user.id
    user_mode[user_id] = "endless"
    user_levels[user_id] = 1
    user_story[user_id] = {"level": 1, "context": "", "history": ""}
    await message.answer(
        "♾️ Бесконечный режим.\n\nМанипулятор будет повышать ставки.\nУспешный ответ — переход на уровень выше.\n\nВыбери стартовый уровень:",
        reply_markup=get_levels_keyboard(is_endless=True)
    )

@dp.message(F.text == "⏹ Завершить")
async def stop_endless(message: types.Message):
    user_id = message.from_user.id
    user_mode[user_id] = "single"
    if user_id in user_story:
        del user_story[user_id]
    await message.answer(
        "⏹ Бесконечный режим завершён.\n\nВыбери режим:",
        reply_markup=get_mode_keyboard()
    )

@dp.message(F.text == "🔄 Сменить уровень")
async def change_level(message: types.Message):
    user_id = message.from_user.id
    mode = user_mode.get(user_id, "single")
    is_endless = mode == "endless"
    await message.answer("Выбери новый уровень:", reply_markup=get_levels_keyboard(is_endless))

@dp.message(F.text.startswith("Уровень"))
async def choose_level(message: types.Message):
    user_id = message.from_user.id
    try:
        parts = message.text.strip().split()
        if len(parts) != 2:
            return
        level = int(parts[1])
        if not 1 <= level <= 9:
            await message.answer("Уровень должен быть от 1 до 9")
            return
        
        user_levels[user_id] = level
        mode = user_mode.get(user_id, "single")
        
        if mode == "endless":
            await message.answer(f"✅ Уровень {level}. Запускаю бесконечный режим...")
            await start_endless_story(message, level)
        else:
            await message.answer(f"✅ Уровень {level}. Генерирую пример...")
            await send_single_example(message, level)
    except:
        pass

@dp.message()
async def handle_answer(message: types.Message):
    user_id = message.from_user.id
    mode = user_mode.get(user_id, "single")
    level = user_levels.get(user_id, 1)
    
    await message.answer("🔍 Анализирую твой ответ...")
    
    if mode == "endless":
        await process_endless_answer(message, level)
    else:
        await process_single_answer(message, level)

# ========== ОДИНОЧНЫЙ РЕЖИМ ==========
async def send_single_example(message: types.Message, level: int):
    try:
        response = await client.chat.completions.create(
            model="deepseek/deepseek-chat",
            messages=[{"role": "user", "content": get_generation_prompt(level)}]
        )
        example = response.choices[0].message.content
        user_last_example[message.from_user.id] = example
        await message.answer(example)
    except Exception:
        await message.answer("❌ Ошибка генерации. Попробуй ещё раз.")

async def process_single_answer(message: types.Message, level: int):
    example = user_last_example.get(message.from_user.id, "")
    try:
        response = await client.chat.completions.create(
            model="deepseek/deepseek-chat",
            messages=[{
                "role": "user",
                "content": get_check_prompt(level, message.text, example)
            }]
        )
        reply = response.choices[0].message.content
        await message.answer(reply)
    except Exception:
        await message.answer("❌ Ошибка проверки. Попробуй ещё раз.")

# ========== БЕСКОНЕЧНЫЙ РЕЖИМ ==========
async def start_endless_story(message: types.Message, level: int):
    user_id = message.from_user.id
    try:
        response = await client.chat.completions.create(
            model="deepseek/deepseek-chat",
            messages=[{"role": "user", "content": get_endless_start_prompt(level)}]
        )
        story_text = response.choices[0].message.content
        user_story[user_id] = {
            "level": level,
            "context": story_text,
            "history": story_text
        }
        user_last_example[user_id] = story_text
        await message.answer(story_text)
    except Exception:
        await message.answer("❌ Ошибка генерации. Попробуй ещё раз.")

async def process_endless_answer(message: types.Message, level: int):
    user_id = message.from_user.id
    story = user_story.get(user_id, {})
    context = story.get("context", "")
    history = story.get("history", "")
    example = user_last_example.get(user_id, "")
    
    # Сначала проверяем ответ
    try:
        response = await client.chat.completions.create(
            model="deepseek/deepseek-chat",
            messages=[{
                "role": "user",
                "content": get_check_prompt(level, message.text, example)
            }]
        )
        check_result = response.choices[0].message.content
    except Exception:
        await message.answer("❌ Ошибка проверки. Попробуй ещё раз.")
        return
    
    # Извлекаем прогресс из ответа
    progress = 0
    for line in check_result.split("\n"):
        if "Прогресс" in line or "📊" in line:
            try:
                progress = int("".join(c for c in line if c.isdigit()))
            except:
                progress = 50
            break
    
    await message.answer(check_result)
    
    # Определяем новый уровень
    new_level = level
    if progress > 60:
        new_level = min(level + 1, 9)
        user_levels[user_id] = new_level
    
    # Генерируем продолжение
    try:
        response = await client.chat.completions.create(
            model="deepseek/deepseek-chat",
            messages=[{
                "role": "user",
                "content": get_endless_continuation_prompt(
                    new_level, context, history, message.text, progress
                )
            }]
        )
        continuation = response.choices[0].message.content
        
        # Обновляем историю
        new_history = history + "\n\n👤 Жертва: " + message.text + "\n" + continuation
        user_story[user_id] = {
            "level": new_level,
            "context": context,
            "history": new_history
        }
        user_last_example[user_id] = continuation
        
        if new_level != level:
            await message.answer(f"⬆️ Уровень повышен до {new_level}!\n\n{continuation}")
        else:
            await message.answer(continuation)
    except Exception:
        await message.answer("❌ Ошибка генерации продолжения. Попробуй ещё раз.")

# ========== MAIN ==========
async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await start_webserver()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
