import os
import asyncio
import logging
import threading
import sqlite3
from datetime import datetime
from dotenv import load_dotenv
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = os.getenv("ADMIN_ID")
WEBAPP_URL = os.getenv("WEBAPP_URL", "https://your-app.onrender.com")
PORT = int(os.getenv("PORT", "10000"))

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from flask import Flask, render_template, request, jsonify

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
logger = logging.getLogger(__name__)

app = Flask(__name__)
dp = Dispatcher()

# ===== DATABASE =====
def init_db():
    conn = sqlite3.connect("blackwork_hub.db")
    c = conn.cursor()
    
    c.execute("""CREATE TABLE IF NOT EXISTS catalog
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  name TEXT, description TEXT, price TEXT,
                  category TEXT, is_available BOOLEAN DEFAULT 1)""")
    
    c.execute("""CREATE TABLE IF NOT EXISTS masters
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  name TEXT, specialty TEXT, experience TEXT,
                  rating REAL, bio TEXT)""")
    
    c.execute("""CREATE TABLE IF NOT EXISTS requests
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  name TEXT, phone TEXT, machine_type TEXT,
                  description TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
    
    c.execute("SELECT COUNT(*) FROM catalog")
    if c.fetchone()[0] == 0:
        items = [
            ("🖤 STEALTH PRO X1", "Professional blackwork machine\nAdjustable needle stroke\nDense packing specialist", "35 000 ₽", "ROTARY", 1),
            ("⚡ SHADOW MASTER 2000", "Powerful coil machine\nMaximum power for large projects\nBlackwork monster", "28 500 ₽", "COIL", 1),
            ("🎯 PRECISION LINE V3", "Lightweight rotary\nFine lines & dotwork\nPrecision control", "22 000 ₽", "ROTARY", 1),
            ("💀 DARK SOUL CUSTOM", "Custom build\nUnique design\nHand-made exclusive", "45 000 ₽", "CUSTOM", 1),
            ("🔮 VOID REAPER", "Limited edition\nBlackwork specialist\nProfessional series", "55 000 ₽", "LIMITED", 1),
            ("🐺 SHADOW WOLF", "Signature series\nArtist choice\nPremium quality", "42 000 ₽", "SIGNATURE", 1),
        ]
        c.executemany("INSERT INTO catalog VALUES (NULL,?,?,?,?,?)", items)
    
    c.execute("SELECT COUNT(*) FROM masters")
    if c.fetchone()[0] == 0:
        items = [
            ("ALEXEY INKGOD", "Blackwork, Dotwork", "8 years", 4.9, "Large-scale blackwork projects specialist"),
            ("MARIA BLACK", "Ornamental, Black&Grey", "5 years", 4.8, "Geometric patterns expert"),
            ("DMITRY SHADE", "Realism, Blackwork", "10 years", 5.0, "International award-winning artist"),
            ("DARK KRISHNA X", "Experimental, Dark Art", "12 years", 4.9, "Legendary machine creator"),
        ]
        c.executemany("INSERT INTO masters VALUES (NULL,?,?,?,?,?)", items)
    
    conn.commit()
    conn.close()

init_db()

# ===== FLASK ROUTES =====
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
    conn = sqlite3.connect("blackwork_hub.db")
    c = conn.cursor()
    c.execute("SELECT * FROM catalog")
    items = [{"id": r[0], "name": r[1], "description": r[2], 
              "price": r[3], "category": r[4], 
              "is_available": bool(r[5])} for r in c.fetchall()]
    conn.close()
    return jsonify(items)

@app.route("/api/masters")
def api_masters():
    conn = sqlite3.connect("blackwork_hub.db")
    c = conn.cursor()
    c.execute("SELECT * FROM masters")
    items = [{"id": r[0], "name": r[1], "specialty": r[2], 
              "experience": r[3], "rating": r[4], 
              "bio": r[5]} for r in c.fetchall()]
    conn.close()
    return jsonify(items)

@app.route("/api/submit_request", methods=["POST"])
def submit_request():
    data = request.json
    name = data.get("name")
    phone = data.get("phone")
    machine_type = data.get("machine_type", "")
    description = data.get("description", "")
    
    if not name or not phone:
        return jsonify({"success": False, "error": "Name and phone required"}), 400
    
    conn = sqlite3.connect("blackwork_hub.db")
    c = conn.cursor()
    c.execute("INSERT INTO requests (name, phone, machine_type, description) VALUES (?,?,?,?)",
              (name, phone, machine_type, description))
    request_id = c.lastrowid
    conn.commit()
    conn.close()
    
    logger.info(f"📝 New request #{request_id} from {name}")
    return jsonify({"success": True, "request_id": request_id})

# ===== TELEGRAM BOT =====
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    webapp_buttons = [
        [InlineKeyboardButton(text="🛍 CATALOG", web_app=WebAppInfo(url=f"{WEBAPP_URL}/catalog"))],
        [InlineKeyboardButton(text="👨‍🎨 MASTERS", web_app=WebAppInfo(url=f"{WEBAPP_URL}/masters"))],
        [InlineKeyboardButton(text="🔧 SETUP FINDER", web_app=WebAppInfo(url=f"{WEBAPP_URL}/setup_finder"))],
        [InlineKeyboardButton(text="📝 ORDER CUSTOM", web_app=WebAppInfo(url=WEBAPP_URL))],
    ]
    
    text_buttons = [
        [InlineKeyboardButton(text="📋 Catalog in Chat", callback_data="catalog_text")],
        [InlineKeyboardButton(text="👥 Masters in Chat", callback_data="masters_text")],
        [InlineKeyboardButton(text="💬 Contact", url="https://t.me/BlackWorkTatoo")],
    ]
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=webapp_buttons + text_buttons)
    
    await message.answer(
        f"🖤 <b>BLACKWORK MACHINE HUB</b>\n\n"
        f"<i>Premium Tattoo Machines for Blackwork Artists</i>\n\n"
        f"▸ VOID REAPER\n▸ SHADOW WOLF\n▸ DARK KRISHNA X\n\n"
        f"🌐 {WEBAPP_URL}",
        parse_mode="HTML",
        reply_markup=keyboard
    )

@dp.callback_query()
async def process_callback(callback: types.CallbackQuery):
    await callback.answer()
    
    if callback.data == "catalog_text":
        conn = sqlite3.connect("blackwork_hub.db")
        c = conn.cursor()
        c.execute("SELECT name, description, price, category, is_available FROM catalog")
        items = c.fetchall()
        conn.close()
        
        text = "🛍 <b>CATALOG</b>\n\n"
        for name, desc, price, cat, avail in items:
            status = "✅" if avail else "❌ SOLD OUT"
            text += f"{status} <b>{name}</b>\n<i>{desc}</i>\n💎 {price} | {cat}\n\n"
        
        await callback.message.answer(text, parse_mode="HTML")
    
    elif callback.data == "masters_text":
        conn = sqlite3.connect("blackwork_hub.db")
        c = conn.cursor()
        c.execute("SELECT name, specialty, experience, rating, bio FROM masters")
        items = c.fetchall()
        conn.close()
        
        text = "👨‍🎨 <b>MASTERS</b>\n\n"
        for name, spec, exp, rating, bio in items:
            stars = "⭐" * int(rating)
            text += f"<b>{name}</b>\n🎯 {spec}\n📅 {exp}\n{stars} {rating}/5\n<i>{bio}</i>\n\n"
        
        await callback.message.answer(text, parse_mode="HTML")

# ===== MAIN =====
async def main():
    bot = Bot(token=BOT_TOKEN)
    
    # Flask в отдельном потоке
    def run_flask():
        app.run(host="0.0.0.0", port=PORT, debug=False)
    
    threading.Thread(target=run_flask, daemon=True).start()
    
    # Запуск бота
    logger.info(f"🤖 Bot started!")
    logger.info(f"🌐 WebApp: {WEBAPP_URL}")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
