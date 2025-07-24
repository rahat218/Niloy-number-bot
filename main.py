import logging
import datetime
import os
import psycopg
from threading import Thread
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
# |         RENDER-কে সচল রাখার জন্য নতুন ওয়েব সার্ভার অংশ (মুখোশ)            |
# -----------------------------------------------------------------------------
web_app = Flask(__name__)

@web_app.route('/')
def index():
    return "Bot is alive and running!"

def run_web_server():
    # Render তার নিজের জন্য একটি PORT ভেরিয়েবল সেট করে, আমরা সেটি ব্যবহার করব
    port = int(os.environ.get("PORT", 8080))
    web_app.run(host='0.0.0.0', port=port)

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
                # টেবিল তৈরির কোড আগের মতোই থাকবে
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
# |             বটের মূল লজিক (এখানে কোনো পরিবর্তন নেই)                       |
# -----------------------------------------------------------------------------

async def get_main_menu_keyboard(user_id):
    keyboard = [
        [InlineKeyboardButton("💎 Get Facebook Number", callback_data="get_number_facebook")],
        [InlineKeyboardButton("✈️ Get Telegram Number", callback_data="get_number_telegram")],
        [InlineKeyboardButton("💬 Get WhatsApp Number", callback_data="get_number_whatsapp")],
        [InlineKeyboardButton("📞 Support", url=f"https://t.me/{SUPPORT_USERNAME}")],
    ]
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
    await update.message.reply_photo(
        photo="https://telegra.ph/file/02194911f26a7962c454e.jpg",
        caption=f"👋 **Welcome, {user.first_name}!**\n\nChoose a service to get a number.",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

# ... (বাকি সব ফাংশন যেমন handle_get_number, handle_release_number, auto_release_callback আগের মতোই থাকবে) ...
# হ্যান্ডলার ফাংশনগুলো আগের কোড থেকে কপি করে এখানে পেস্ট করা যেতে পারে অথবা এখানে পুনরায় লেখা যেতে পারে।
# সুবিধার জন্য, আমি এখানে মূল ফাংশনগুলো আবার দিয়ে দিচ্ছি।

async def handle_get_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    
    async with await get_db_conn() as aconn:
        async with aconn.cursor() as acur:
            await acur.execute("SELECT is_banned, ban_until, last_number_request_time FROM users WHERE user_id = %s", (user_id,))
            user_data = await acur.fetchone()
            
            if not user_data:
                await acur.execute("INSERT INTO users (user_id, first_name) VALUES (%s, %s) ON CONFLICT (user_id) DO NOTHING", (user_id, query.from_user.first_name))
                user_data = (False, None, None)

            is_banned, ban_until, last_request_time = user_data

            if is_banned and ban_until and datetime.datetime.utcnow() < ban_until:
                await query.edit_message_caption(caption="❌ **You are Banned!**", parse_mode='Markdown')
                return

            if last_request_time:
                cooldown_end = last_request_time + datetime.timedelta(minutes=COOLDOWN_MINUTES)
                if datetime.datetime.utcnow() < cooldown_end:
                    await query.answer("⏳ Cooldown active!", show_alert=True)
                    return
            
            service = query.data.split("_")[2]
            
            await acur.execute("SELECT id, phone_number FROM numbers WHERE service = %s AND is_available = TRUE AND is_reported = FALSE ORDER BY RANDOM() LIMIT 1 FOR UPDATE", (service,))
            number_record = await acur.fetchone()
            
            if number_record:
                number_id, phone_number = number_record
                now_utc = datetime.datetime.utcnow()
                await acur.execute("UPDATE numbers SET is_available = FALSE, assigned_to = %s, assigned_at = %s WHERE id = %s", (user_id, now_utc, number_id))
                await acur.execute("UPDATE users SET last_number_request_time = %s WHERE user_id = %s", (now_utc, user_id))

                keyboard = [[InlineKeyboardButton("✅ OTP Received, Release", callback_data=f"release_success_{number_id}")],
                            [InlineKeyboardButton("❌ Report & Get New", callback_data=f"release_fail_{number_id}")]]
                await query.edit_message_caption(caption=f"**Your {service.capitalize()} Number:**\n`{phone_number}`", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
                context.job_queue.run_once(auto_release_callback, LEASE_TIME_MINUTES * 60, data={'user_id': user_id, 'number_id': number_id, 'number_str': phone_number}, name=f"release_{user_id}")
            else:
                await query.answer(f"No numbers available for {service.capitalize()}", show_alert=True)

async def handle_release_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    action, status, number_id_str = query.data.split("_")
    number_id = int(number_id_str)

    async with await get_db_conn() as aconn:
        async with aconn.cursor() as acur:
            if status == "success":
                await query.answer("✅ Released!", show_alert=True)
                await acur.execute("UPDATE numbers SET is_available = TRUE, assigned_to = NULL WHERE id = %s", (number_id,))
                await acur.execute("UPDATE users SET strikes = 0 WHERE user_id = %s", (user_id,))
                await query.edit_message_caption(caption="✅ **Number Released!** Strikes cleared.", reply_markup=await get_main_menu_keyboard(user_id), parse_mode='Markdown')
            elif status == "fail":
                await query.answer("📝 Reporting...", show_alert=True)
                await acur.execute("UPDATE numbers SET is_available = TRUE, assigned_to = NULL, is_reported = TRUE WHERE id = %s", (number_id,))
                await query.edit_message_caption(caption="📝 **Number Reported!**", reply_markup=await get_main_menu_keyboard(user_id), parse_mode='Markdown')

    current_jobs = context.job_queue.get_jobs_by_name(f"release_{user_id}")
    for job in current_jobs:
        job.schedule_removal()

async def auto_release_callback(context: ContextTypes.DEFAULT_TYPE):
    job_data = context.job.data
    user_id, number_id = job_data['user_id'], job_data['number_id']
    logger.warning(f"Lease expired for user {user_id}. Applying strike.")
    async with await get_db_conn() as aconn:
        async with aconn.cursor() as acur:
            await acur.execute("UPDATE numbers SET is_available = TRUE, assigned_to = NULL WHERE id = %s", (number_id,))
            await acur.execute("UPDATE users SET strikes = strikes + 1 WHERE user_id = %s RETURNING strikes", (user_id,))
            result = await acur.fetchone()
            new_strikes = result[0] if result else 0

            if new_strikes >= MAX_STRIKES:
                ban_until = datetime.datetime.utcnow() + datetime.timedelta(hours=BAN_HOURS)
                await acur.execute("UPDATE users SET is_banned = TRUE, ban_until = %s, strikes = 0 WHERE user_id = %s", (ban_until, user_id))
                await context.bot.send_message(user_id, f"❌ **BANNED for {BAN_HOURS} hours!**")
            else:
                await context.bot.send_message(user_id, f"⚠️ **Lease Expired!** 1 strike added. Total: {new_strikes}/{MAX_STRIKES}")


# -----------------------------------------------------------------------------
# |                 ফাইনাল অ্যাপ্লিকেশন চালু করার নতুন নিয়ম                     |
# -----------------------------------------------------------------------------
def main() -> None:
    # ধাপ ১: ওয়েব সার্ভারটিকে একটি আলাদা থ্রেডে (Thread) চালু করা
    # এর ফলে এটি মূল বটকে কোনোভাবে বাধা দেবে না
    web_thread = Thread(target=run_web_server)
    web_thread.start()
    
    # ধাপ ২: টেলিগ্রাম বট অ্যাপ্লিকেশন তৈরি করা
    app = Application.builder().token(BOT_TOKEN).post_init(setup_database).build()
    
    # ধাপ ৩: আগের মতোই সব হ্যান্ডলার যোগ করা
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CallbackQueryHandler(handle_get_number, pattern="^get_number_"))
    app.add_handler(CallbackQueryHandler(handle_release_number, pattern="^release_"))
    
    # ধাপ ৪: বটটিকে পোলিং মোডে চালু করা
    logger.info("Bot polling has started...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
