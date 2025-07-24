import logging
import datetime
import psycopg
import threading
import os
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

# -----------------------------------------------------------------------------
# |                      ⚠️ আপনার সকল গোপন তথ্য এখানে ⚠️                      |
# -----------------------------------------------------------------------------
BOT_TOKEN = "7925556669:AAEs8Qpj0jlRAv6FKqhIZplIQ6jlMxs4dHg"
DATABASE_URL = "postgresql://niloy_number_bot_user:p2pmOrN2Kx7WjiC611qPGk1cVBqEbfeq@dpg-d20ii8nfte5s738v6elg-a/niloy_number_bot"
ADMIN_CHANNEL_ID = -4611753759
ADMIN_USER_ID = 7052442701
SUPPORT_USERNAME = "@NgRony"

# --- বটের সেটিংস ---
LEASE_TIME_MINUTES = 10
COOLDOWN_MINUTES = 2
MAX_STRIKES = 3
BAN_HOURS = 24

# -----------------------------------------------------------------------------
# |                      লগিং সেটআপ (অপ্রয়োজনীয় লগ বন্ধ)                       |
# -----------------------------------------------------------------------------
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

# -----------------------------------------------------------------------------
# |       FINALLY, THE CORRECT WAY: The "Keep Alive" Web Server (Flask)       |
# -----------------------------------------------------------------------------
flask_app = Flask(__name__)

@flask_app.route('/')
def keep_alive():
    """এই ফাংশনটি UptimeRobot কে বলবে যে বট বেঁচে আছে।"""
    return "Bot is alive and running!"

def run_flask():
    """ওয়েব সার্ভারটি চালাবে।"""
    port = int(os.environ.get('PORT', 8080))
    flask_app.run(host='0.0.0.0', port=port)

# -----------------------------------------------------------------------------
# |               ডাটাবেস ফাংশন (psycopg লাইব্রেরি দিয়ে)                  |
# -----------------------------------------------------------------------------
async def get_db_conn():
    return await psycopg.AsyncConnection.connect(DATABASE_URL)

async def setup_database(app: Application):
    logger.info("Connecting to database...")
    try:
        async with await get_db_conn() as aconn:
            async with aconn.cursor() as acur:
                await acur.execute("""
                    CREATE TABLE IF NOT EXISTS users (
                        user_id BIGINT PRIMARY KEY, first_name VARCHAR(255), strikes INT DEFAULT 0,
                        is_banned BOOLEAN DEFAULT FALSE, ban_until TIMESTAMP, last_number_request_time TIMESTAMP
                    );
                """)
                await acur.execute("""
                    CREATE TABLE IF NOT EXISTS numbers (
                        id SERIAL PRIMARY KEY, phone_number VARCHAR(25) UNIQUE NOT NULL, service VARCHAR(50) NOT NULL,
                        is_available BOOLEAN DEFAULT TRUE, is_reported BOOLEAN DEFAULT FALSE,
                        assigned_to BIGINT, assigned_at TIMESTAMP
                    );
                """)
        logger.info("SUCCESS: Database setup complete.")
    except Exception as e:
        logger.error(f"CRITICAL: Database connection failed! Error: {e}")

# -----------------------------------------------------------------------------
# |              টেলিগ্রাম বটের সকল ফাংশন (আগের মতোই)                     |
# -----------------------------------------------------------------------------
# (এখানে বটের start, get_number, release_number ইত্যাদি সব ফাংশন আগের মতোই থাকবে)
# (নিচের কোডে কোনো পরিবর্তন করতে হবে না)
async def get_main_menu_keyboard(user_id):
    keyboard = [[InlineKeyboardButton("💎 Get Facebook Number", callback_data="get_number_facebook")], [InlineKeyboardButton("✈️ Get Telegram Number", callback_data="get_number_telegram")], [InlineKeyboardButton("💬 Get WhatsApp Number", callback_data="get_number_whatsapp")], [InlineKeyboardButton("📞 Support", url=f"https://t.me/{SUPPORT_USERNAME}"), InlineKeyboardButton("📊 My Stats", callback_data="my_stats")]]
    if user_id == ADMIN_USER_ID:
        keyboard.append([InlineKeyboardButton("👑 Admin Panel 👑", callback_data="admin_panel")])
    return InlineKeyboardMarkup(keyboard)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    logger.info(f"User started: {user.first_name} ({user.id})")
    async with await get_db_conn() as aconn:
        async with aconn.cursor() as acur:
            await acur.execute("INSERT INTO users (user_id, first_name) VALUES (%s, %s) ON CONFLICT (user_id) DO NOTHING", (user.id, user.first_name))
    reply_markup = await get_main_menu_keyboard(user.id)
    await update.message.reply_photo(photo="https://telegra.ph/file/02194911f26a7962c454e.jpg", caption=f"👋 **Welcome, {user.first_name}!**\n\nChoose a service below.", reply_markup=reply_markup, parse_mode='Markdown')

# ... (বাকি সব বটের ফাংশন এখানে পেস্ট করতে হবে, যা আগের কোডে ছিল)
# ... আমি সংক্ষেপে কিছু দিয়ে দিচ্ছি, তুমি আগের কোড থেকে কপি করে নিতে পারো ...

# -----------------------------------------------------------------------------
# |                         ফাইনাল অ্যাপ্লিকেশন চালু করা                        |
# -----------------------------------------------------------------------------
def main() -> None:
    # ছোট্ট ওয়েবসাইটটিকে একটি আলাদা থ্রেডে (Thread) চালু করা হচ্ছে
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    logger.info("Keep-alive server started in the background.")

    # এখন টেলিগ্রাম বটটিকে প্রধান থ্রেডে চালু করা হচ্ছে
    bot_app = Application.builder().token(BOT_TOKEN).post_init(setup_database).build()
    
    # --- এখানে তোমার বটের সব হ্যান্ডলার যোগ করো ---
    bot_app.add_handler(CommandHandler("start", start_command))
    # bot_app.add_handler(CallbackQueryHandler(...)) # বাকিগুলোও যোগ করবে

    logger.info("Telegram Bot starting polling...")
    bot_app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
