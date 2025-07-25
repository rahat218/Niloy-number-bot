import logging
import datetime
import pytz
import psycopg
import psycopg.rows
import asyncio
import threading
import os
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    Application,
    ConversationHandler,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
from telegram.constants import ParseMode
from telegram.error import Forbidden, BadRequest, Conflict # Conflict এখানে ইম্পোর্ট করা হয়েছে

# -----------------------------------------------------------------------------
# |                      ⚠️ আপনার সকল গোপন তথ্য এখানে ⚠️                      |
# -----------------------------------------------------------------------------
BOT_TOKEN = "7925556669:AAE5F9zUGOK37niSd0x-YEQX8rn-xGd8Pl8"
DATABASE_URL = "postgresql://niloy_number_bot_user:p2pmOrN2Kx7WjiC611qPGk1cVBqEbfeq@dpg-d20ii8nfte5s738v6elg-a/niloy_number_bot"
ADMIN_USER_ID = 7052442701
SUPPORT_USERNAME = "@NgRony"

# --- বটের সেটিংস ---
MAX_STRIKES = 3
BAN_HOURS = 24
NUMBER_EXPIRATION_MINUTES = 5 
USER_COOLDOWN_SECONDS = 120 

# --- বাটন টেক্সট ---
GET_NUMBER_TEXT = "✨ Get Number 🎗️"
MY_STATS_TEXT = "📊 My Stats"
SUPPORT_TEXT = "📞 Support"
LANGUAGE_TEXT = "🌐 Language"
ADMIN_PANEL_TEXT = "👑 Admin Panel 👑"

# --- Conversation States ---
ADDING_NUMBERS = 1
BROADCAST_MESSAGE = 2

# --- সম্পূর্ণ বহুভাষিক টেক্সট ---
LANG_TEXT = {
    'bn': {
        "welcome": "👋 **স্বাগতম, {first_name}!**\n\nনিচের কীবোর্ড থেকে একটি অপশন বেছে নিন।",
        "choose_service": "🔢 কোন সার্ভিসের জন্য নম্বর প্রয়োজন? অনুগ্রহ করে বেছে নিন:",
        "stats_header": "📊 **আপনার পরিসংখ্যান**", "strikes": "স্ট্রাইক",
        "status_banned": "অ্যাকাউন্ট স্ট্যাটাস: {time_left} পর আপনার ব্যান রিমুভ হবে।",
        "status_normal": "স্ট্যাটাস: সাধারণ ব্যবহারকারী", "stats_not_found": "আপনার পরিসংখ্যান খুঁজে পাওয়া যায়নি।",
        "support_prompt": "📞 সাপোর্টের জন্য নিচের বাটনে ক্লিক করুন।", "support_button": "সাপোর্টে যোগাযোগ করুন",
        "unknown_command": "🤔 দুঃখিত, কমান্ডটি বুঝতে পারিনি।", "choose_language": "অনুগ্রহ করে আপনার ভাষা নির্বাচন করুন:",
        "lang_changed": "✅ আপনার ভাষা সফলভাবে 'বাংলা' করা হয়েছে।", "searching_number": "🔍 আপনার জন্য একটি **{service}** নম্বর খোঁজা হচ্ছে...",
        "no_number_available": "❌ **দুঃখিত, এই মুহূর্তে নম্বর শেষ!** ❌\n\nঅ্যাডমিন খুব শীঘ্রই নতুন নম্বর যোগ করবেন।\n⏳ অনুগ্রহ করে কিছুক্ষণ পর আবার চেষ্টা করুন।",
        "new_numbers_broadcast": "🎉 **সুখবর! নতুন নম্বর যোগ করা হয়েছে!** 🎉\n\n**তারিখ:** {date}\n\nএখনই আপনার প্রয়োজনীয় নম্বরটি নিয়ে নিন!",
        "admin_panel_welcome": "👑 **অ্যাডমিন প্যানেলে স্বাগতম** 👑", "guideline_title": "📜 **অ্যাডমিন গাইডলাইন** 📜",
        "guideline_text": "`➕ নম্বর যোগ করুন`\n`/add` বা বাটন ক্লিক করে, প্রতি লাইনে একটি করে নম্বর ও সার্ভিস কমা দিয়ে পাঠান।\n*উদাহরণ:* `+880...,Facebook`\n\n`🗑️ নম্বর মুছুন`\n`/delnumber [নম্বর]`\n\n`♻️ নম্বর রিভিউ`\n`/view_reported` - রিপোর্ট হওয়া নম্বর দেখুন।\n`/view_expired` - অব্যবহৃত নম্বর দেখুন।\n`/reactivate [নম্বর]` - নম্বর পুনরায় ব্যবহারযোগ্য করুন।\n\n`📣 ঘোষণা দিন`\n`/broadcast` বা বাটন ক্লিক করুন।\n\n`🗑️ ঘোষণা মুছুন`\n`/delbroadcast` - সর্বশেষ ঘোষণা মুছুন।\n\n`🚫 ব্যান/আনব্যান`\n`/ban [User ID]`\n`/unban [User ID]`",
        "ask_for_numbers": "✍️ নম্বরগুলো পাঠান। ফরম্যাট: `+12345,Facebook`",
        "numbers_added_success": "✅ সফলভাবে {count} টি নতুন নম্বর যোগ করা হয়েছে।",
        "numbers_added_fail": "❌ কোনো বৈধ নম্বর পাওয়া যায়নি।",
        "user_banned_success": "✅ ব্যবহারকারী {user_id} কে ব্যান করা হয়েছে।",
        "user_unbanned_success": "✅ ব্যবহারকারী {user_id} কে আনব্যান করা হয়েছে।",
        "user_not_found": "❌ ব্যবহারকারী {user_id} কে খুঁজে পাওয়া যায়নি।",
        "broadcast_sent": "✅ বার্তাটি {count} জন ব্যবহারকারীকে পাঠানো হয়েছে।",
        "broadcast_no_message": "❌ /broadcast কমান্ডের সাথে একটি বার্তা দিন।",
        "ask_broadcast_message": "📣 আপনার ঘোষণার বার্তাটি পাঠান:",
        "broadcast_deleted": "✅ সর্বশেষ ঘোষণাটি সফলভাবে মুছে ফেলা হয়েছে।",
        "admin_announcement": "📣 অ্যাডমিনের ঘোষণা 📣", "back_button": "⬅️ পিছনে",
        "number_message": "আপনার নম্বরটি হলো: `{number}`\n\nএই নম্বরটি **{minutes} মিনিট** পর অটো রিলিজ হয়ে যাবে। অনুগ্রহ করে দ্রুত কাজ সম্পন্ন করুন।",
        "otp_received_button": "✅ OTP পেয়েছি", "otp_not_received_button": "❌ OTP আসেনি",
        "number_released": "✅ ধন্যবাদ! আপনার নম্বরটি সফলভাবে রিলিজ করা হয়েছে।",
        "number_reported": "⚠️ নম্বরটি রিপোর্ট করার জন্য ধন্যবাদ। আমরা আপনাকে একটি নতুন নম্বর দিচ্ছি।",
        "cooldown_message": "🚫 আপনি খুব দ্রুত অনুরোধ করছেন। অনুগ্রহ করে {seconds} সেকেন্ড পর আবার চেষ্টা করুন।",
        "user_is_banned": "🚫 **আপনার অ্যাকাউন্ট ব্যান করা হয়েছে।**\nআপনি আমাদের নীতি ভঙ্গ করার কারণে বট ব্যবহার করতে পারবেন না।\n\n**কারণ:** স্প্যামিং।\nব্যানের সময়সীমা শেষ হলে আবার চেষ্টা করুন।",
        "strike_warning_1": "⚠️ **সতর্কবার্তা (স্ট্রাইক ১/৩)!**\nআপনি আপনার নেওয়া নম্বরটি `{number}` নির্দিষ্ট সময়ের মধ্যে ব্যবহার করেননি। অনুগ্রহ করে পরেরবার সতর্ক থাকবেন।",
        "strike_warning_2": "🚨 **চূড়ান্ত সতর্কবার্তা (স্ট্রাইক ২/৩)!**\nআপনি আবারও একটি নম্বর ব্যবহার না করে ফেলে রেখেছেন। আর একবার এই ভুল করলেই আপনার অ্যাকাউন্ট **{ban_hours} ঘণ্টার জন্য ব্যান** করা হবে।",
        "strike_ban_message": "🚫 **অ্যাকাউন্ট ব্যান!**\nআপনি বারবার সতর্কবার্তা উপেক্ষা করে নম্বর অপচয় করার কারণে, আমাদের সিস্টেম আপনাকে **{ban_hours} ঘণ্টার জন্য ব্যান** করেছে। এই সময়ের পর আপনার অ্যাকাউন্ট স্বয়ংক্রিয়ভাবে সচল হয়ে যাবে।",
        "number_deleted_success": "✅ নম্বর `{number}` সফলভাবে মুছে ফেলা হয়েছে।",
        "number_not_found_db": "❌ নম্বর `{number}` ডাটাবেসে খুঁজে পাওয়া যায়নি।",
        "number_reactivated_success": "✅ নম্বর `{number}` পুনরায় ব্যবহারযোগ্য করা হয়েছে।",
        "no_reported_numbers": "👍 কোনো রিপোর্ট করা নম্বর নেই।",
        "reported_numbers_header": "--- রিপোর্ট করা নম্বর ---",
        "no_expired_numbers": "👍 কোনো অব্যবহৃত/মেয়াদোত্তীর্ণ নম্বর নেই।",
        "expired_numbers_header": "--- মেয়াদোত্তীর্ণ নম্বর ---",
    }
}
en_text = {k: v.replace('বাংলা', 'English').replace('বাংলায়', 'English') for k, v in LANG_TEXT['bn'].items()}
LANG_TEXT['en'] = en_text

# -----------------------------------------------------------------------------
# |                      লগিং ও সার্ভার সেটআপ                       |
# -----------------------------------------------------------------------------
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("telegram.ext").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

flask_app = Flask(__name__)
@flask_app.route('/')
def keep_alive(): return "Bot is alive!"
def run_flask(): flask_app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))

# -----------------------------------------------------------------------------
# |                         ডাটাবেস এবং প্রধান ফাংশন                          |
# -----------------------------------------------------------------------------
async def get_db_conn():
    return await psycopg.AsyncConnection.connect(DATABASE_URL)

async def setup_database(app: Application):
    logger.info("Verifying database schema...")
    try:
        async with await get_db_conn() as aconn:
            async with aconn.cursor() as acur:
                await acur.execute("""
                    CREATE TABLE IF NOT EXISTS users (
                        user_id BIGINT PRIMARY KEY, first_name VARCHAR(255), strikes INT DEFAULT 0,
                        is_banned BOOLEAN DEFAULT FALSE, ban_until TIMESTAMP WITH TIME ZONE,
                        language VARCHAR(5) DEFAULT 'bn', last_broadcast_id BIGINT,
                        cooldown_until TIMESTAMP WITH TIME ZONE
                    );
                    CREATE TABLE IF NOT EXISTS numbers (
                        id SERIAL PRIMARY KEY, phone_number VARCHAR(25) UNIQUE NOT NULL,
                        service VARCHAR(50) NOT NULL, status VARCHAR(20) DEFAULT 'available',
                        assigned_to_id BIGINT, assigned_at TIMESTAMP WITH TIME ZONE, message_id BIGINT
                    );
                    CREATE INDEX IF NOT EXISTS numbers_status_service_idx ON numbers (status, service);
                """)
        logger.info("SUCCESS: Database schema is up-to-date.")
        await app.bot.send_message(chat_id=ADMIN_USER_ID, text="✅ **Bot Deployed/Restarted Successfully!**", parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        logger.error(f"CRITICAL: Database setup failed! Error: {e}")

async def get_user_lang(user_id: int) -> str:
    try:
        async with await get_db_conn() as aconn:
            async with aconn.cursor() as acur:
                await acur.execute("SELECT language FROM users WHERE user_id = %s", (user_id,))
                result = await acur.fetchone()
                return result[0] if result and result[0] else 'bn'
    except Exception: return 'bn'

# -----------------------------------------------------------------------------
# |                কীবোর্ড এবং মেনু তৈরির ফাংশন                |
# -----------------------------------------------------------------------------
def get_main_reply_keyboard(user_id: int):
    keyboard = [[GET_NUMBER_TEXT], [MY_STATS_TEXT, SUPPORT_TEXT, LANGUAGE_TEXT]]
    if user_id == ADMIN_USER_ID: keyboard.append([ADMIN_PANEL_TEXT])
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, input_field_placeholder="Choose an option...")

# -----------------------------------------------------------------------------
# |                        AUTOMATED JOBS & ERROR HANDLER (নতুন)                 |
# -----------------------------------------------------------------------------
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log the error and handle Conflict errors by shutting down."""
    if isinstance(context.error, Conflict):
        logger.warning("Conflict error detected. Another instance is running. Shutting down this instance.")
        # os._exit(1) forcefully stops the current process. This is the most effective
        # way to kill a "zombie" instance on platforms like Render's free tier.
        os._exit(1)
    else:
        logger.error("Exception while handling an update:", exc_info=context.error)

async def number_expiration_job(context: ContextTypes.DEFAULT_TYPE):
    # This function remains unchanged
    job = context.job
    user_id, number, service = job.data
    lang = await get_user_lang(user_id)
    async with await get_db_conn() as aconn:
        async with aconn.cursor(row_factory=psycopg.rows.dict_row) as acur:
            await acur.execute("SELECT status, message_id FROM numbers WHERE phone_number = %s", (number,))
            number_data = await acur.fetchone()
            if number_data and number_data['status'] == 'in_use':
                await acur.execute("UPDATE numbers SET status = 'expired', assigned_to_id = NULL, assigned_at = NULL, message_id = NULL WHERE phone_number = %s", (number,))
                await acur.execute("UPDATE users SET strikes = strikes + 1 WHERE user_id = %s RETURNING strikes", (user_id,))
                new_strikes = (await acur.fetchone())['strikes']
                try:
                    await context.bot.edit_message_text("⌛️ এই নম্বরের মেয়াদ শেষ।", chat_id=user_id, message_id=number_data['message_id'])
                except (BadRequest, Forbidden): pass
                if new_strikes >= MAX_STRIKES:
                    ban_until = datetime.datetime.now(pytz.utc) + datetime.timedelta(hours=BAN_HOURS)
                    await acur.execute("UPDATE users SET is_banned = TRUE, ban_until = %s WHERE user_id = %s", (ban_until, user_id))
                    await context.bot.send_message(user_id, LANG_TEXT[lang]['strike_ban_message'].format(ban_hours=BAN_HOURS))
                elif new_strikes == 2:
                    await context.bot.send_message(user_id, LANG_TEXT[lang]['strike_warning_2'].format(ban_hours=BAN_HOURS))
                elif new_strikes == 1:
                    await context.bot.send_message(user_id, LANG_TEXT[lang]['strike_warning_1'].format(number=number))

async def daily_cleanup_job(context: ContextTypes.DEFAULT_TYPE):
    # This function remains unchanged
    logger.info("Running daily cleanup and unban job...")
    try:
        async with await get_db_conn() as aconn:
            async with aconn.cursor(row_factory=psycopg.rows.dict_row) as acur:
                await acur.execute("UPDATE users SET is_banned = FALSE, ban_until = NULL, strikes = 0 WHERE is_banned = TRUE AND ban_until < NOW() RETURNING user_id")
                unbanned_users = await acur.fetchall()
                for user in unbanned_users:
                    logger.info(f"Auto-unbanned user: {user['user_id']}")
                    try:
                        await context.bot.send_message(user['user_id'], "✅ আপনার অ্যাকাউন্টের ব্যান তুলে নেওয়া হয়েছে। আপনি এখন বট ব্যবহার করতে পারবেন।")
                    except (Forbidden, BadRequest):
                        logger.warning(f"Could not notify unbanned user {user['user_id']}.")
    except Exception as e:
        logger.error(f"Daily cleanup job failed: {e}")

# ... (বাকি সকল ইউজার এবং অ্যাডমিন হ্যান্ডলার অপরিবর্তিত থাকবে) ...
# I am including all other functions to provide the complete code as requested.
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    async with await get_db_conn() as aconn:
        async with aconn.cursor() as acur:
            await acur.execute("INSERT INTO users (user_id, first_name) VALUES (%s, %s) ON CONFLICT (user_id) DO UPDATE SET first_name = EXCLUDED.first_name", (user.id, user.first_name))
    lang = await get_user_lang(user.id)
    await update.message.reply_text(text=LANG_TEXT[lang]['welcome'].format(first_name=user.first_name), reply_markup=get_main_reply_keyboard(user.id), parse_mode=ParseMode.MARKDOWN)
async def check_user_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    user_id = update.effective_user.id
    lang = await get_user_lang(user_id)
    async with await get_db_conn() as aconn:
        async with aconn.cursor(row_factory=psycopg.rows.dict_row) as acur:
            await acur.execute("SELECT is_banned, ban_until, cooldown_until FROM users WHERE user_id = %s", (user_id,))
            user_data = await acur.fetchone()
            if user_data:
                effective_message = update.callback_query.message if update.callback_query else update.message
                if user_data['is_banned']:
                    await effective_message.reply_text(LANG_TEXT[lang]['user_is_banned'])
                    return False
                if user_data['cooldown_until'] and user_data['cooldown_until'] > datetime.datetime.now(pytz.utc):
                    seconds_left = int((user_data['cooldown_until'] - datetime.datetime.now(pytz.utc)).total_seconds())
                    await effective_message.reply_text(LANG_TEXT[lang]['cooldown_message'].format(seconds=seconds_left))
                    return False
    return True
async def handle_get_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_user_status(update, context): return
    lang = await get_user_lang(update.effective_user.id)
    keyboard = [[InlineKeyboardButton(s, callback_data=f"get_number_{s.lower()}") for s in ["Facebook", "Telegram", "WhatsApp"]]]
    await update.message.reply_text(LANG_TEXT[lang]['choose_service'], reply_markup=InlineKeyboardMarkup(keyboard))
async def handle_my_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = await get_user_lang(user_id)
    async with await get_db_conn() as aconn:
        async with aconn.cursor(row_factory=psycopg.rows.dict_row) as acur:
            await acur.execute("SELECT strikes, is_banned, ban_until FROM users WHERE user_id = %s", (user_id,))
            stats = await acur.fetchone()
            if stats:
                message = f"**{LANG_TEXT[lang]['stats_header']}**\n\n{LANG_TEXT[lang]['strikes']}: `{stats['strikes']}/{MAX_STRIKES}`\n"
                if stats['is_banned']:
                    time_left = (stats['ban_until'] - datetime.datetime.now(pytz.utc))
                    hours, remainder = divmod(time_left.total_seconds(), 3600)
                    minutes, _ = divmod(remainder, 60)
                    time_left_str = f"{int(hours)}h {int(minutes)}m"
                    message += f"{LANG_TEXT[lang]['status_banned'].format(time_left=time_left_str)}"
                else: message += f"{LANG_TEXT[lang]['status_normal']}"
            else: message = LANG_TEXT[lang]['stats_not_found']
    await update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN)
async def handle_support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = await get_user_lang(update.effective_user.id)
    reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton(text=LANG_TEXT[lang]['support_button'], url=f"https://t.me/{SUPPORT_USERNAME.lstrip('@')}")]])
    await update.message.reply_text(LANG_TEXT[lang]['support_prompt'], reply_markup=reply_markup)
async def handle_language_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = await get_user_lang(update.effective_user.id)
    keyboard = [[InlineKeyboardButton("🇧🇩 বাংলা", callback_data="set_lang_bn"), InlineKeyboardButton("🇬🇧 English", callback_data="set_lang_en")]]
    await update.message.reply_text(LANG_TEXT[lang]['choose_language'], reply_markup=InlineKeyboardMarkup(keyboard))
async def handle_button_press(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    data = query.data
    lang = await get_user_lang(user.id)
    if data.startswith("set_lang_"):
        new_lang = data.split("_")[-1]
        async with await get_db_conn() as aconn:
            async with aconn.cursor() as acur: await acur.execute("UPDATE users SET language = %s WHERE user_id = %s", (new_lang, user.id))
        await query.edit_message_text(LANG_TEXT[new_lang]['lang_changed'])
        return
    if not await check_user_status(update, context):
        try: await query.message.delete()
        except: pass
        return
    if data.startswith("get_number_"):
        service = data.split("_")[-1].capitalize()
        await query.edit_message_text(text=LANG_TEXT[lang]['searching_number'].format(service=service), parse_mode=ParseMode.MARKDOWN)
        async with await get_db_conn() as aconn:
            async with aconn.cursor(row_factory=psycopg.rows.dict_row) as acur:
                await acur.execute("UPDATE numbers SET status = 'in_use', assigned_to_id = %s, assigned_at = NOW() WHERE id = (SELECT id FROM numbers WHERE service ILIKE %s AND status = 'available' ORDER BY random() LIMIT 1) RETURNING phone_number, id", (user.id, service))
                number_data = await acur.fetchone()
        if number_data:
            number = number_data['phone_number']
            keyboard = [[InlineKeyboardButton(LANG_TEXT[lang]['otp_received_button'], callback_data=f"release_{number}"), InlineKeyboardButton(LANG_TEXT[lang]['otp_not_received_button'], callback_data=f"report_{number}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            sent_message = await query.edit_message_text(text=LANG_TEXT[lang]['number_message'].format(number=number, minutes=NUMBER_EXPIRATION_MINUTES), reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)
            async with await get_db_conn() as aconn:
                async with aconn.cursor() as acur: await acur.execute("UPDATE numbers SET message_id = %s WHERE phone_number = %s", (sent_message.message_id, number))
            context.job_queue.run_once(number_expiration_job, datetime.timedelta(minutes=NUMBER_EXPIRATION_MINUTES), data=[user.id, number, service], name=f"exp_{user.id}_{number}")
        else:
            await query.edit_message_text(text=LANG_TEXT[lang]['no_number_available'], parse_mode=ParseMode.MARKDOWN)
    elif data.startswith("release_"):
        number = data.split("_")[1]
        async with await get_db_conn() as aconn:
            async with aconn.cursor() as acur:
                await acur.execute("UPDATE numbers SET status = 'available', assigned_to_id = NULL, assigned_at = NULL, message_id = NULL WHERE phone_number = %s AND assigned_to_id = %s", (number, user.id))
                cooldown_time = datetime.datetime.now(pytz.utc) + datetime.timedelta(seconds=USER_COOLDOWN_SECONDS)
                await acur.execute("UPDATE users SET cooldown_until = %s WHERE user_id = %s", (cooldown_time, user.id))
        await query.edit_message_text(text=LANG_TEXT[lang]['number_released'])
        jobs = context.job_queue.get_jobs_by_name(f"exp_{user.id}_{number}")
        for job in jobs: job.schedule_removal()
    elif data.startswith("report_"):
        number = data.split("_")[1]
        await query.edit_message_text(text=LANG_TEXT[lang]['number_reported'])
        async with await get_db_conn() as aconn:
            async with aconn.cursor() as acur: await acur.execute("UPDATE numbers SET status = 'reported', assigned_to_id = NULL, assigned_at = NULL, message_id = NULL WHERE phone_number = %s AND assigned_to_id = %s", (number, user.id))
        jobs = context.job_queue.get_jobs_by_name(f"exp_{user.id}_{number}")
        for job in jobs: job.schedule_removal()
        await handle_get_number(update, context)
async def admin_panel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_USER_ID: return
    lang = await get_user_lang(ADMIN_USER_ID)
    keyboard = [[InlineKeyboardButton("➕ নম্বর যোগ করুন", callback_data="admin_add_numbers"), InlineKeyboardButton("📣 ঘোষণা দিন", callback_data="admin_broadcast")], [InlineKeyboardButton("📜 গাইডলাইন দেখুন", callback_data="admin_guideline")]]
    await update.message.reply_text(LANG_TEXT[lang]['admin_panel_welcome'], reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)
async def admin_panel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.from_user.id != ADMIN_USER_ID: return
    lang = await get_user_lang(ADMIN_USER_ID)
    if query.data == "admin_add_numbers":
        await query.message.reply_text(LANG_TEXT[lang]['ask_for_numbers'])
        return ADDING_NUMBERS
    elif query.data == "admin_broadcast":
        await query.message.reply_text(LANG_TEXT[lang]['ask_broadcast_message'])
        return BROADCAST_MESSAGE
    elif query.data == "admin_guideline":
        await query.message.reply_text(f"**{LANG_TEXT[lang]['guideline_title']}**\n\n{LANG_TEXT[lang]['guideline_text']}", parse_mode=ParseMode.MARKDOWN)
    return ConversationHandler.END
async def handle_add_numbers_convo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = await get_user_lang(ADMIN_USER_ID)
    lines = update.message.text.strip().split('\n')
    valid_numbers = [(p[0].strip(), p[1].strip().capitalize()) for line in lines if len(p := line.split(',')) == 2 and p[0].strip().startswith('+')]
    if not valid_numbers:
        await update.message.reply_text(LANG_TEXT[lang]['numbers_added_fail']); return ConversationHandler.END
    async with await get_db_conn() as aconn:
        async with aconn.cursor() as acur:
            await acur.executemany("INSERT INTO numbers (phone_number, service) VALUES (%s, %s) ON CONFLICT (phone_number) DO NOTHING", valid_numbers)
            count = acur.rowcount
    await update.message.reply_text(LANG_TEXT[lang]['numbers_added_success'].format(count=count))
    if count > 0: context.application.create_task(broadcast_message(context, LANG_TEXT['bn']['new_numbers_broadcast'].format(date=datetime.datetime.now().strftime("%d %B, %Y"))))
    return ConversationHandler.END
async def handle_broadcast_convo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = await get_user_lang(ADMIN_USER_ID)
    message_to_broadcast = f"**{LANG_TEXT[lang]['admin_announcement']}**\n\n{update.message.text}"
    context.application.create_task(broadcast_message(context, message_to_broadcast))
    return ConversationHandler.END
async def broadcast_message(context: ContextTypes.DEFAULT_TYPE, message_text: str):
    lang = await get_user_lang(ADMIN_USER_ID)
    async with await get_db_conn() as aconn:
        async with aconn.cursor(row_factory=psycopg.rows.dict_row) as acur:
            await acur.execute("SELECT user_id, last_broadcast_id FROM users")
            all_users = await acur.fetchall()
    sent_count = 0
    for user_data in all_users:
        user_id = user_data['user_id']
        try:
            sent_message = await context.bot.send_message(chat_id=user_id, text=message_text, parse_mode=ParseMode.MARKDOWN)
            async with aconn.cursor() as acur_update:
                await acur_update.execute("UPDATE users SET last_broadcast_id = %s WHERE user_id = %s", (sent_message.message_id, user_id))
            sent_count += 1
        except Forbidden: logger.warning(f"User {user_id} blocked the bot.")
        except Exception as e: logger.error(f"Failed broadcast to {user_id}: {e}")
        await asyncio.sleep(0.05)
    await context.bot.send_message(ADMIN_USER_ID, LANG_TEXT[lang]['broadcast_sent'].format(count=sent_count))
async def delete_last_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_USER_ID: return
    lang = await get_user_lang(ADMIN_USER_ID)
    await update.message.reply_text("🗑️ সর্বশেষ ঘোষণাটি মুছে ফেলা হচ্ছে...")
    async with await get_db_conn() as aconn:
        async with aconn.cursor(row_factory=psycopg.rows.dict_row) as acur:
            await acur.execute("SELECT user_id, last_broadcast_id FROM users WHERE last_broadcast_id IS NOT NULL")
            users_with_broadcast = await acur.fetchall()
    for user in users_with_broadcast:
        try: await context.bot.delete_message(chat_id=user['user_id'], message_id=user['last_broadcast_id'])
        except (BadRequest, Forbidden): pass
        await asyncio.sleep(0.05)
    async with aconn.cursor() as acur: await acur.execute("UPDATE users SET last_broadcast_id = NULL")
    await update.message.reply_text(LANG_TEXT[lang]['broadcast_deleted'])
async def ban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_USER_ID: return
    lang = await get_user_lang(ADMIN_USER_ID)
    try:
        user_to_ban = int(context.args[0])
        ban_time = datetime.datetime.now(pytz.utc) + datetime.timedelta(hours=BAN_HOURS)
        async with await get_db_conn() as aconn:
            async with aconn.cursor() as acur:
                await acur.execute("UPDATE users SET is_banned = TRUE, ban_until = %s, strikes = %s WHERE user_id = %s", (ban_time, MAX_STRIKES, user_to_ban))
                msg = LANG_TEXT[lang]['user_banned_success'].format(user_id=user_to_ban) if acur.rowcount > 0 else LANG_TEXT[lang]['user_not_found'].format(user_id=user_to_ban)
        await update.message.reply_text(msg)
    except (IndexError, ValueError): await update.message.reply_text("ব্যবহার: /ban [User ID]")
async def unban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_USER_ID: return
    lang = await get_user_lang(ADMIN_USER_ID)
    try:
        user_to_unban = int(context.args[0])
        async with await get_db_conn() as aconn:
            async with aconn.cursor() as acur:
                await acur.execute("UPDATE users SET is_banned = FALSE, ban_until = NULL, strikes = 0 WHERE user_id = %s", (user_to_unban,))
                msg = LANG_TEXT[lang]['user_unbanned_success'].format(user_id=user_to_unban) if acur.rowcount > 0 else LANG_TEXT[lang]['user_not_found'].format(user_id=user_to_unban)
        await update.message.reply_text(msg)
    except (IndexError, ValueError): await update.message.reply_text("ব্যবহার: /unban [User ID]")
async def delnumber_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_USER_ID: return
    lang = await get_user_lang(ADMIN_USER_ID)
    try:
        number_to_delete = context.args[0].strip()
        async with await get_db_conn() as aconn:
            async with aconn.cursor() as acur:
                await acur.execute("DELETE FROM numbers WHERE phone_number = %s", (number_to_delete,))
                if acur.rowcount > 0: await update.message.reply_text(LANG_TEXT[lang]['number_deleted_success'].format(number=number_to_delete))
                else: await update.message.reply_text(LANG_TEXT[lang]['number_not_found_db'].format(number=number_to_delete))
    except IndexError: await update.message.reply_text("ব্যবহার: /delnumber [+123456...]")
async def reactivate_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_USER_ID: return
    lang = await get_user_lang(ADMIN_USER_ID)
    try:
        number_to_reactivate = context.args[0].strip()
        async with await get_db_conn() as aconn:
            async with aconn.cursor() as acur:
                await acur.execute("UPDATE numbers SET status = 'available', assigned_to_id = NULL WHERE phone_number = %s", (number_to_reactivate,))
                if acur.rowcount > 0: await update.message.reply_text(LANG_TEXT[lang]['number_reactivated_success'].format(number=number_to_reactivate))
                else: await update.message.reply_text(LANG_TEXT[lang]['number_not_found_db'].format(number=number_to_reactivate))
    except IndexError: await update.message.reply_text("ব্যবহার: /reactivate [+123456...]")
async def view_numbers_by_status(update: Update, context: ContextTypes.DEFAULT_TYPE, status: str):
    if update.effective_user.id != ADMIN_USER_ID: return
    lang = await get_user_lang(ADMIN_USER_ID)
    header = LANG_TEXT[lang][f'{status}_numbers_header']
    no_numbers_msg = LANG_TEXT[lang][f'no_{status}_numbers']
    async with await get_db_conn() as aconn:
        async with aconn.cursor(row_factory=psycopg.rows.dict_row) as acur:
            await acur.execute("SELECT phone_number, service FROM numbers WHERE status = %s", (status,))
            numbers = await acur.fetchall()
    if not numbers:
        await update.message.reply_text(no_numbers_msg)
        return
    message = f"**{header}**\n\n"
    for num in numbers: message += f"`{num['phone_number']}` - *{num['service']}*\n"
    await update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN)

# -----------------------------------------------------------------------------
# |                         ফাইনাল অ্যাপ্লিকেশন চালু করা                        |
# -----------------------------------------------------------------------------
def main() -> None:
    threading.Thread(target=run_flask, daemon=True).start()
    bot_app = Application.builder().token(BOT_TOKEN).post_init(setup_database).build()
    
    job_queue = bot_app.job_queue
    job_queue.run_daily(daily_cleanup_job, time=datetime.time(hour=0, minute=5, tzinfo=pytz.UTC))

    # --- নতুন Error Handler যোগ করা হয়েছে ---
    bot_app.add_error_handler(error_handler)

    # Conversation and command handlers...
    admin_conv_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(admin_panel_callback, pattern='^admin_add_numbers$'),
            CommandHandler("add", lambda u,c: admin_panel_callback(u.callback_query,c)),
            CallbackQueryHandler(admin_panel_callback, pattern='^admin_broadcast$'),
            CommandHandler("broadcast", lambda u,c: admin_panel_callback(u.callback_query,c))
        ],
        states={
            ADDING_NUMBERS: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_add_numbers_convo)],
            BROADCAST_MESSAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_broadcast_convo)],
        },
        fallbacks=[CommandHandler("start", start_command)], per_message=False,
    )
    
    bot_app.add_handler(admin_conv_handler)
    bot_app.add_handler(CommandHandler("start", start_command))
    bot_app.add_handler(CommandHandler("ban", ban_command))
    bot_app.add_handler(CommandHandler("unban", unban_command))
    bot_app.add_handler(CommandHandler("delnumber", delnumber_command))
    bot_app.add_handler(CommandHandler("delbroadcast", delete_last_broadcast))
    bot_app.add_handler(CommandHandler("reactivate", reactivate_command))
    bot_app.add_handler(CommandHandler("view_reported", lambda u, c: view_numbers_by_status(u, c, 'reported')))
    bot_app.add_handler(CommandHandler("view_expired", lambda u, c: view_numbers_by_status(u, c, 'expired')))
    bot_app.add_handler(MessageHandler(filters.TEXT & filters.Regex(f'^{GET_NUMBER_TEXT}$'), handle_get_number))
    bot_app.add_handler(MessageHandler(filters.TEXT & filters.Regex(f'^{MY_STATS_TEXT}$'), handle_my_stats))
    bot_app.add_handler(MessageHandler(filters.TEXT & filters.Regex(f'^{SUPPORT_TEXT}$'), handle_support))
    bot_app.add_handler(MessageHandler(filters.TEXT & filters.Regex(f'^{LANGUAGE_TEXT}$'), handle_language_button))
    bot_app.add_handler(MessageHandler(filters.TEXT & filters.Regex(f'^{ADMIN_PANEL_TEXT}$'), admin_panel_command))
    bot_app.add_handler(CallbackQueryHandler(admin_panel_callback, pattern='^admin_guideline$'))
    bot_app.add_handler(CallbackQueryHandler(handle_button_press))
    bot_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, start_command))

    logger.info("Telegram Bot starting polling...")
    bot_app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)

if __name__ == "__main__":
    main()
