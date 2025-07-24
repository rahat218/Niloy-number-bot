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
BOT_TOKEN = "7925556669:AAE5F9zUGOK37niSd0x-YEQX8rn-xGd8Pl8"
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
# |       বটকে ২৪/৭ জাগিয়ে রাখার জন্য ওয়েব সার্ভার (Flask)      |
# -----------------------------------------------------------------------------
flask_app = Flask(__name__)

@flask_app.route('/')
def keep_alive():
    """এই ফাংশনটি UptimeRobot কে বলবে যে বট বেঁচে আছে।"""
    return "Bot is alive and running successfully!"

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
        # বট চালু হওয়ার পর অ্যাডমিনকে একটি মেসেজ পাঠানো হবে
        await app.bot.send_message(chat_id=ADMIN_USER_ID, text="✅ Bot has started successfully and is now online!")
    except Exception as e:
        logger.error(f"CRITICAL: Database connection or initial boot failed! Error: {e}")

# -----------------------------------------------------------------------------
# |              টেলিগ্রাম বটের সকল ফাংশন (সম্পূর্ণ এবং নির্ভুল)               |
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
            await acur.execute("INSERT INTO users (user_id, first_name) VALUES (%s, %s) ON CONFLICT (user_id) DO NOTHING", (user.id, user.first_name))
    
    reply_markup = await get_main_menu_keyboard(user.id)
    # ছবির বদলে টেক্সট পাঠানো হচ্ছে, যা কোনোদিন ফেইল করবে না
    await update.message.reply_text(
        text=f"👋 **Welcome, {user.first_name}!**\n\nChoose a service below to get a temporary number.",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

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

            is_banned, ban_until, last_req_time = user_data

            if is_banned and ban_until and datetime.datetime.utcnow() < ban_until:
                await query.message.reply_text(f"❌ **You are Banned!**")
                return

            if last_req_time:
                cooldown_end = last_req_time + datetime.timedelta(minutes=COOLDOWN_MINUTES)
                if datetime.datetime.utcnow() < cooldown_end:
                    await query.answer("⏳ Please wait for the cooldown to finish!", show_alert=True)
                    return
            
            service = query.data.split("_")[2]
            
            await acur.execute("SELECT id, phone_number FROM numbers WHERE service = %s AND is_available = TRUE AND is_reported = FALSE ORDER BY RANDOM() LIMIT 1 FOR UPDATE", (service,))
            number_record = await acur.fetchone()
            
            if number_record:
                number_id, phone_number = number_record
                now_utc = datetime.datetime.utcnow()
                
                await acur.execute("UPDATE numbers SET is_available = FALSE, assigned_to = %s, assigned_at = %s WHERE id = %s", (user_id, now_utc, number_id))
                await acur.execute("UPDATE users SET last_number_request_time = %s WHERE user_id = %s", (now_utc, user_id))

                keyboard = [[InlineKeyboardButton("✅ OTP Received, Release Now", callback_data=f"release_success_{number_id}")],
                            [InlineKeyboardButton("❌ Report & Get New One", callback_data=f"release_fail_{number_id}")]]
                await query.message.edit_text(text=f"**Your {service.capitalize()} Number:**\n\n`{phone_number}`", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
                
                context.job_queue.run_once(auto_release_callback, LEASE_TIME_MINUTES * 60, data={'user_id': user_id, 'number_id': number_id, 'number_str': phone_number}, name=f"release_{user_id}")
            else:
                await query.answer(f"Sorry, no numbers available for {service.capitalize()} right now.", show_alert=True)

async def handle_release_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    action, status, number_id_str = query.data.split("_")
    number_id = int(number_id_str)
    
    async with await get_db_conn() as aconn:
        async with aconn.cursor() as acur:
            if status == "success":
                await query.answer("✅ Great! Releasing number...", show_alert=True)
                await acur.execute("UPDATE numbers SET is_available = TRUE, assigned_to = NULL, assigned_at = NULL WHERE id = %s", (number_id,))
                await acur.execute("UPDATE users SET strikes = 0 WHERE user_id = %s", (user_id,))
                await query.message.edit_text(text="✅ **Number Released!**\n\nYour strikes have been cleared.", reply_markup=await get_main_menu_keyboard(user_id), parse_mode='Markdown')
            
            elif status == "fail":
                await query.answer("📝 Reporting number...", show_alert=True)
                await acur.execute("UPDATE numbers SET is_available = TRUE, assigned_to = NULL, is_reported = TRUE WHERE id = %s", (number_id,))
                await query.message.edit_text(text="📝 **Number Reported!**\n\nYou can now request a new number.", reply_markup=await get_main_menu_keyboard(user_id), parse_mode='Markdown')

    current_jobs = context.job_queue.get_jobs_by_name(f"release_{user_id}")
    for job in current_jobs:
        job.schedule_removal()

async def auto_release_callback(context: ContextTypes.DEFAULT_TYPE):
    job_data, user_id, number_id = context.job.data, context.job.data['user_id'], context.job.data['number_id']
    logger.warning(f"Lease expired for user {user_id}. Applying strike.")
    async with await get_db_conn() as aconn:
        async with aconn.cursor() as acur:
            await acur.execute("UPDATE numbers SET is_available = TRUE, assigned_to = NULL, assigned_at = NULL WHERE id = %s", (number_id,))
            await acur.execute("UPDATE users SET strikes = strikes + 1 WHERE user_id = %s RETURNING strikes", (user_id,))
            new_strikes = (await acur.fetchone() or (0,))[0]

            if new_strikes >= MAX_STRIKES:
                ban_until = datetime.datetime.utcnow() + datetime.timedelta(hours=BAN_HOURS)
                await acur.execute("UPDATE users SET is_banned = TRUE, ban_until = %s, strikes = 0 WHERE user_id = %s", (ban_until, user_id))
                await context.bot.send_message(user_id, f"❌ **You are BANNED for {BAN_HOURS} hours!**")
            else:
                await context.bot.send_message(user_id, f"⚠️ **Number Expired!**\nYou received 1 strike.")

# -----------------------------------------------------------------------------
# |                         ফাইনাল অ্যাপ্লিকেশন চালু করা                        |
# -----------------------------------------------------------------------------
def main() -> None:
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    logger.info("Keep-alive server started in the background.")

    bot_app = Application.builder().token(BOT_TOKEN).post_init(setup_database).build()
    
    bot_app.add_handler(CommandHandler("start", start_command))
    bot_app.add_handler(CallbackQueryHandler(handle_get_number, pattern="^get_number_"))
    bot_app.add_handler(CallbackQueryHandler(handle_release_number, pattern="^release_"))

    logger.info("Telegram Bot starting polling...")
    bot_app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
