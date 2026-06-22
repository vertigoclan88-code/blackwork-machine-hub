import os, sys, asyncio, logging, threading, sqlite3, re
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
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from flask import Flask, render_template, request, jsonify

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
logger = logging.getLogger(__name__)

app = Flask(__name__)
dp  = Dispatcher()

# DB
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
                    ("🖤 VOID REAPER",    "Макс. плотность закраса\nХод 4.2 мм • Большие площади",    "от $300/мес", "BLACKOUT",  1),
                    ("⚡ SHADOW WOLF",    "Баланс скорости и плотности\nХод 3.8 мм • Универсальный",  "от $350/мес", "BLACKWORK", 1),
                    ("🎯 DARK KRISHNA X", "Точный контроль\nХод 3.5 мм • Dark Lettering",             "от $400/мес", "LETTERING", 1),
                ],
            )

init_db()

# Language
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

# Flask routes
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/catalog")
def catalog():
    return render_template("catalog.html")

@app.route("/masters")
def masters():
    return render_template("masters.html")

@app.route("/models")
def models():
    return render_template("models.html")

@app.route("/setup_finder")
def setup_finder():
    return render_template("setup_finder.html")

@app.route("/api/masters")
def api_masters():
    masters_data = [
        {"name": "DIMA KRISHNA", "specialty": "Blackwork, Dark Lettering", "experience": "15 years", "rating": 5.0, "bio": "Custom machine creator. Hand-built every unit since 2010."},
        {"name": "ALEXEY INKGOD", "specialty": "Blackwork, Dotwork", "experience": "8 years", "rating": 4.9, "bio": "Large-scale blackwork projects specialist."},
        {"name": "MARIA BLACK", "specialty": "Ornamental, Black&Grey", "experience": "5 years", "rating": 4.8, "bio": "Geometric patterns and abstract designs."},
    ]
    return jsonify(masters_data)

@app.route("/api/catalog")
def api_catalog():
    with get_conn() as conn:
        items = [dict(r) for r in conn.execute("SELECT * FROM catalog WHERE is_available=1")]
    return jsonify(items)

PHONE_RE = re.compile(r"^\+?[\d\s\-()]{7,20}$")

@app.route("/api/submit_request", methods=["POST"])
def submit_request():
    data  = request.get_json(silent=True) or {}
    name  = str(data.get("name",  "")).strip()[:100]
    phone = str(data.get("phone", "")).strip()[:30]
    model = str(data.get("model", "")).strip()[:100]
    desc  = str(data.get("description", "")).strip()[:1000]
    if not name or not phone:
        return jsonify({"success": False, "error": "name and phone required"}), 400
    if not PHONE_RE.match(phone):
        return jsonify({"success": False, "error": "invalid phone"}), 400
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO requests(name,phone,model,description) VALUES(?,?,?,?)",
            (name, phone, model, desc),
        )
    return jsonify({"success": True})

# Texts
TEXTS = {
    "ru": {
        "start": (
            "🖤 <b>BLACKWORK MACHINE HUB</b>\n\n"
            "Кастомные машинки для <b>Dark Lettering и Black Work</b> — в аренду.\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "🔩 <b>VOID REAPER</b> — ход 4.2мм · блэкаут\n"
            "⚡ <b>SHADOW WOLF</b> — ход 3.8мм · универсал\n"
            "🎯 <b>DARK KRISHNA X</b> — ход 3.5мм · леттеринг\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "Плотная заливка с одного прохода. Без пятен, без просветов.\n"
            "Собираем вручную. Беспроводные. Настройка под твою руку.\n\n"
            "💵 <b>Аренда от $300/мес</b> · 📩 Доставка по всему миру"
        ),
        "why": (
            "🔧 <b>ПОЧЕМУ НАШИ МАШИНКИ</b>\n\n"
            "<b>Не доработанный Китай. Инженерное решение под Black Work.</b>\n\n"
            "🔹 <b>Ход иглы заточен под плотность</b>\n"
            "Максимальное давление пигмента за минимум проходов.\n\n"
            "🔹 <b>Стабильность на длинных сессиях</b>\n"
            "Каждая машинка тестируется 3+ часа непрерывной заливки.\n\n"
            "🔹 <b>Полностью беспроводные</b>\n"
            "Никаких проводов — полная свобода движения.\n\n"
            "🔹 <b>Настройка под твою руку</b>\n"
            "Калибруем ход, отдачу и баланс персонально.\n\n"
            "🔹 <b>Поддержка 24/7</b>\n"
            "Сборщик на связи с первого дня аренды."
        ),
        "rent": (
            "💰 <b>АРЕНДА — УМНЫЙ ВЫБОР</b>\n\n"
            "Хорошая машинка стоит как 2–3 сеанса.\n"
            "Не у всех есть сумма сразу — аренда решает это.\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "💵 Сеанс у мастера: <b>$150–200</b>\n"
            "💵 Аренда: <b>от $300/мес</b>\n"
            "📈 Окупаемость: <b>1.5–2 сеанса</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "✅ Нет крупных вложений\n"
            "✅ Не подошло — заменим\n"
            "✅ Машинка всегда обслужена\n"
            "✅ Персональная настройка включена"
        ),
        "support": (
            "🛠 <b>ПОДДЕРЖКА 24/7</b>\n\n"
            "Мы не продаём железо и не исчезаем.\n"
            "Сборщик на связи лично с первого дня:\n\n"
            "▸ Настройка под твою руку и технику\n"
            "▸ Помощь на первых рабочих сессиях\n"
            "▸ Удалённая диагностика и советы\n"
            "▸ Замена или доработка при необходимости\n"
            "▸ Обучение Black Work и Dark Lettering\n\n"
            "📩 <b>Доставка по всему миру</b>\n"
            "Работаем с мастерами из 20+ стран."
        ),
        "for_whom": (
            "🎯 <b>КОМУ ПОДХОДИТ</b>\n\n"
            "✔️ <b>Опытным мастерам</b>\n"
            "Переход в Black Work без риска потерять деньги на неподходящей машинке.\n\n"
            "✔️ <b>Начинающим</b>\n"
            "Профессиональный инструмент без большого бюджета на старте.\n\n"
            "✔️ <b>Студиям</b>\n"
            "Расширение услуг и привлечение мастеров нового направления.\n\n"
            "✔️ <b>Недовольным обычной заливкой</b>\n"
            "Если стандартные машинки не дают нужной плотности."
        ),
        "models": (
            "🖤 <b>3 МОДЕЛИ — 3 ХАРАКТЕРА</b>\n\n"
            "🔩 <b>VOID REAPER</b> · от $300/мес\n"
            "Ход 4.2мм · Категория: BLACKOUT\n"
            "Максимальная плотность закраса. Большие площади с одного прохода.\n\n"
            "⚡ <b>SHADOW WOLF</b> · от $350/мес\n"
            "Ход 3.8мм · Категория: BLACKWORK\n"
            "Баланс скорости и плотности. Универсальный боец.\n\n"
            "🎯 <b>DARK KRISHNA X</b> · от $400/мес\n"
            "Ход 3.5мм · Категория: LETTERING\n"
            "Точный контроль для Dark Lettering и тонких работ.\n\n"
            "Все модели беспроводные. Настройка под мастера включена."
        ),
        "btn_catalog":  "🛍 КАТАЛОГ",
        "btn_masters":  "👨‍🎨 МАСТЕРА",
        "btn_setup":    "🔧 SETUP FINDER",
        "btn_models":   "🖤 МОДЕЛИ",
        "btn_rent":     "💰 АРЕНДА",
        "btn_why":      "⚙️ ПОЧЕМУ МЫ",
        "btn_support":  "🛠 ПОДДЕРЖКА",
        "btn_whom":     "🎯 КОМУ",
        "btn_contact":  "📩 НАПИСАТЬ МАСТЕРУ",
        "btn_ru":       "🇷🇺 RU ✓",
        "btn_en":       "🇬🇧 EN",
        "btn_back":     "‹ НАЗАД",
    },
    "en": {
        "start": (
            "🖤 <b>BLACKWORK MACHINE HUB</b>\n\n"
            "Custom machines for <b>Dark Lettering & Black Work</b> — for rent.\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "🔩 <b>VOID REAPER</b> — 4.2mm stroke · blackout\n"
            "⚡ <b>SHADOW WOLF</b> — 3.8mm stroke · universal\n"
            "🎯 <b>DARK KRISHNA X</b> — 3.5mm stroke · lettering\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "Dense fill in one pass. No spots, no gaps.\n"
            "Hand-built. Wireless. Calibrated to your hand.\n\n"
            "💵 <b>Rent from $300/mo</b> · 📩 Worldwide shipping"
        ),
        "why": (
            "🔧 <b>WHY OUR MACHINES</b>\n\n"
            "<b>Not modified China. Engineered for Black Work.</b>\n\n"
            "🔹 <b>Stroke tuned for density</b>\n"
            "Max pigment pressure, minimum passes.\n\n"
            "🔹 <b>Stable on long sessions</b>\n"
            "Every machine tested 3+ hours of continuous fill.\n\n"
            "🔹 <b>Fully wireless</b>\n"
            "Zero cords, total freedom of movement.\n\n"
            "🔹 <b>Tuned to YOUR hand</b>\n"
            "Stroke, feedback, balance — calibrated personally.\n\n"
            "🔹 <b>24/7 support</b>\n"
            "Builder online personally from day one."
        ),
        "rent": (
            "💰 <b>RENT — THE SMART CHOICE</b>\n\n"
            "A good machine costs as much as 2–3 sessions.\n"
            "Not everyone has that upfront — renting solves it.\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "💵 Session price: <b>$150–200</b>\n"
            "💵 Rental: <b>from $300/mo</b>\n"
            "📈 Break-even: <b>1.5–2 sessions</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "✅ No big upfront cost\n"
            "✅ Not right? We swap it\n"
            "✅ Always maintained\n"
            "✅ Personal calibration included"
        ),
        "support": (
            "🛠 <b>24/7 SUPPORT</b>\n\n"
            "We don't sell hardware and vanish.\n"
            "Builder online personally from day one:\n\n"
            "▸ Hand and technique calibration\n"
            "▸ Help on your first working sessions\n"
            "▸ Remote diagnostics and advice\n"
            "▸ Replacement or adjustment if needed\n"
            "▸ Black Work & Dark Lettering training\n\n"
            "📩 <b>Worldwide shipping</b>\n"
            "Working with artists from 20+ countries."
        ),
        "for_whom": (
            "🎯 <b>WHO IS THIS FOR</b>\n\n"
            "✔️ <b>Experienced artists</b>\n"
            "Enter Black Work without the risk of buying the wrong machine.\n\n"
            "✔️ <b>Beginners</b>\n"
            "Pro tool without a big startup budget.\n\n"
            "✔️ <b>Studios</b>\n"
            "Expand services and attract artists in a new direction.\n\n"
            "✔️ <b>Unhappy with standard fill</b>\n"
            "When regular machines don't deliver the density you need."
        ),
        "models": (
            "🖤 <b>3 MODELS — 3 CHARACTERS</b>\n\n"
            "🔩 <b>VOID REAPER</b> · from $300/mo\n"
            "Stroke 4.2mm · Category: BLACKOUT\n"
            "Maximum fill density. Large areas in one pass.\n\n"
            "⚡ <b>SHADOW WOLF</b> · from $350/mo\n"
            "Stroke 3.8mm · Category: BLACKWORK\n"
            "Speed and density balance. The universal fighter.\n\n"
            "🎯 <b>DARK KRISHNA X</b> · from $400/mo\n"
            "Stroke 3.5mm · Category: LETTERING\n"
            "Precise control for Dark Lettering and fine work.\n\n"
            "All models wireless. Calibration included."
        ),
        "btn_catalog":  "🛍 CATALOG",
        "btn_masters":  "👨‍🎨 MASTERS",
        "btn_setup":    "🔧 SETUP FINDER",
        "btn_models":   "🖤 MODELS",
        "btn_rent":     "💰 RENT",
        "btn_why":      "⚙️ WHY US",
        "btn_support":  "🛠 SUPPORT",
        "btn_whom":     "🎯 WHO",
        "btn_contact":  "📩 CONTACT MASTER",
        "btn_ru":       "🇷🇺 RU",
        "btn_en":       "🇬🇧 EN ✓",
        "btn_back":     "‹ BACK",
    },
}

CONTENT_KEYS = {"why", "rent", "support", "for_whom", "models"}

# Keyboards
def main_keyboard(lang: str) -> InlineKeyboardMarkup:
    t = TEXTS[lang]
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t["btn_catalog"], web_app=WebAppInfo(url=f"{WEBAPP_URL}"))],
        [InlineKeyboardButton(text=t["btn_masters"], web_app=WebAppInfo(url=f"{WEBAPP_URL}/masters")),
         InlineKeyboardButton(text=t["btn_setup"], web_app=WebAppInfo(url=f"{WEBAPP_URL}/setup_finder"))],
        [InlineKeyboardButton(text=t["btn_models"], callback_data="models"),
         InlineKeyboardButton(text=t["btn_rent"], callback_data="rent")],
        [InlineKeyboardButton(text=t["btn_why"], callback_data="why"),
         InlineKeyboardButton(text=t["btn_support"], callback_data="support")],
        [InlineKeyboardButton(text=t["btn_whom"], callback_data="for_whom")],
        [InlineKeyboardButton(text=t["btn_contact"], url="https://t.me/rootxi")],
        [InlineKeyboardButton(text=t["btn_ru"], callback_data="lang_ru"),
         InlineKeyboardButton(text=t["btn_en"], callback_data="lang_en")],
    ])

def back_keyboard(lang: str) -> InlineKeyboardMarkup:
    t = TEXTS[lang]
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t["btn_catalog"], web_app=WebAppInfo(url=f"{WEBAPP_URL}"))],
        [InlineKeyboardButton(text=t["btn_masters"], web_app=WebAppInfo(url=f"{WEBAPP_URL}/masters")),
         InlineKeyboardButton(text=t["btn_setup"], web_app=WebAppInfo(url=f"{WEBAPP_URL}/setup_finder"))],
        [InlineKeyboardButton(text=t["btn_contact"], url="https://t.me/rootxi")],
        [InlineKeyboardButton(text=t["btn_ru"], callback_data="lang_ru"),
         InlineKeyboardButton(text=t["btn_en"], callback_data="lang_en")],
        [InlineKeyboardButton(text=t["btn_back"], callback_data="back")],
    ])

# Handlers
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    lang = get_lang(message.from_user.id)
    await message.answer(TEXTS[lang]["start"], parse_mode="HTML", reply_markup=main_keyboard(lang))

@dp.message()
async def on_unknown(message: types.Message):
    lang = get_lang(message.from_user.id)
    await message.answer(TEXTS[lang]["start"], parse_mode="HTML", reply_markup=main_keyboard(lang))

@dp.callback_query()
async def process_callback(cb: types.CallbackQuery):
    await cb.answer()
    uid  = cb.from_user.id
    data = cb.data

    if data == "lang_ru":
        set_lang(uid, "ru")
    elif data == "lang_en":
        set_lang(uid, "en")

    lang = get_lang(uid)
    t    = TEXTS[lang]

    if data in ("back", "lang_ru", "lang_en"):
        try:
            await cb.message.edit_text(t["start"], parse_mode="HTML", reply_markup=main_keyboard(lang))
        except Exception:
            await cb.message.answer(t["start"], parse_mode="HTML", reply_markup=main_keyboard(lang))
    elif data in CONTENT_KEYS:
        try:
            await cb.message.edit_text(t[data], parse_mode="HTML", reply_markup=back_keyboard(lang))
        except Exception:
            await cb.message.answer(t[data], parse_mode="HTML", reply_markup=back_keyboard(lang))

# Run
def run_flask():
    app.run(host="0.0.0.0", port=PORT, debug=False, use_reloader=False)

async def main():
    bot = Bot(token=BOT_TOKEN)
    threading.Thread(target=run_flask, daemon=True).start()
    logger.info(f"Bot started. WebApp: {WEBAPP_URL}")
    await dp.start_polling(bot, skip_updates=True)

if __name__ == "__main__":
    asyncio.run(main())
