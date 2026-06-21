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
            ("VOID REAPER", "Max density packing\n4.2mm stroke\nLarge areas", "from $300/mo", "BLACKOUT", 1),
            ("SHADOW WOLF", "Speed & density balance\n3.8mm stroke\nUniversal fighter", "from $350/mo", "BLACKWORK", 1),
            ("DARK KRISHNA X", "Precision control\n3.5mm stroke\nDark Lettering", "from $400/mo", "LETTERING", 1),
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

TEXT_START = """
<b>CUSTOM BLACKWORK MACHINES FOR RENT</b>

<i>The machine that makes Black Work — real Black Work.</i>

Dense, hard packing in one pass. No spots, no gaps, no re-working the skin.

We don't sell universal machines. We hand-build them for one task — <b>Dark Lettering & Black Work</b>, where density and stability matter more than speed.

3 custom models. Wireless. For any hand, any style.
"""

TEXT_WHY = """
<b>WHY OUR MACHINES</b>

<i>Not a modified Chinese machine. An engineering solution for Black Work.</i>

- <b>Stroke geometry tuned for density, not speed</b>
- <b>Stable on long sessions</b> — tested 3+ hours
- <b>Fully wireless</b> — total freedom
- <b>Tuned to YOUR hand</b> — personal calibration before shipping
- <b>Made by hand, not assembly line</b>
"""

TEXT_RENT = """
<b>WHY RENT, NOT BUY</b>

A good Black Work machine costs 2-3 sessions. Not every artist has that upfront — and that's normal.

Session: $150-200
Rent: <b>from $300/mo</b>

Payback in 1.5-2 sessions, then pure profit on a pro tool.

No big upfront cost. Try, switch if needed. Machine always maintained — our job.
"""

TEXT_SUPPORT = """
<b>24/7 SUPPORT</b>

<i>We don't sell hardware and disappear.</i>

The builder is personally in touch from day one:

- Machine tuning for your hand
- Help with first Black Work sessions
- Remote diagnostics & maintenance tips
- Replacement/modification if needed
- Black Work & Dark Lettering basics training

Worldwide shipping.
"""

TEXT_FOR_WHOM = """
<b>WHO IS THIS FOR</b>

- Experienced artists moving into Black Work
- New artists without budget for pro gear
- Studios adding Black Work services
- Anyone unsatisfied with standard machine packing
"""

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="CHOOSE MODEL", web_app=WebAppInfo(url=f"{WEBAPP_URL}/catalog"))],
        [InlineKeyboardButton(text="HOW RENT WORKS", callback_data="rent")],
        [InlineKeyboardButton(text="WHY OUR MACHINES", callback_data="why")],
        [InlineKeyboardButton(text="24/7 SUPPORT", callback_data="support")],
        [InlineKeyboardButton(text="WHO IS IT FOR", callback_data="for_whom")],
        [InlineKeyboardButton(text="CONTACT MASTER", url="https://t.me/rootxi")],
    ])
    
    await message.answer(TEXT_START, parse_mode="HTML", reply_markup=keyboard)

@dp.callback_query()
async def process_callback(callback: types.CallbackQuery):
    await callback.answer()
    
    texts = {
        "why": TEXT_WHY,
        "rent": TEXT_RENT,
        "support": TEXT_SUPPORT,
        "for_whom": TEXT_FOR_WHOM,
    }
    
    if callback.data in texts:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="CHOOSE MODEL", web_app=WebAppInfo(url=f"{WEBAPP_URL}/catalog"))],
        ])
        await callback.message.answer(texts[callback.data], parse_mode="HTML", reply_markup=keyboard)

def run_flask():
    app.run(host="0.0.0.0", port=PORT, debug=False, use_reloader=False)

async def main():
    bot = Bot(token=BOT_TOKEN)
    threading.Thread(target=run_flask, daemon=True).start()
    logger.info(f"Bot started! WebApp: {WEBAPP_URL}")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
