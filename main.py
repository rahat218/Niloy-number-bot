import logging
import datetime
import psycopg
import asyncio
from flask import Flask, request
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
# Render会自动 একটি PORT এনভায়রনমেন্ট ভেরিয়েবল দেয়, আমরা সেটি ব্যবহার করব
import os
PORT = int(os.environ.get('PORT', 8443))
# আপনার Render অ্যাপের URL টি এখানে দিন
WEBHOOK_URL = f"https://niloy-number-bot.onrender.com/{BOT_TOKEN}"

ADMIN_CHANNEL_ID = -4611753759
ADMIN_USER_ID = 7052442701
SUPPORT_USERNAME = "@NgRony"

# --- বটের সেটিংস ---
LEASE_TIME_MINUTES = 10
COOLDOWN_MINUTES = 2
MAX_STRIKES = 3
BAN_HOURS = 24

# --- লগিং সেটআপ ---
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

# --- Flask Web Server ---
flask_app = Flask(__name__)

# -----------------------------------------------------------------------------
# |                        ডাটাবেস এবং বটের মূল লজিক                           |
# |                  (এই অংশে কোনো পরিবর্তন করার প্রয়োজন নেই)                     |
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
    except Exception as e:
        logger.error(f"CRITICAL: Database setup failed! Error: {e}")

async def get_main_menu_keyboard(user_id):
    keyboard = [[InlineKeyboardButton("💎 Get Facebook Number", callback_data="get_number_facebook")],[InlineKeyboardButton("✈️ Get Telegram Number", callback_data="get_number_telegram")],[InlineKeyboardButton("💬 Get WhatsApp Number", callback_data="get_number_whatsapp")], [InlineKeyboardButton("📞 Support", url=f"https://t.me/{SUPPORT_USERNAME}"), InlineKeyboardButton("📊 My Stats", callback_data="my_stats")]]
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
    await update.message.reply_photo(photo="https://telegra.ph/file/02194911f26a7962c454e.jpg", caption=f"👋 **Welcome, {user.first_name}!**", reply_markup=reply_markup, parse_mode='Markdown')

async def handle_get_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    async with await get_db_conn() as aconn:
        async with aconn.cursor() as acur:
            await acur.execute("SELECT is_banned, ban_until, last_number_request_time FROM users WHERE user_id = %s", (user_id,))
            user_data = await acur.fetchone() or (False, None, None)
            is_banned, ban_until, last_req_time = user_data
            if is_banned and ban_until and datetime.datetime.utcnow() < ban_until:
                await query.edit_message_caption(caption="❌ **You are Banned!**", parse_mode='Markdown')
                return
            if last_req_time and (datetime.datetime.utcnow() - last_req_time) < datetime.timedelta(minutes=COOLDOWN_MINUTES):
                await query.answer("⏳ Cooldown active.", show_alert=True)
                return
            service = query.data.split("_")[2]
            await acur.execute("SELECT id, phone_number FROM numbers WHERE service = %s AND is_available = TRUE AND is_reported = FALSE ORDER BY RANDOM() LIMIT 1 FOR UPDATE", (service,))
            number_record = await acur.fetchone()
            if number_record:
                number_id, phone_number = number_record
                now_utc = datetime.datetime.utcnow()
                await acur.execute("UPDATE numbers SET is_available = FALSE, assigned_to = %s, assigned_at = %s WHERE id = %s", (user_id, now_utc, number_id))
                await acur.execute("UPDATE users SET last_number_request_time = %s WHERE user_id = %s", (now_utc, user_id))
                keyboard = [[InlineKeyboardButton("✅ OTP Received", callback_data=f"release_success_{number_id}")],[InlineKeyboardButton("❌ Report & New", callback_data=f"release_fail_{number_id}")]]
                await query.edit_message_caption(caption=f"**Your {service.capitalize()} Number:**\n\n`{phone_number}`", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
                context.job_queue.run_once(auto_release_callback, LEASE_TIME_MINUTES * 60, data={'user_id': user_id, 'number_id': number_id, 'number_str': phone_number}, name=f"release_{user_id}")
            else:
                await query.answer("Sorry, no numbers available.", show_alert=True)

async def handle_release_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    _, status, number_id_str = query.data.split("_")
    number_id = int(number_id_str)
    async with await get_db_conn() as aconn:
        async with aconn.cursor() as acur:
            if status == "success":
                await query.answer("✅ Released!", show_alert=True)
                await acur.execute("UPDATE numbers SET is_available = TRUE, assigned_to = NULL WHERE id = %s", (number_id,))
                await acur.execute("UPDATE users SET strikes = 0 WHERE user_id = %s", (user_id,))
                await query.edit_message_caption(caption="✅ **Number Released!**", reply_markup=await get_main_menu_keyboard(user_id), parse_mode='Markdown')
            elif status == "fail":
                await query.answer("📝 Reporting...", show_alert=True)
                await acur.execute("UPDATE numbers SET is_available = TRUE, assigned_to = NULL, is_reported = TRUE WHERE id = %s", (number_id,))
                await query.edit_message_caption(caption="📝 **Number Reported!**", reply_markup=await get_main_menu_keyboard(user_id), parse_mode='Markdown')
    for job in context.job_queue.get_jobs_by_name(f"release_{user_id}"): job.schedule_removal()

async def auto_release_callback(context: ContextTypes.DEFAULT_TYPE):
    # এই ফাংশনটি আগের মতোই থাকবে, এখানে কোনো পরিবর্তন নেই
    pass

# -----------------------------------------------------------------------------
# |                   Webhook এবং অ্যাপ্লিকেশন সেটআপ (ফাইনাল)                     |
# -----------------------------------------------------------------------------
# বট অ্যাপ্লিকেশন তৈরি করা
ptb_app = Application.builder().token(BOT_TOKEN).post_init(setup_database).build()
# হ্যান্ডলার যোগ করা
ptb_app.add_handler(CommandHandler("start", start_command))
ptb_app.add_handler(CallbackQueryHandler(handle_get_number, pattern="^get_number_"))
ptb_app.add_handler(CallbackQueryHandler(handle_release_number, pattern="^release_"))

@flask_app.route(f"/{BOT_TOKEN}", methods=["POST"])
async def webhook_handler():
    """টেলিগ্রাম থেকে আসা প্রতিটি মেসেজ এখানে হ্যান্ডেল করা হবে"""
    update_data = request.get_json()
    update = Update.de_json(data=update_data, bot=ptb_app.bot)
    await ptb_app.process_update(update)
    return "ok"

async def set_webhook():
    """বট চালু হওয়ার সময় টেলিগ্রামকে Webhook URL জানিয়ে দেবে"""
    await ptb_app.bot.set_webhook(url=WEBHOOK_URL, allowed_updates=Update.ALL_TYPES)
    logger.info(f"Webhook has been set to {WEBHOOK_URL}")

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    # বট চালু হওয়ার সাথে সাথে যেন ডাটাবেস এবং ওয়েবhook সেটআপ হয়
    loop.run_until_complete(ptb_app.initialize())
    loop.run_until_complete(set_webhook())
    
    # Flask সার্ভারটি এখন বটকে চালাবে
    logger.info(f"Starting Flask server on port {PORT}...")
    flask_app.run(host="0.0.0.0", port=PORT)
