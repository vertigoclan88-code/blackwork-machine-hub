import os, sys, asyncio, logging, threading, sqlite3, json
from datetime import datetime
from dotenv import load_dotenv
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "8695239375:AAHFzw7kbXJp2vQ40Lam2XcpvMbH7BE1Tp4")
ADMIN_ID = os.getenv("ADMIN_ID", "7875731370")
PORT = int(os.getenv("PORT", "10000"))
WEBAPP_URL = os.getenv("WEBAPP_URL", "https://blackwork-machine-hub.onrender.com")

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from flask import Flask, render_template, request, jsonify

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
logger = logging.getLogger(__name__)

app = Flask(__name__)
dp = Dispatcher()

user_lang = {}

def init_db():
    conn = sqlite3.connect("blackwork_hub.db")
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS catalog
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  name TEXT, description TEXT, price TEXT,
                  category TEXT, is_available BOOLEAN DEFAULT 1)""")
    c.execute("""CREATE TABLE IF NOT EXISTS requests
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  name TEXT, phone TEXT, model TEXT,
                  description TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
    c.execute("SELECT COUNT(*) FROM catalog")
    if c.fetchone()[0] == 0:
        items = [
            ("🖤 VOID REAPER", "Макс. плотность закраса\nХод 4.2 мм • Большие площади", "от $300/мес", "BLACKOUT", 1),
            ("⚡ SHADOW WOLF", "Баланс скорости и плотности\nХод 3.8 мм • Универсальный", "от $350/мес", "BLACKWORK", 1),
            ("🎯 DARK KRISHNA X", "Точный контроль\nХод 3.5 мм • Dark Lettering", "от $400/мес", "LETTERING", 1),
        ]
        c.executemany("INSERT INTO catalog VALUES (NULL,?,?,?,?,?)", items)
    conn.commit()
    conn.close()

init_db()

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/catalog")
def catalog():
    return render_template("catalog.html")

@app.route("/api/catalog")
def api_catalog():
    conn = sqlite3.connect("blackwork_hub.db")
    c = conn.cursor()
    c.execute("SELECT * FROM catalog")
    items = [{"id": r[0], "name": r[1], "description": r[2], 
              "price": r[3], "category": r[4], "is_available": bool(r[5])} for r in c.fetchall()]
    conn.close()
    return jsonify(items)

@app.route("/api/submit_request", methods=["POST"])
def submit_request():
    data = request.json
    conn = sqlite3.connect("blackwork_hub.db")
    c = conn.cursor()
    c.execute("INSERT INTO requests (name, phone, model, description) VALUES (?,?,?,?)",
              (data.get("name",""), data.get("phone",""), data.get("model",""), data.get("description","")))
    conn.commit()
    conn.close()
    return jsonify({"success": True})

TEXTS = {
    "ru": {
        "start": "🖤 <b>КАСТОМНЫЕ МАШИНКИ ДЛЯ BLACK WORK — В АРЕНДУ</b>\n\n<b>Машинка, которая делает Black Work — настоящим Black Work.</b>\n\nПлотная, жёсткая заливка с одного прохода. Без пятен, без просветов, без перепрохода по коже.\n\nМы не продаём серийные машинки «для всего». Мы собираем их вручную под одну задачу — <b>Dark Lettering и Black Work</b>, где важна не скорость, а <b>плотность и стабильность хода иглы</b>.\n\n3 кастомных модели. Беспроводные. Под любую руку и любой стиль.\n\n▔▔▔▔▔▔▔▔▔▔▔▔▔▔\n💵 <b>Аренда от $300/мес</b>\n🔧 <b>Настройка персонально под мастера</b>\n📩 <b>Доставка по всему миру</b>",
        "why": "🖤 <b>ПОЧЕМУ НАШИ МАШИНКИ</b>\n\n<b>Не доработанный Китай. Инженерное решение под Black Work.</b>\n\n🔹 <b>Ход иглы заточен под плотность</b>\nСтандартные машинки — универсальный удар. Наша геометрия — максимальное давление пигмента за минимум проходов.\n\n🔹 <b>Стабильность на длинных сессиях</b>\nТестируем каждую машинку 3+ часа непрерывной заливки.\n\n🔹 <b>Полностью беспроводные</b>\nНикаких проводов — свобода движения.\n\n🔹 <b>Персональная настройка под руку</b>\nКалибруем ход, отдачу и баланс под твою технику.\n\n🔹 <b>Made by hand</b>\n3 модели — 3 характера хода.",
        "rent": "💰 <b>АРЕНДА ВМЕСТО ПОКУПКИ</b>\n\n<b>Хорошая машинка = 2–3 сеанса. Не у всех есть сумма сразу.</b>\n\n💵 Сеанс: $150–200\n💵 Аренда: <b>от $300/мес</b>\n\nОкупаемость: <b>1,5–2 сеанса</b> → чистая прибыль.\n\n✅ Без крупных вложений\n✅ Не подошло — заменим\n✅ Машинка всегда обслужена\n✅ Порог входа снижен",
        "support": "🛠 <b>ПОДДЕРЖКА 24/7</b>\n\n<b>Не продаём железо и не исчезаем.</b>\n\nСборщик на связи лично с первого дня:\n\n▸ Настройка под твою руку\n▸ Помощь на первых сессиях\n▸ Диагностика и советы по уходу\n▸ Замена/доработка при необходимости\n▸ Обучение Black Work и Dark Lettering\n\n📩 Доставка по всему миру",
        "for_whom": "🎯 <b>КОМУ ПОДХОДИТ</b>\n\n✔️ Опытным — переход в Black Work без риска\n✔️ Начинающим — проф. инструмент без бюджета\n✔️ Студиям — расширение услуг\n✔️ Недовольным обычной заливкой",
        "btn_model": "🖤 ВЫБРАТЬ МОДЕЛЬ",
        "btn_rent": "💰 АРЕНДА",
        "btn_why": "🔧 ПОЧЕМУ МЫ",
        "btn_support": "🛠 ПОДДЕРЖКА",
        "btn_whom": "🎯 КОМУ",
        "btn_contact": "📩 МАСТЕР",
        "btn_ru": "🇷🇺 RU",
        "btn_en": "🇬🇧 EN",
        "btn_back": "« НАЗАД",
    },
    "en": {
        "start": "🖤 <b>CUSTOM BLACKWORK MACHINES FOR RENT</b>\n\n<b>The machine that makes Black Work — real Black Work.</b>\n\nDense packing in one pass. No spots, no gaps, no re-working.\n\nHand-built for <b>Dark Lettering & Black Work</b> — density and stability over speed.\n\n3 custom models. Wireless. For any hand, any style.\n\n▔▔▔▔▔▔▔▔▔▔▔▔▔▔\n💵 <b>Rent from $300/mo</b>\n🔧 <b>Personal calibration included</b>\n📩 <b>Worldwide shipping</b>",
        "why": "🖤 <b>WHY OUR MACHINES</b>\n\n<b>Not modified China. Engineered for Black Work.</b>\n\n🔹 <b>Stroke tuned for density</b>\nMax pigment pressure, minimum passes.\n\n🔹 <b>Stable on long sessions</b>\n3+ hour tested before shipping.\n\n🔹 <b>Fully wireless</b>\nZero cords, total freedom.\n\n🔹 <b>Tuned to YOUR hand</b>\nStroke, feedback, balance — calibrated personally.\n\n🔹 <b>Made by hand</b>\n3 models, 3 characters.",
        "rent": "💰 <b>RENT VS BUY</b>\n\n<b>A good machine = 2–3 sessions. Not everyone has that upfront.</b>\n\n💵 Session: $150–200\n💵 Rent: <b>from $300/mo</b>\n\nPayback: <b>1.5–2 sessions</b> → pure profit.\n\n✅ No big upfront cost\n✅ Not right? Swap it\n✅ Always maintained\n✅ Entry barrier lowered",
        "support": "🛠 <b>24/7 SUPPORT</b>\n\n<b>We don't sell hardware and vanish.</b>\n\nBuilder online personally from day one:\n\n▸ Hand tuning\n▸ First session help\n▸ Remote diagnostics\n▸ Replacement if needed\n▸ Black Work training\n\n📩 Worldwide shipping",
        "for_whom": "🎯 <b>WHO IS THIS FOR</b>\n\n✔️ Experienced — risk-free Black Work\n✔️ Beginners — pro tool, no big budget\n✔️ Studios — new service offering\n✔️ Unhappy with standard packing",
        "btn_model": "🖤 CHOOSE MODEL",
        "btn_rent": "💰 RENT",
        "btn_why": "🔧 WHY US",
        "btn_support": "🛠 SUPPORT",
        "btn_whom": "🎯 WHO",
        "btn_contact": "📩 CONTACT",
        "btn_ru": "🇷🇺 RU",
        "btn_en": "🇬🇧 EN",
        "btn_back": "« BACK",
    }
}

def get_main_keyboard(lang):
    t = TEXTS[lang]
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t["btn_model"], web_app=WebAppInfo(url=f"{WEBAPP_URL}/catalog"))],
        [InlineKeyboardButton(text=t["btn_rent"], callback_data="rent"),
         InlineKeyboardButton(text=t["btn_why"], callback_data="why")],
        [InlineKeyboardButton(text=t["btn_support"], callback_data="support"),
         InlineKeyboardButton(text=t["btn_whom"], callback_data="for_whom")],
        [InlineKeyboardButton(text=t["btn_contact"], url="https://t.me/rootxi")],
        [InlineKeyboardButton(text=t["btn_ru"], callback_data="lang_ru"),
         InlineKeyboardButton(text=t["btn_en"], callback_data="lang_en")],
    ])

def get_back_keyboard(lang):
    t = TEXTS[lang]
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t["btn_model"], web_app=WebAppInfo(url=f"{WEBAPP_URL}/catalog"))],
        [InlineKeyboardButton(text=t["btn_back"], callback_data="back")],
    ])

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    lang = user_lang.get(user_id, "ru")
    await message.answer(TEXTS[lang]["start"], parse_mode="HTML", reply_markup=get_main_keyboard(lang))

@dp.callback_query()
async def process_callback(callback: types.CallbackQuery):
    await callback.answer()
    user_id = callback.from_user.id
    
    if callback.data == "lang_ru":
        user_lang[user_id] = "ru"
    elif callback.data == "lang_en":
        user_lang[user_id] = "en"
    
    lang = user_lang.get(user_id, "ru")
    t = TEXTS[lang]
    
    if callback.data == "back":
        await callback.message.answer(t["start"], parse_mode="HTML", reply_markup=get_main_keyboard(lang))
    elif callback.data in ["why", "rent", "support", "for_whom"]:
        await callback.message.answer(t[callback.data], parse_mode="HTML", reply_markup=get_back_keyboard(lang))
    elif callback.data in ["lang_ru", "lang_en"]:
        await callback.message.answer(t["start"], parse_mode="HTML", reply_markup=get_main_keyboard(lang))

def run_flask():
    app.run(host="0.0.0.0", port=PORT, debug=False, use_reloader=False)

async def main():
    bot = Bot(token=BOT_TOKEN)
    threading.Thread(target=run_flask, daemon=True).start()
    logger.info(f"Bot started! WebApp: {WEBAPP_URL}")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
