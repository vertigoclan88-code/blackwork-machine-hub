import os, sys, asyncio, logging, threading, sqlite3, json, re
from datetime import datetime
from functools import wraps
from dotenv import load_dotenv
load_dotenv()

BOT_TOKEN  = os.getenv("BOT_TOKEN")
ADMIN_ID   = int(os.getenv("ADMIN_ID", "0"))
PORT       = int(os.getenv("PORT", "10000"))
WEBAPP_URL = os.getenv("WEBAPP_URL", "https://blackwork-machine-hub.onrender.com")

if not BOT_TOKEN:
    sys.exit("ERROR: BOT_TOKEN not set in environment")

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton,
    WebAppInfo, FSInputFile,
)
from flask import Flask, render_template, request, jsonify

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
logger = logging.getLogger(__name__)

app = Flask(__name__)
dp  = Dispatcher()

# ---------------------------------------------------------------------------
# DB
# ---------------------------------------------------------------------------

DB_PATH = "blackwork_hub.db"

def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS catalog (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                name         TEXT NOT NULL,
                description  TEXT,
                price        TEXT,
                category     TEXT,
                is_available BOOLEAN DEFAULT 1
            );
            CREATE TABLE IF NOT EXISTS requests (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                name        TEXT,
                phone       TEXT,
                model       TEXT,
                description TEXT,
                created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS user_settings (
                user_id INTEGER PRIMARY KEY,
                lang    TEXT DEFAULT 'ru'
            );
        """)
        if conn.execute("SELECT COUNT(*) FROM catalog").fetchone()[0] == 0:
            conn.executemany(
                "INSERT INTO catalog VALUES (NULL,?,?,?,?,?)",
                [
                    ("🖤 VOID REAPER",   "Макс. плотность закраса\nХод 4.2 мм • Большие площади", "от $300/мес", "BLACKOUT",   1),
                    ("⚡ SHADOW WOLF",   "Баланс скорости и плотности\nХод 3.8 мм • Универсальный", "от $350/мес", "BLACKWORK",  1),
                    ("🎯 DARK KRISHNA X","Точный контроль\nХод 3.5 мм • Dark Lettering",           "от $400/мес", "LETTERING",  1),
                ],
            )

init_db()

# ---------------------------------------------------------------------------
# Language helpers (persistent)
# ---------------------------------------------------------------------------

def get_lang(user_id: int) -> str:
    with get_conn() as conn:
        row = conn.execute("SELECT lang FROM user_settings WHERE user_id=?", (user_id,)).fetchone()
    return row["lang"] if row else "ru"

def set_lang(user_id: int, lang: str):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO user_settings(user_id, lang) VALUES(?,?) "
            "ON CONFLICT(user_id) DO UPDATE SET lang=excluded.lang",
            (user_id, lang),
        )

# ---------------------------------------------------------------------------
# Flask routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/catalog")
def catalog():
    return render_template("catalog.html")

@app.route("/masters")
def masters():
    return render_template("masters.html")

@app.route("/setup_finder")
def setup_finder():
    return render_template("setup_finder.html")

@app.route("/api/catalog")
def api_catalog():
    with get_conn() as conn:
        items = [dict(r) for r in conn.execute("SELECT * FROM catalog WHERE is_available=1")]
    return jsonify(items)

PHONE_RE = re.compile(r"^\+?[\d\s\-()]{7,20}$")

@app.route("/api/submit_request", methods=["POST"])
def submit_request():
    data = request.get_json(silent=True) or {}
    name  = str(data.get("name",  "")).strip()[:100]
    phone = str(data.get("phone", "")).strip()[:30]
    model = str(data.get("model", "")).strip()[:100]
    desc  = str(data.get("description", "")).strip()[:1000]

    if not name or not phone:
        return jsonify({"success": False, "error": "name and phone are required"}), 400
    if not PHONE_RE.match(phone):
        return jsonify({"success": False, "error": "invalid phone"}), 400

    with get_conn() as conn:
        conn.execute(
            "INSERT INTO requests(name, phone, model, description) VALUES(?,?,?,?)",
            (name, phone, model, desc),
        )
    return jsonify({"success": True})

@app.route("/api/requests")
def api_requests():
    """Admin endpoint — restrict by IP or token in production."""
    admin_token = request.headers.get("X-Admin-Token", "")
    if admin_token != os.getenv("ADMIN_TOKEN", ""):
        return jsonify({"error": "forbidden"}), 403
    with get_conn() as conn:
        rows = [dict(r) for r in conn.execute("SELECT * FROM requests ORDER BY created_at DESC")]
    return jsonify(rows)

# ---------------------------------------------------------------------------
# Bot texts & keyboards
# ---------------------------------------------------------------------------

TEXTS = {
    "ru": {
        "start": (
            "🖤 <b>КАСТОМНЫЕ МАШИНКИ ДЛЯ BLACK WORK — В АРЕНДУ</b>\n\n"
            "<b>Машинка, которая делает Black Work — настоящим Black Work.</b>\n\n"
            "Плотная, жёсткая заливка с одного прохода. Без пятен, без просветов, без перепрохода по коже.\n\n"
            "Мы не продаём серийные машинки «для всего». Мы собираем их вручную под одну задачу — "
            "<b>Dark Lettering и Black Work</b>, где важна не скорость, а <b>плотность и стабильность хода иглы</b>.\n\n"
            "3 кастомных модели. Беспроводные. Под любую руку и любой стиль.\n\n"
            "▔▔▔▔▔▔▔▔▔▔▔▔▔▔\n"
            "💵 <b>Аренда от $300/мес</b>\n"
            "🔧 <b>Настройка персонально под мастера</b>\n"
            "📩 <b>Доставка по всему миру</b>"
        ),
        "why": (
            "🖤 <b>ПОЧЕМУ НАШИ МАШИНКИ</b>\n\n"
            "<b>Не доработанный Китай. Инженерное решение под Black Work.</b>\n\n"
            "🔹 <b>Ход иглы заточен под плотность</b>\n"
            "Стандартные машинки — универсальный удар. Наша геометрия — максимальное давление пигмента за минимум проходов.\n\n"
            "🔹 <b>Стабильность на длинных сессиях</b>\nТестируем каждую машинку 3+ часа непрерывной заливки.\n\n"
            "🔹 <b>Полностью беспроводные</b>\nНикаких проводов — свобода движения.\n\n"
            "🔹 <b>Персональная настройка под руку</b>\nКалибруем ход, отдачу и баланс под твою технику.\n\n"
            "🔹 <b>Made by hand</b>\n3 модели — 3 характера хода."
        ),
        "rent": (
            "💰 <b>АРЕНДА ВМЕСТО ПОКУПКИ</b>\n\n"
            "<b>Хорошая машинка = 2–3 сеанса. Не у всех есть сумма сразу.</b>\n\n"
            "💵 Сеанс: $150–200\n💵 Аренда: <b>от $300/мес</b>\n\n"
            "Окупаемость: <b>1,5–2 сеанса</b> → чистая прибыль.\n\n"
            "✅ Без крупных вложений\n✅ Не подошло — заменим\n"
            "✅ Машинка всегда обслужена\n✅ Порог входа снижен"
        ),
        "support": (
            "🛠 <b>ПОДДЕРЖКА 24/7</b>\n\n"
            "<b>Не продаём железо и не исчезаем.</b>\n\n"
            "Сборщик на связи лично с первого дня:\n\n"
            "▸ Настройка под твою руку\n▸ Помощь на первых сессиях\n"
            "▸ Диагностика и советы по уходу\n▸ Замена/доработка при необходимости\n"
            "▸ Обучение Black Work и Dark Lettering\n\n"
            "📩 Доставка по всему миру"
        ),
        "for_whom": (
            "🎯 <b>КОМУ ПОДХОДИТ</b>\n\n"
            "✔️ Опытным — переход в Black Work без риска\n"
            "✔️ Начинающим — проф. инструмент без бюджета\n"
            "✔️ Студиям — расширение услуг\n"
            "✔️ Недовольным обычной заливкой"
        ),
        "unknown": "Используй кнопки ниже 👇",
        "btn_model":   "🖤 ВЫБРАТЬ МОДЕЛЬ",
        "btn_rent":    "💰 АРЕНДА",
        "btn_why":     "🔧 ПОЧЕМУ МЫ",
        "btn_support": "🛠 ПОДДЕРЖКА",
        "btn_whom":    "🎯 КОМУ",
        "btn_contact": "📩 МАСТЕР",
        "btn_catalog": "🖤 КАТАЛОГ",
        "btn_masters": "👨‍🎨 МАСТЕРА",
        "btn_setup":   "🔧 SETUP FINDER",
        "btn_ru":      "🇷🇺 RU ✓",
        "btn_en":      "🇬🇧 EN",
        "btn_back":    "« НАЗАД",
    },
    "en": {
        "start": (
            "🖤 <b>CUSTOM BLACKWORK MACHINES FOR RENT</b>\n\n"
            "<b>The machine that makes Black Work — real Black Work.</b>\n\n"
            "Dense packing in one pass. No spots, no gaps, no re-working.\n\n"
            "Hand-built for <b>Dark Lettering & Black Work</b> — density and stability over speed.\n\n"
            "3 custom models. Wireless. For any hand, any style.\n\n"
            "▔▔▔▔▔▔▔▔▔▔▔▔▔▔\n"
            "💵 <b>Rent from $300/mo</b>\n"
            "🔧 <b>Personal calibration included</b>\n"
            "📩 <b>Worldwide shipping</b>"
        ),
        "why": (
            "🖤 <b>WHY OUR MACHINES</b>\n\n"
            "<b>Not modified China. Engineered for Black Work.</b>\n\n"
            "🔹 <b>Stroke tuned for density</b>\nMax pigment pressure, minimum passes.\n\n"
            "🔹 <b>Stable on long sessions</b>\n3+ hours tested before shipping.\n\n"
            "🔹 <b>Fully wireless</b>\nZero cords, total freedom.\n\n"
            "🔹 <b>Tuned to YOUR hand</b>\nStroke, feedback, balance — calibrated personally.\n\n"
            "🔹 <b>Made by hand</b>\n3 models, 3 characters."
        ),
        "rent": (
            "💰 <b>RENT VS BUY</b>\n\n"
            "<b>A good machine = 2–3 sessions. Not everyone has that upfront.</b>\n\n"
            "💵 Session: $150–200\n💵 Rent: <b>from $300/mo</b>\n\n"
            "Payback: <b>1.5–2 sessions</b> → pure profit.\n\n"
            "✅ No big upfront cost\n✅ Not right? Swap it\n"
            "✅ Always maintained\n✅ Entry barrier lowered"
        ),
        "support": (
            "🛠 <b>24/7 SUPPORT</b>\n\n"
            "<b>We don't sell hardware and vanish.</b>\n\n"
            "Builder online personally from day one:\n\n"
            "▸ Hand tuning\n▸ First session help\n"
            "▸ Remote diagnostics\n▸ Replacement if needed\n"
            "▸ Black Work training\n\n"
            "📩 Worldwide shipping"
        ),
        "for_whom": (
            "🎯 <b>WHO IS THIS FOR</b>\n\n"
            "✔️ Experienced — risk-free Black Work\n"
            "✔️ Beginners — pro tool, no big budget\n"
            "✔️ Studios — new service offering\n"
            "✔️ Unhappy with standard packing"
        ),
        "unknown": "Use the buttons below 👇",
        "btn_model":   "🖤 CHOOSE MODEL",
        "btn_rent":    "💰 RENT",
        "btn_why":     "🔧 WHY US",
        "btn_support": "🛠 SUPPORT",
        "btn_whom":    "🎯 WHO",
        "btn_contact": "📩 CONTACT",
        "btn_catalog": "🖤 CATALOG",
        "btn_masters": "👨‍🎨 MASTERS",
        "btn_setup":   "🔧 SETUP FINDER",
        "btn_ru":      "🇷🇺 RU",
        "btn_en":      "🇬🇧 EN ✓",
        "btn_back":    "« BACK",
    },
}

CONTENT_KEYS = {"why", "rent", "support", "for_whom"}

def main_keyboard(lang: str) -> InlineKeyboardMarkup:
    t = TEXTS[lang]
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t["btn_catalog"],
                              web_app=WebAppInfo(url=f"{WEBAPP_URL}/catalog"))],
        [InlineKeyboardButton(text=t["btn_masters"],
                              web_app=WebAppInfo(url=f"{WEBAPP_URL}/masters")),
         InlineKeyboardButton(text=t["btn_setup"],
                              web_app=WebAppInfo(url=f"{WEBAPP_URL}/setup_finder"))],
        [InlineKeyboardButton(text=t["btn_rent"],    callback_data="rent"),
         InlineKeyboardButton(text=t["btn_why"],     callback_data="why")],
        [InlineKeyboardButton(text=t["btn_support"], callback_data="support"),
         InlineKeyboardButton(text=t["btn_whom"],    callback_data="for_whom")],
        [InlineKeyboardButton(text=t["btn_contact"], url="https://t.me/rootxi")],
        [InlineKeyboardButton(text=t["btn_ru"], callback_data="lang_ru"),
         InlineKeyboardButton(text=t["btn_en"], callback_data="lang_en")],
    ])

def back_keyboard(lang: str) -> InlineKeyboardMarkup:
    t = TEXTS[lang]
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t["btn_catalog"],
                              web_app=WebAppInfo(url=f"{WEBAPP_URL}/catalog"))],
        [InlineKeyboardButton(text=t["btn_masters"],
                              web_app=WebAppInfo(url=f"{WEBAPP_URL}/masters")),
         InlineKeyboardButton(text=t["btn_setup"],
                              web_app=WebAppInfo(url=f"{WEBAPP_URL}/setup_finder"))],
        [InlineKeyboardButton(text=t["btn_back"], callback_data="back")],
    ])

# ---------------------------------------------------------------------------
# Bot handlers
# ---------------------------------------------------------------------------

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    lang = get_lang(message.from_user.id)
    await message.answer(
        TEXTS[lang]["start"],
        parse_mode="HTML",
        reply_markup=main_keyboard(lang),
    )

@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    lang = get_lang(message.from_user.id)
    await message.answer(
        TEXTS[lang]["start"],
        parse_mode="HTML",
        reply_markup=main_keyboard(lang),
    )

@dp.message()
async def on_unknown(message: types.Message):
    """Catch-all for any text/sticker/etc."""
    lang = get_lang(message.from_user.id)
    await message.answer(
        TEXTS[lang]["unknown"],
        reply_markup=main_keyboard(lang),
    )

@dp.callback_query()
async def process_callback(cb: types.CallbackQuery):
    await cb.answer()
    uid  = cb.from_user.id
    data = cb.data

    # Language switch
    if data == "lang_ru":
        set_lang(uid, "ru")
    elif data == "lang_en":
        set_lang(uid, "en")

    lang = get_lang(uid)
    t    = TEXTS[lang]

    if data in ("back", "lang_ru", "lang_en"):
        # Edit current message instead of sending a new one
        try:
            await cb.message.edit_text(
                t["start"],
                parse_mode="HTML",
                reply_markup=main_keyboard(lang),
            )
        except Exception:
            await cb.message.answer(
                t["start"],
                parse_mode="HTML",
                reply_markup=main_keyboard(lang),
            )

    elif data in CONTENT_KEYS:
        try:
            await cb.message.edit_text(
                t[data],
                parse_mode="HTML",
                reply_markup=back_keyboard(lang),
            )
        except Exception:
            await cb.message.answer(
                t[data],
                parse_mode="HTML",
                reply_markup=back_keyboard(lang),
            )

# ---------------------------------------------------------------------------
# Admin notification helper
# ---------------------------------------------------------------------------

async def notify_admin(bot: Bot, text: str):
    if ADMIN_ID:
        try:
            await bot.send_message(ADMIN_ID, text, parse_mode="HTML")
        except Exception as e:
            logger.warning(f"Admin notify failed: {e}")

# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def run_flask():
    app.run(host="0.0.0.0", port=PORT, debug=False, use_reloader=False)

async def main():
    bot = Bot(token=BOT_TOKEN)
    threading.Thread(target=run_flask, daemon=True).start()
    logger.info(f"Bot started. WebApp: {WEBAPP_URL}")
    await dp.start_polling(bot, skip_updates=True)

if __name__ == "__main__":
    asyncio.run(main())
