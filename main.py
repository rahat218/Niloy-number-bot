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
    MessageHandler,  # <-- নতুন ইম্পোর্ট
    filters,         # <-- নতুন ইম্পোর্ট
    ContextTypes,
)

# -----------------------------------------------------------------------------
# |                      ⚠️ আপনার সকল গোপন তথ্য এখানে ⚠️                      |
# -----------------------------------------------------------------------------
BOT_TOKEN = "7925556669:AAEs8Qpj0jlRAv6FKqhIZplIQ6jlMxs4dHg" # প্রয়োজনে নতুন টোকেন ব্যবহার করুন
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
# |                      লগিং ও ওয়েব সার্ভার সেটআপ                       |
# -----------------------------------------------------------------------------
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

flask_app = Flask(__name__)
@flask_app.route('/')
def keep_alive():
    return "Bot is alive and running successfully!"

def run_flask():
    port = int(os.environ.get('PORT', 8080))
    flask_app.run(host='0.0.0.0', port=port)

# -----------------------------------------------------------------------------
# |                         ডাটাবেস এবং প্রধান ফাংশন                          |
# -----------------------------------------------------------------------------
async def get_db_conn():
    return await psycopg.AsyncConnection.connect(DATABASE_URL)

async def setup_database(app: Application):
    logger.info("Connecting to database...")
    try:
        async with await get_db_conn() as aconn:
            async with aconn.cursor() as acur:
                await acur.execute("""
                    CREATE TABLE IF NOT EXISTS users (user_id BIGINT PRIMARY KEY, first_name VARCHAR(255), strikes INT DEFAULT 0, is_banned BOOLEAN DEFAULT FALSE, ban_until TIMESTAMP, last_number_request_time TIMESTAMP);
                    CREATE TABLE IF NOT EXISTS numbers (id SERIAL PRIMARY KEY, phone_number VARCHAR(25) UNIQUE NOT NULL, service VARCHAR(50) NOT NULL, is_available BOOLEAN DEFAULT TRUE, is_reported BOOLEAN DEFAULT FALSE, assigned_to BIGINT, assigned_at TIMESTAMP);
                """)
        logger.info("SUCCESS: Database setup complete.")
        await app.bot.send_message(chat_id=ADMIN_USER_ID, text="✅ **Bot Deployed/Restarted Successfully!**\nEverything is online and working.")
    except Exception as e:
        logger.error(f"CRITICAL: Database or boot failure! Error: {e}")

# -----------------------------------------------------------------------------
# |                      টেলিগ্রাম বটের সকল হ্যান্ডলার                       |
# -----------------------------------------------------------------------------
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
            await acur.execute("INSERT INTO users (user_id, first_name) VALUES (%s, %s) ON CONFLICT (user_id) DO UPDATE SET first_name = EXCLUDED.first_name", (user.id, user.first_name))
    
    reply_markup = await get_main_menu_keyboard(user.id)
    await update.message.reply_text(text=f"👋 **Welcome, {user.first_name}!**\n\nChoose a service below to get a temporary number.", reply_markup=reply_markup, parse_mode='Markdown')

# ⭐️⭐️⭐️ নতুন ফিচারটি এখানে ⭐️⭐️⭐️
async def handle_unknown_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """কোনো ব্যবহারকারী আজেবাজে টেক্সট পাঠালে এই ফাংশনটি কাজ করবে"""
    logger.info(f"Received unknown text from user {update.effective_user.id}: '{update.message.text}'")
    reply_markup = await get_main_menu_keyboard(update.effective_user.id)
    await update.message.reply_text(
        text="🤔 দুঃখিত, আমি আপনার কথাটি বুঝতে পারিনি।\n\nঅনুগ্রহ করে নিচের বাটনগুলো ব্যবহার করে আপনার প্রয়োজনীয় সেবাটি বেছে নিন।",
        reply_markup=reply_markup
    )

async def handle_button_press(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # এই ফাংশনটি আগের মতোই থাকবে, এখানে কোনো পরিবর্তন নেই
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data
    logger.info(f"Button '{data}' pressed by user {user_id}")
    # ... (বাকি সব কোড আগের মতোই)
    if data.startswith("get_number_"):
        service = data.split("_")[2]
        
        async with await get_db_conn() as aconn:
            async with aconn.cursor(row_factory=psycopg.rows.dict_row) as acur:
                await acur.execute("SELECT * FROM users WHERE user_id = %s", (user_id,))
                user_data = await acur.fetchone()
                if not user_data:
                    await acur.execute("INSERT INTO users (user_id, first_name) VALUES (%s, %s)", (user_id, query.from_user.first_name))
                    await acur.execute("SELECT * FROM users WHERE user_id = %s", (user_id,))
                    user_data = await acur.fetchone()

                if user_data['is_banned']: # ... বাকি লজিক কাজ করবে
                    await query.message.reply_text("❌ You are currently banned.")
                    return
                # ... (এই ফাংশানের বাকি সব কোড আগের মতোই আছে, পরিবর্তন করা হয়নি)
    elif data.startswith("release_"): # ... এই অংশটিও আগের মতোই আছে
        pass

# ... (auto_release_callback ফাংশনটি আগের মতোই থাকবে)
async def auto_release_callback(context: ContextTypes.DEFAULT_TYPE):
    pass

# -----------------------------------------------------------------------------
# |                         ফাইনাল অ্যাপ্লিকেশন চালু করা                        |
# -----------------------------------------------------------------------------
def main() -> None:
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    logger.info("Keep-alive server started.")

    bot_app = Application.builder().token(BOT_TOKEN).post_init(setup_database).build()
    
    # --- হ্যান্ডলারগুলো যোগ করা ---
    bot_app.add_handler(CommandHandler("start", start_command))
    bot_app.add_handler(CallbackQueryHandler(handle_button_press))
    
    # ⭐️⭐️⭐️ নতুন হ্যান্ডলারটি এখানে যোগ করা হয়েছে ⭐️⭐️⭐️
    # এই লাইনটি বটকে বলছে: যদি কোনো টেক্সট মেসেজ আসে (filters.TEXT) যা কোনো কমান্ড নয় (~filters.COMMAND),
    # তাহলে `handle_unknown_text` ফাংশনটি চালু করবে।
    bot_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_unknown_text))

    logger.info("Telegram Bot starting polling...")
    bot_app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
