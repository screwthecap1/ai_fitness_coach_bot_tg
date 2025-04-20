from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler
from joblib import load
import pandas as pd
from dotenv import load_dotenv
import os
from database import create_table, save_user, get_user, delete_user, update_steps, update_plan
import requests
import random

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")


# Замените на свой API ключ OpenRouter
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# Загрузка энкодеров и моделей
le_gender_s, le_goal_s, le_level_s, le_location_s = load("model_training/encoders.pkl")
schedule_models = load("model_training/model.pkl")

AGE, GENDER, HEIGHT, WEIGHT, GOAL, LEVEL, LOCATION, FIT_SYNC_CHOICE, MANUAL_STEPS = range(9)
GPT_CHAT = 9


async def show_main_menu(update: Update):
    keyboard = [[
        KeyboardButton("📝 Обновить анкету"), KeyboardButton("📅 Мой план")
    ], [
        KeyboardButton("💬 Задать вопрос"), KeyboardButton("🔗 Google Fit")
    ], [
        KeyboardButton("🔁 Новый план"), KeyboardButton("👤 Моя анкета")  # Новая кнопка
    ]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text("Выбери действие:", reply_markup=reply_markup)

# TODO: Необходимо удалить неиспользуемую переменную
async def show_main_menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await show_main_menu(update)
    return ConversationHandler.END

async def handle_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    # ✅ Если GPT активен — перенаправляем сразу туда
    if context.user_data.get("chat_active"):
        return await handle_gpt_message(update, context)

    elif text == "📝 Обновить анкету":
        await update.message.reply_text("👉 Введи команду /update, чтобы обновить анкету.")
        return ConversationHandler.END

    # Если это ответ на выбор "Да/Нет" по Google Fit
    if context.user_data.get("expecting_fit_sync"):
        return await get_fit_sync_choice(update, context)

    elif text == "📅 Мой план":
        await profile(update, context)
        return ConversationHandler.END

    elif text == "👤 Моя анкета":
        await show_user_profile(update, context)
        return ConversationHandler.END


    elif text == "💬 Задать вопрос":
        context.user_data["chat_active"] = True  # <- Ставим флаг
        return await start_gpt_chat(update, context)

    elif text == "🔁 Новый план":
        return await regenerate_plan(update, context)

    elif text == "🔗 Google Fit":
        return await syncfit(update, context)

    else:
        await update.message.reply_text("Неизвестная команда. Используй меню кнопок.")
        return ConversationHandler.END

WELCOME_TEXT = (
    "*Привет, я Климентий Миньюонович — твой ИИ-фитнес тренер!* 🤖💪\n\n"
    "Помогу тебе:\n"
    "✅ Составить персональный план тренировок\n"
    "✅ Учесть твои цели, уровень и образ жизни\n"
    "✅ Общаться и отвечать на твои вопросы\n\n"
)

async def start_survey(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    text = update.message.text
    is_update = text in ["/update", "📝 Обновить анкету"]

    with open("img.png", "rb") as photo:
        await update.message.reply_photo(
            photo=photo,
            caption=WELCOME_TEXT,
            parse_mode="Markdown"
        )

    user = get_user(user_id)

    if user and not is_update:
        profile_text = f"""👋 Привет снова, {update.effective_user.first_name}!
📝 Твоя анкета:
👤 Возраст: {user[1]} лет
🚻 Пол: {user[2]}
📏 Рост: {user[4]} см
⚖️ Вес: {user[3]} кг
🎯 Цель: {user[5]}
🏋️ Уровень: {user[6]}
📍 Место: {user[7]}
👣 Шагов в день: {user[8] if user[8] else 'не указано'}"""
        await update.message.reply_text(profile_text)
        await show_main_menu(update)
        return ConversationHandler.END

    if is_update:
        delete_user(user_id)
        context.user_data.clear()
        await update.message.reply_text("🔁 Анкета сброшена. Давай заполним заново!")

    await update.message.reply_text("👉 Сколько тебе лет?")
    return AGE



def add_noise_to_data(data):
    noisy_data = data.copy()

    noisy_data["age"] += random.choice([-1, 0, 1])
    noisy_data["weight"] += random.choice([-1, 0, 1])
    noisy_data["height"] += random.choice([-1, 0, 1])
    noisy_data["steps"] = int(noisy_data["steps"] * random.uniform(0.95, 1.05))

    return noisy_data

# Возраст
async def get_age(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["age"] = int(update.message.text)
    await update.message.reply_text("Твой пол? (М/Ж)")
    return GENDER

async def get_gender(update: Update, context: ContextTypes.DEFAULT_TYPE):
    g = update.message.text.upper()
    context.user_data["gender"] = "M" if g == "М" else "F"
    await update.message.reply_text("Твой рост (в см)?")
    return HEIGHT

async def get_height(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["height"] = int(update.message.text)
    await update.message.reply_text("Твой вес (в кг)?")
    return WEIGHT

async def get_weight(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["weight"] = int(update.message.text)
    reply_keyboard = [["Похудение", "Масса", "Поддержание"]]
    await update.message.reply_text("Какая у тебя цель?", reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True))
    return GOAL

async def get_goal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["goal"] = update.message.text
    reply_keyboard = [["Начинающий", "Средний", "Продвинутый"]]
    await update.message.reply_text("Твой уровень подготовки?", reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True))
    return LEVEL

def predict_week_schedule(data):
    features = pd.DataFrame([{
        "age": int(data["age"]),
        "weight": int(data["weight"]),
        "height": int(data["height"]),
        "gender_enc": le_gender_s.transform([data["gender"]])[0],
        "goal_enc": le_goal_s.transform([data["goal"]])[0],
        "level_enc": le_level_s.transform([data["level"]])[0],
        "steps": int(data.get("steps", 6000)),
        "location_enc": le_location_s.transform([data.get("location", "Дом")])[0],
    }])

    days = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    day_keys = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]

    schedule = {}
    for day, key in zip(days, day_keys):
        model, encoder = schedule_models[key]
        y_pred = model.predict(features)[0]
        schedule[day] = encoder.inverse_transform([y_pred])[0]

    return schedule


# Уровень
async def get_level(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["level"] = update.message.text
    reply_keyboard = [["Зал", "Дом", "Улица"]]
    await update.message.reply_text("🏠 Где ты хочешь заниматься?", reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True))
    return LOCATION

async def get_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    location_input = update.message.text.lower()
    mapping = {
        "зал": "Зал",
        "дом": "Дом",
        "улица": "Улица"
    }

    if location_input not in mapping:
        await update.message.reply_text("❗ Пожалуйста, выбери вариант из предложенных: Зал, Дом или Улица.")
        return LOCATION

    context.user_data["location"] = mapping[location_input]
    context.user_data["expecting_fit_sync"] = True

    reply_keyboard = [["Да", "Нет"]]
    await update.message.reply_text(
        "🔗 Хочешь подключить Google Fit для автоматического определения шагов?",
        reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True)
    )
    return FIT_SYNC_CHOICE


async def get_fit_sync_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    answer = update.message.text.lower()
    context.user_data.pop("expecting_fit_sync", None)

    if answer == "да":
        await update.message.reply_text("Открываю окно авторизации Google Fit...")
        try:
            from google_fit import get_credentials, get_steps_data
            token = get_credentials()
            steps_list = get_steps_data(token)
            avg_steps = sum(steps_list) // len(steps_list)
            context.user_data["steps"] = avg_steps
            await update.message.reply_text(f"✅ Успешно! Среднее: {avg_steps} шагов в день")
        except Exception as e:
            await update.message.reply_text(f"⚠️ Ошибка подключения: {e}\nВведи количество шагов вручную:")
            return MANUAL_STEPS
    else:
        await update.message.reply_text("Сколько в среднем ты проходишь шагов в день?")
        return MANUAL_STEPS

    return await finalize_profile(update, context)

async def get_manual_steps(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        context.user_data["steps"] = int(update.message.text)
    except ValueError:
        await update.message.reply_text("❗ Введи только число — среднее количество шагов в день:")
        return MANUAL_STEPS
    return await finalize_profile(update, context)

async def finalize_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    save_user(user_id, context.user_data)

    steps = context.user_data.get("steps", 6000)

    profile_text = f"""📝 Твоя анкета:
👤 Возраст: {context.user_data['age']} лет
🚻 Пол: {context.user_data['gender']}
📏 Рост: {context.user_data['height']} см
⚖️ Вес: {context.user_data['weight']} кг
🎯 Цель: {context.user_data['goal']}
🏋️ Уровень: {context.user_data['level']}
📍 Место тренировки: {context.user_data['location']}
👣 Шагов в день: {steps}
"""
    await update.message.reply_text(profile_text)

    schedule = predict_week_schedule(context.user_data)

    plan_text = "\n📅 Расписание на неделю от AI:\n"
    for day, activity in schedule.items():
        plan_text += f"{day}: {activity}\n"

    await update.message.reply_text(plan_text)
    await show_main_menu(update)
    return ConversationHandler.END

# TODO: Необходимо удалить неиспользуемую переменную
async def profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    user = get_user(user_id)

    if user is None:
        await update.message.reply_text("🙁 Профиль не найден. Пройди анкету командой /start.")
        return

    # показываем сохранённый план, если он есть
    saved_plan = user[9]
    if saved_plan:
        await update.message.reply_text("📅 Сохраняённый план:\n" + saved_plan)

    # генерируем актуальное расписание всегда
    user_data_loaded = {
        "age": user[1],
        "gender": user[2],
        "weight": user[3],
        "height": user[4],
        "goal": user[5],
        "level": user[6],
        "location": user[7],
        "steps": user[8]
    }

    schedule = predict_week_schedule(user_data_loaded)

    plan_text = f"\n📅 Актуальное расписание от AI:\n"
    for day, activity in schedule.items():
        plan_text += f"{day}: {activity}\n"

    await update.message.reply_text(plan_text)

# TODO: Необходимо удалить неиспользуемую переменную
async def show_user_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    user = get_user(user_id)

    if not user:
        await update.message.reply_text("🙁 Анкета не найдена. Пройди опрос с помощью /start.")
        return

    profile_text = f"""📄 *Твоя анкета:*
👤 Возраст: {user[1]} лет
🚻 Пол: {user[2]}
📏 Рост: {user[4]} см
⚖️ Вес: {user[3]} кг
🎯 Цель: {user[5]}
🏋️ Уровень: {user[6]}
📍 Место: {user[7]}
👣 Шагов в день: {user[8] if user[8] else 'не указано'}
"""
    await update.message.reply_text(profile_text, parse_mode="Markdown")

# TODO: Необходимо удалить неиспользуемую переменную
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Анкета отменена. Введи /start, чтобы начать заново.")
    return ConversationHandler.END

# TODO: Необходимо удалить неиспользуемую переменную
async def syncfit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔗 Подключаюсь к Google Fit...")

    try:
        from google_fit import get_credentials, get_steps_data

        token = get_credentials()
        steps_list = get_steps_data(token)

        if not steps_list:
            await update.message.reply_text("😕 Не удалось получить данные о шагах.")
            return

        total_steps = sum(steps_list)
        avg_steps = total_steps // len(steps_list)

        # Сохраняем в БД
        user_id = update.message.from_user.id
        update_steps(user_id, avg_steps)

        await update.message.reply_text(
            f"✅ Google Fit подключен!\n👣 Среднее за 7 дней: {avg_steps} шагов\nТы готов к тренировке — введи /start"
        )

    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка при подключении Google Fit: {e}")

# Включение GPT-чата
async def start_gpt_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["chat_history"] = [
        {"role": "system", "content": "Ты — персональный фитнес-тренер. Отвечай чётко, понятно и дружелюбно."}
    ]
    reply_markup = ReplyKeyboardMarkup([["↩️ Выйти из чата"]], resize_keyboard=True)
    await update.message.reply_text("💬 GPT-чат активирован! Напиши вопрос или нажми «↩️ Выйти из чата».", reply_markup=reply_markup)
    return GPT_CHAT

# Обработка каждого сообщения
async def handle_gpt_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_message = update.message.text

    # 👋 Выйти из GPT-чата можно, если написать "выход"
    if user_message.lower() in ["выход", "выйти", "назад", "↩️ выйти из чата"]:
        context.user_data["chat_active"] = False
        await update.message.reply_text("👋 Выход из GPT-чата. Возвращаю главное меню.")
        await show_main_menu(update)
        return ConversationHandler.END

    context.user_data["chat_history"].append({"role": "user", "content": user_message})
    await update.message.reply_text("🤖 Думаю...")

    try:
        headers = {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json"
        }

        data = {
            "model": "mistralai/mistral-7b-instruct",  # или "openai/gpt-3.5-turbo" если хочешь
            "messages": context.user_data["chat_history"]
        }

        response = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=data)
        result = response.json()

        if "choices" in result and result["choices"]:
            answer = result["choices"][0]["message"]["content"]
            context.user_data["chat_history"].append({"role": "assistant", "content": answer})
            await update.message.reply_text(answer)
        else:
            await update.message.reply_text("⚠️ Не удалось получить ответ. Попробуй чуть позже.")

    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {e}")

# TODO: Необходимо удалить неиспользуемую переменную
async def regenerate_plan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    user = get_user(user_id)

    if not user:
        await update.message.reply_text("🙁 Профиль не найден. Пройди анкету сначала с помощью /start.")
        return ConversationHandler.END

    user_data_loaded = {
        "age": user[1],
        "gender": user[2],
        "weight": user[3],
        "height": user[4],
        "goal": user[5],
        "level": user[6],
        "location": user[7],
        "steps": user[8]
    }

    noisy_input = add_noise_to_data(user_data_loaded)
    schedule = predict_week_schedule(noisy_input)

    plan_text = "🔁 Новый вариант плана от AI:\n"
    for day, activity in schedule.items():
        plan_text += f"{day}: {activity}\n"

    update_plan(user_id, plan_text)  # <--- Сохраняем!

    await update.message.reply_text(plan_text)
    return ConversationHandler.END



# Запуск бота
if __name__ == '__main__':
    create_table()
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    # 🧠 ConversationHandler: анкета + GPT-чат
    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("start", start_survey),
            CommandHandler("update", start_survey),
            CommandHandler("gptchat", start_gpt_chat)
        ],
        states={
            AGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_age)],
            GENDER: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_gender)],
            HEIGHT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_height)],
            WEIGHT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_weight)],
            GOAL: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_goal)],
            LEVEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_level)],
            LOCATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_location)],
            FIT_SYNC_CHOICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_fit_sync_choice)],
            MANUAL_STEPS: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_manual_steps)],
            GPT_CHAT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_gpt_message)]
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True
    )

    app.add_handler(conv_handler)  # ВАЖНО: первым!
    app.add_handler(CommandHandler("menu", show_main_menu_command))
    app.add_handler(CommandHandler("profile", profile))
    app.add_handler(CommandHandler("syncfit", syncfit))
    app.add_handler(CommandHandler("syncfit", syncfit))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_menu))

    print("Бот запущен.")
    app.run_polling()
