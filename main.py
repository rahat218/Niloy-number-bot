import logging
import datetime
import traceback
import html
import json
import psycopg
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)
from telegram.constants import ParseMode

# -----------------------------------------------------------------------------
# |                      ⚠️ আপনার সকল গোপন তথ্য এখানে ⚠️                      |
# -----------------------------------------------------------------------------
BOT_TOKEN = "7925556669:AAEs8Qpj0jlRAv6FKqhIZplIQ6jlMxs4dHg"
DATABASE_URL = "postgresql://niloy_number_bot_user:p2pmOrN2Kx7WjiC611qPGk1cVBqEbfeq@dpg-d20ii8nfte5s738v6elg-a/niloy_number_bot"
ADMIN_USER_ID = 7052442701
SUPPORT_USERNAME = "@NgRony"
# নোটিফিকেশন পাওয়ার জন্য অ্যাডমিন চ্যানেল বা আপনার পার্সোনাল আইডি দিন
NOTIFICATION_CHAT_ID = 7052442701 # আমি এখানে আপনার ইউজার আইডি দিয়ে দিলাম

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
# |                নতুন: ক্র্যাশ হলে অ্যাডমিনকে নোটিফিকেশন পাঠানো                 |
# -----------------------------------------------------------------------------
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """যেকোনো এরর বা ক্র্যাশ হলে এই ফাংশনটি কাজ করবে এবং অ্যাডমিনকে জানাবে।"""
    logger.error("Exception while handling an update:", exc_info=context.error)
    tb_list = traceback.format_exception(None, context.error, context.error.__traceback__)
    tb_string = "".join(tb_list)

    update_str = update.to_dict() if isinstance(update, Update) else str(update)
    message = (
        f"🚨 **An exception was raised while handling an update**\n\n"
        f"<pre>update = {html.escape(json.dumps(update_str, indent=2, ensure_ascii=False))}"
        "</pre>\n\n"
        f"<pre>context.chat_data = {html.escape(str(context.chat_data))}</pre>\n\n"
        f"<pre>context.user_data = {html.escape(str(context.user_data))}</pre>\n\n"
        f"<pre>{html.escape(tb_string)}</pre>"
    )
    
    await context.bot.send_message(
        chat_id=NOTIFICATION_CHAT_ID, text=message, parse_mode=ParseMode.HTML
    )

# -----------------------------------------------------------------------------
# |               ডাটাবেস ফাংশন (psycopg লাইব্রেরি দিয়ে)                  |
# -----------------------------------------------------------------------------
async def get_db_conn():
    return await psycopg.AsyncConnection.connect(DATABASE_URL, autocommit=True)

async def setup_database(app: Application):
    """বট চালু হওয়ার সময় স্বয়ংক্রিয়ভাবে ডাটাবেস ও টেবিল তৈরি করবে"""
    logger.info("Connecting to database with 'psycopg' library...")
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
        # নতুন: বট চালু হলে অ্যাডমিনকে মেসেজ পাঠানো
        await app.bot.send_message(chat_id=NOTIFICATION_CHAT_ID, text="✅ **Bot is online and ready!**\n\nSuccessfully connected to the database and all systems are operational.")
    except Exception as e:
        logger.error(f"CRITICAL: Database connection failed! Error: {e}")
        # নতুন: ডাটাবেস কানেক্ট না হলেও যেন অ্যাডমিন জানতে পারে
        await app.bot.send_message(chat_id=NOTIFICATION_CHAT_ID, text=f"❌ **CRITICAL ERROR!**\n\nBot could not connect to the database. Please check Render logs.\n\n**Error:** `{e}`")


# -----------------------------------------------------------------------------
# |                         বটের মূল লজিক (ক্র্যাশ ফিক্সড)                         |
# -----------------------------------------------------------------------------

async def get_main_menu_keyboard(user_id):
    keyboard = [[InlineKeyboardButton("💎 Get Facebook Number", callback_data="get_number_facebook")],
                [InlineKeyboardButton("✈️ Get Telegram Number", callback_data="get_number_telegram")],
                [InlineKeyboardButton("💬 Get WhatsApp Number", callback_data="get_number_whatsapp")],
                [InlineKeyboardButton("📞 Support", url=f"https://t.me/{SUPPORT_USERNAME}"),
                 InlineKeyboardButton("📊 My Stats", callback_data="my_stats")]]
    if user_id == ADMIN_USER_ID:
        keyboard.append([InlineKeyboardButton("👑 Admin Panel 👑", callback_data="admin_panel")])
    return InlineKeyboardMarkup(keyboard)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/start কমান্ড দিলে এই ফাংশন কাজ করবে (ছবি ছাড়া)"""
    user = update.effective_user
    logger.info(f"New user started: {user.first_name} (ID: {user.id})")
    
    async with await get_db_conn() as aconn:
        async with aconn.cursor() as acur:
            await acur.execute("INSERT INTO users (user_id, first_name) VALUES (%s, %s) ON CONFLICT (user_id) DO NOTHING", (user.id, user.first_name))
    
    reply_markup = await get_main_menu_keyboard(user.id)
    # ফিক্স: reply_photo এর পরিবর্তে reply_text ব্যবহার করা হয়েছে, যা কখনো ক্র্যাশ করবে না।
    welcome_text = f"👋 **Welcome, {user.first_name}!**\n\nChoose a service below to get a temporary number for OTP verification."
    await update.message.reply_text(text=welcome_text, reply_markup=reply_markup, parse_mode='Markdown')

# --- (বাকি কোডের কোনো পরিবর্তন নেই, তাই সেগুলো এখানে পুনরাবৃত্তি করছি না) ---
# --- (The rest of the code is unchanged from the previous version) ---
# --- You can copy the functions handle_get_number, handle_release_number, and auto_release_callback from the previous response ---

async def handle_get_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    
    async with await get_db_conn() as aconn:
        async with aconn.cursor() as acur:
            await acur.execute("SELECT * FROM users WHERE user_id = %s", (user_id,))
            user_data = await acur.fetchone()
            
            if not user_data:
                await acur.execute("INSERT INTO users (user_id, first_name) VALUES (%s, %s)", (user_id, query.from_user.first_name))
                user_data = (user_id, query.from_user.first_name, 0, False, None, None)

            user_dict = {'is_banned': user_data[3], 'ban_until': user_data[4], 'last_number_request_time': user_data[5]}

            if user_dict['is_banned'] and user_dict['ban_until'] and datetime.datetime.utcnow() < user_dict['ban_until']:
                await query.edit_message_text(text=f"❌ **You are Banned!**", parse_mode='Markdown')
                return

            if user_dict['last_number_request_time']:
                cooldown_end = user_dict['last_number_request_time'] + datetime.timedelta(minutes=COOLDOWN_MINUTES)
                if datetime.datetime.utcnow() < cooldown_end:
                    await query.answer("⏳ Please wait for the cooldown to finish!", show_alert=True)
                    return
            
            service = query.data.split("_")[2]
            
            await acur.execute("SELECT * FROM numbers WHERE service = %s AND is_available = TRUE AND is_reported = FALSE ORDER BY RANDOM() LIMIT 1 FOR UPDATE", (service,))
            number_record = await acur.fetchone()
            
            if number_record:
                number_id, phone_number = number_record[0], number_record[1]
                now_utc = datetime.datetime.utcnow()
                
                await acur.execute("UPDATE numbers SET is_available = FALSE, assigned_to = %s, assigned_at = %s WHERE id = %s", (user_id, now_utc, number_id))
                await acur.execute("UPDATE users SET last_number_request_time = %s WHERE user_id = %s", (now_utc, user_id))

                keyboard = [[InlineKeyboardButton("✅ OTP Received, Release Now", callback_data=f"release_success_{number_id}")],
                            [InlineKeyboardButton("❌ Report & Get New One", callback_data=f"release_fail_{number_id}")]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await update.effective_message.edit_text(text=f"**Your {service.capitalize()} Number:**\n\n`{phone_number}`\n\n_This number is yours for {LEASE_TIME_MINUTES} minutes._", reply_markup=reply_markup, parse_mode='Markdown')
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
                await acur.execute("SELECT phone_number, service FROM numbers WHERE id = %s", (number_id,))
                number_info = await acur.fetchone()
                report_message = f"🚨 **Number Reported!**\nUser: `{user_id}`\nNumber: `{number_info[0]}` ({number_info[1]})"
                await context.bot.send_message(NOTIFICATION_CHAT_ID, report_message, parse_mode='Markdown')
                await query.message.edit_text(text="📝 **Number Reported!**\n\nYou can now request a new number.", reply_markup=await get_main_menu_keyboard(user_id), parse_mode='Markdown')

    current_jobs = context.job_queue.get_jobs_by_name(f"release_{user_id}")
    for job in current_jobs:
        job.schedule_removal()

async def auto_release_callback(context: ContextTypes.DEFAULT_TYPE):
    job_data = context.job.data
    user_id, number_id, number_str = job_data['user_id'], job_data['number_id'], job_data['number_str']

    logger.warning(f"Lease expired for user {user_id}. Applying strike.")
    async with await get_db_conn() as aconn:
        async with aconn.cursor() as acur:
            await acur.execute("UPDATE numbers SET is_available = TRUE, assigned_to = NULL, assigned_at = NULL WHERE id = %s", (number_id,))
            await acur.execute("UPDATE users SET strikes = strikes + 1 WHERE user_id = %s RETURNING strikes", (user_id,))
            result = await acur.fetchone()
            new_strikes = result[0] if result else 0

            admin_message = f"⏰ **Lease Expired & Strike!**\nUser: `{user_id}`\nStrikes: **{new_strikes}/{MAX_STRIKES}**."
            await context.bot.send_message(NOTIFICATION_CHAT_ID, admin_message, parse_mode='Markdown')

            if new_strikes >= MAX_STRIKES:
                ban_until = datetime.datetime.utcnow() + datetime.timedelta(hours=BAN_HOURS)
                await acur.execute("UPDATE users SET is_banned = TRUE, ban_until = %s, strikes = 0 WHERE user_id = %s", (ban_until, user_id))
                await context.bot.send_message(user_id, f"❌ **You are BANNED for {BAN_HOURS} hours!**")
            else:
                await context.bot.send_message(user_id, f"⚠️ **Number Expired!**\nYou received 1 strike. Total: `{new_strikes}/{MAX_STRIKES}`.")


# -----------------------------------------------------------------------------
# |                           অ্যাপ্লিকেশন চালু করা                          |
# -----------------------------------------------------------------------------
def main() -> None:
    app = Application.builder().token(BOT_TOKEN).post_init(setup_database).build()
    
    # নতুন: এরর হ্যান্ডলার যোগ করা
    app.add_error_handler(error_handler)
    
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CallbackQueryHandler(handle_get_number, pattern="^get_number_"))
    app.add_handler(CallbackQueryHandler(handle_release_number, pattern="^release_"))
    
    logger.info("BOT IS STARTING... Final version.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
