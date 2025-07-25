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
from telegram.error import Forbidden

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

# --- বাটন টেক্সট ---
GET_NUMBER_TEXT = "✨ Get Number 🎗️"
MY_STATS_TEXT = "📊 My Stats"
SUPPORT_TEXT = "📞 Support"
LANGUAGE_TEXT = "🌐 Language"
ADMIN_PANEL_TEXT = "👑 Admin Panel 👑"

# --- Conversation States ---
ADDING_NUMBERS = 1

# --- সম্পূর্ণ বহুভাষিক টেক্সট ---
LANG_TEXT = {
    'bn': {
        "welcome": "👋 **স্বাগতম, {first_name}!**\n\nনিচের কীবোর্ড থেকে একটি অপশন বেছে নিন।",
        "choose_service": "🔢 কোন সার্ভিসের জন্য নম্বর প্রয়োজন? অনুগ্রহ করে বেছে নিন:",
        "stats_header": "📊 **আপনার পরিসংখ্যান**",
        "strikes": "স্ট্রাইক", "spam_count": "স্প্যাম",
        "status_banned": "অ্যাকাউন্ট স্ট্যাটাস: {hours} ঘণ্টার জন্য নিষিদ্ধ",
        "status_normal": "স্ট্যাটাস: সাধারণ ব্যবহারকারী", "stats_not_found": "আপনার পরিসংখ্যান খুঁজে পাওয়া যায়নি।",
        "support_prompt": "📞 সাপোর্টের জন্য নিচের বাটনে ক্লিক করুন।", "support_button": "সাপোর্টে যোগাযোগ করুন",
        "unknown_command": "🤔 দুঃখিত, কমান্ডটি বুঝতে পারিনি।", "choose_language": "অনুগ্রহ করে আপনার ভাষা নির্বাচন করুন:",
        "lang_changed": "✅ আপনার ভাষা সফলভাবে 'বাংলা' করা হয়েছে।", "searching_number": "🔍 আপনার জন্য একটি **{service}** নম্বর খোঁজা হচ্ছে...",
        "no_number_available": "❌ **দুঃখিত, এই মুহূর্তে নম্বর শেষ!** ❌\n\nঅ্যাডমিন খুব শীঘ্রই নতুন নম্বর যোগ করবেন।\n⏳ অনুগ্রহ করে কিছুক্ষণ পর আবার চেষ্টা করুন।",
        "new_numbers_broadcast": "🎉 **সুখবর! নতুন নম্বর যোগ করা হয়েছে!** 🎉\n\n**তারিখ:** {date}\n\nএখনই আপনার প্রয়োজনীয় নম্বরটি নিয়ে নিন!",
        "admin_panel_welcome": "👑 **অ্যাডমিন প্যানেলে স্বাগতম** 👑", "guideline_title": "📜 **অ্যাডমিন গাইডলাইন** 📜",
        "guideline_text": "`➕ নম্বর যোগ করুন`\nএই বাটনে ক্লিক করে, প্রতি লাইনে একটি করে নম্বর ও সার্ভিস কমা দিয়ে পাঠান।\n*উদাহরণ:* `+880...,Facebook`\n\n`📣 ঘোষণা দিন`\n`/broadcast [বার্তা]`\n\n`🚫 ব্যান/আনব্যান`\n`/ban [User ID]`\n`/unban [User ID]`",
        "ask_for_numbers": "✍️ নম্বরগুলো পাঠান। ফরম্যাট: `+12345,Facebook`", "numbers_added_success": "✅ সফলভাবে {count} টি নতুন নম্বর যোগ করা হয়েছে।",
        "numbers_added_fail": "❌ কোনো বৈধ নম্বর পাওয়া যায়নি।", "user_banned_success": "✅ ব্যবহারকারী {user_id} কে ব্যান করা হয়েছে।",
        "user_unbanned_success": "✅ ব্যবহারকারী {user_id} কে আনব্যান করা হয়েছে।", "user_not_found": "❌ ব্যবহারকারী {user_id} কে খুঁজে পাওয়া যায়নি।",
        "broadcast_sent": "✅ বার্তাটি {count} জন ব্যবহারকারীকে পাঠানো হয়েছে।", "broadcast_no_message": "❌ /broadcast কমান্ডের সাথে একটি বার্তা দিন।",
        "admin_announcement": "📣 অ্যাডমিনের ঘোষণা 📣", "back_button": "⬅️ পিছনে",
    },
    'en': {
        "welcome": "👋 **Welcome, {first_name}!**\n\nChoose an option from the keyboard below.", "choose_service": "🔢 Which service do you need a number for? Please choose:",
        "stats_header": "📊 **Your Statistics**", "strikes": "Strikes", "spam_count": "Spam",
        "status_banned": "Account Status: Banned for {hours} hours", "status_normal": "Status: Normal User",
        "stats_not_found": "Your statistics were not found.", "support_prompt": "📞 Click the button below for support.",
        "support_button": "Contact Support", "unknown_command": "🤔 Sorry, I didn't understand.",
        "choose_language": "Please select your language:", "lang_changed": "✅ Language successfully changed to 'English'.",
        "searching_number": "🔍 Searching for a **{service}** number for you...", "no_number_available": "❌ **Sorry, out of numbers!** ❌\n\nThe admin will add new numbers soon.\n⏳ Please try again later.",
        "new_numbers_broadcast": "🎉 **Good News! New Numbers Added!** 🎉\n\n**Date:** {date}\n\nGet yours now!",
        "admin_panel_welcome": "👑 **Welcome to the Admin Panel** 👑", "guideline_title": "📜 **Admin Guideline** 📜",
        "guideline_text": "`➕ Add Numbers`\nClick and send numbers per line, separated by a comma.\n*Example:* `+123...,Facebook`\n\n`📣 Broadcast`\n`/broadcast [Message]`\n\n`🚫 Ban/Unban`\n`/ban [User ID]`\n`/unban [User ID]`",
        "ask_for_numbers": "✍️ Send numbers. Format: `+12345,Facebook`", "numbers_added_success": "✅ Successfully added {count} new numbers.",
        "numbers_added_fail": "❌ No valid numbers found.", "user_banned_success": "✅ User {user_id} has been banned.",
        "user_unbanned_success": "✅ User {user_id} has been unbanned.", "user_not_found": "❌ User {user_id} not found.",
        "broadcast_sent": "✅ Message sent to {count} users.", "broadcast_no_message": "❌ Please provide a message with /broadcast.",
        "admin_announcement": "📣 Admin Announcement 📣", "back_button": "⬅️ Back",
    }
}

# -----------------------------------------------------------------------------
# |                      লগিং ও সার্ভার সেটআপ                       |
# -----------------------------------------------------------------------------
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logging.getLogger("httpx").setLevel(logging.WARNING)
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
                        is_banned BOOLEAN DEFAULT FALSE, ban_until TIMESTAMP, language VARCHAR(5) DEFAULT 'bn',
                        last_number_broadcast_id BIGINT
                    );
                    CREATE TABLE IF NOT EXISTS numbers (
                        id SERIAL PRIMARY KEY, phone_number VARCHAR(25) UNIQUE NOT NULL, service VARCHAR(50) NOT NULL,
                        is_available BOOLEAN DEFAULT TRUE, assigned_to BIGINT, assigned_at TIMESTAMP
                    );
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

async def find_available_number(service: str):
    async with await get_db_conn() as aconn:
        async with aconn.cursor(row_factory=psycopg.rows.dict_row) as acur:
            await acur.execute("SELECT phone_number FROM numbers WHERE service ILIKE %s AND is_available = TRUE LIMIT 1", (service,))
            return await acur.fetchone()

# -----------------------------------------------------------------------------
# |                কীবোর্ড এবং মেনু তৈরির ফাংশন (সংশোধিত)                |
# -----------------------------------------------------------------------------
def get_main_reply_keyboard(user_id: int):
    """প্রধান কীবোর্ড তৈরি করে। অ্যাডমিনের জন্য বিশেষ বাটন যোগ করে।"""
    keyboard = [[GET_NUMBER_TEXT], [MY_STATS_TEXT, SUPPORT_TEXT], [LANGUAGE_TEXT]]
    if user_id == ADMIN_USER_ID:
        keyboard.append([ADMIN_PANEL_TEXT])
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, input_field_placeholder="Choose an option...")

# -----------------------------------------------------------------------------
# |                     কমান্ড এবং বাটন হ্যান্ডলার (সকল)                     |
# -----------------------------------------------------------------------------

# --- Main Commands & Keyboard Button Handlers ---
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    async with await get_db_conn() as aconn:
        async with aconn.cursor() as acur:
            await acur.execute("INSERT INTO users (user_id, first_name) VALUES (%s, %s) ON CONFLICT (user_id) DO UPDATE SET first_name = EXCLUDED.first_name", (user.id, user.first_name))
    lang = await get_user_lang(user.id)
    await update.message.reply_text(
        text=LANG_TEXT[lang]['welcome'].format(first_name=user.first_name),
        reply_markup=get_main_reply_keyboard(user.id), parse_mode=ParseMode.MARKDOWN
    )

async def handle_get_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = await get_user_lang(update.effective_user.id)
    keyboard = [
        [InlineKeyboardButton("💎 Facebook", callback_data="get_number_facebook")],
        [InlineKeyboardButton("✈️ Telegram", callback_data="get_number_telegram")],
        [InlineKeyboardButton("💬 WhatsApp", callback_data="get_number_whatsapp")],
    ]
    await update.message.reply_text(LANG_TEXT[lang]['choose_service'], reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_my_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = await get_user_lang(user_id)
    async with await get_db_conn() as aconn:
        async with aconn.cursor(row_factory=psycopg.rows.dict_row) as acur:
            await acur.execute("SELECT strikes, is_banned FROM users WHERE user_id = %s", (user_id,))
            stats = await acur.fetchone()
            if stats:
                message = f"{LANG_TEXT[lang]['stats_header']}\n\n{LANG_TEXT[lang]['strikes']}: `{stats['strikes']}/{MAX_STRIKES}`\n"
                if stats['is_banned']:
                    message += f"{LANG_TEXT[lang]['spam_count']}: `{MAX_STRIKES}/{MAX_STRIKES}`\n{LANG_TEXT[lang]['status_banned'].format(hours=BAN_HOURS)}"
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

async def admin_panel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_USER_ID: return
    lang = await get_user_lang(ADMIN_USER_ID)
    keyboard = [[InlineKeyboardButton("➕ নম্বর যোগ করুন", callback_data="admin_add_numbers")], [InlineKeyboardButton("📜 গাইডলাইন দেখুন", callback_data="admin_guideline")]]
    await update.message.reply_text(LANG_TEXT[lang]['admin_panel_welcome'], reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)

# --- Admin Panel Conversation Handler ---
async def admin_panel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.from_user.id != ADMIN_USER_ID: return
    lang = await get_user_lang(ADMIN_USER_ID)
    if query.data == "admin_add_numbers":
        await query.message.reply_text(LANG_TEXT[lang]['ask_for_numbers'])
        return ADDING_NUMBERS
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
    if count > 0: context.application.create_task(broadcast_new_numbers(context))
    return ConversationHandler.END

# --- General Inline Button Handler ---
async def handle_button_press(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    user_id = query.from_user.id; data = query.data
    lang = await get_user_lang(user_id)
    if data.startswith("get_number_"):
        service = data.split("_")[-1].capitalize()
        await query.edit_message_text(text=LANG_TEXT[lang]['searching_number'].format(service=service), parse_mode=ParseMode.MARKDOWN)
        number_data = await find_available_number(service)
        if number_data: await query.edit_message_text(f"আপনার নম্বর: `{number_data['phone_number']}`", parse_mode=ParseMode.MARKDOWN)
        else: await query.edit_message_text(text=LANG_TEXT[lang]['no_number_available'], parse_mode=ParseMode.MARKDOWN)
    elif data.startswith("set_lang_"):
        new_lang = data.split("_")[-1]
        async with await get_db_conn() as aconn:
            async with aconn.cursor() as acur: await acur.execute("UPDATE users SET language = %s WHERE user_id = %s", (new_lang, user_id))
        await query.edit_message_text(LANG_TEXT[new_lang]['lang_changed'])

# --- Admin Commands ---
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

# --- Background Tasks & Broadcast ---
async def broadcast_new_numbers(context: ContextTypes.DEFAULT_TYPE):
    async with await get_db_conn() as aconn:
        async with aconn.cursor() as acur:
            await acur.execute("SELECT user_id, language, last_number_broadcast_id FROM users")
            all_users = await acur.fetchall()
    today_date = datetime.datetime.now().strftime("%d %B, %Y")
    for user_id, lang, last_msg_id in all_users:
        if last_msg_id:
            try: await context.bot.delete_message(chat_id=user_id, message_id=last_msg_id)
            except Exception: pass
        try:
            user_lang_code = lang if lang in LANG_TEXT else 'bn'
            message_text = LANG_TEXT[user_lang_code]['new_numbers_broadcast'].format(date=today_date)
            sent_message = await context.bot.send_message(chat_id=user_id, text=message_text, parse_mode=ParseMode.MARKDOWN)
            async with await get_db_conn() as aconn_update:
                async with aconn_update.cursor() as acur_update:
                    await acur_update.execute("UPDATE users SET last_number_broadcast_id = %s WHERE user_id = %s", (sent_message.message_id, user_id))
        except Forbidden: logger.warning(f"User {user_id} blocked the bot.")
        except Exception as e: logger.error(f"Failed broadcast to {user_id}: {e}")
        await asyncio.sleep(0.05)

async def data_cleanup_job(context: ContextTypes.DEFAULT_TYPE):
    logger.info("Running daily data cleanup job...")
    try:
        async with await get_db_conn() as aconn:
            async with aconn.cursor() as acur:
                await acur.execute("DELETE FROM users WHERE strikes = 0 AND (is_banned = FALSE OR ban_until < NOW())")
                logger.info(f"Cleanup complete. Deleted {acur.rowcount} inactive users.")
    except Exception as e: logger.error(f"Data cleanup job failed: {e}")

# -----------------------------------------------------------------------------
# |                         ফাইনাল অ্যাপ্লিকেশন চালু করা                        |
# -----------------------------------------------------------------------------
def main() -> None:
    threading.Thread(target=run_flask, daemon=True).start()
    bot_app = Application.builder().token(BOT_TOKEN).post_init(setup_database).build()
    job_queue = bot_app.job_queue
    job_queue.run_daily(data_cleanup_job, time=datetime.time(hour=21, minute=0, tzinfo=pytz.UTC)) # GMT+6 এর রাত ৩টা

    admin_conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_panel_callback, pattern='^admin_add_numbers$')],
        states={ADDING_NUMBERS: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_add_numbers_convo)]},
        fallbacks=[], per_message=False)
    
    bot_app.add_handler(admin_conv_handler)
    bot_app.add_handler(CommandHandler("start", start_command))
    bot_app.add_handler(CommandHandler("ban", ban_command))
    bot_app.add_handler(CommandHandler("unban", unban_command))

    bot_app.add_handler(MessageHandler(filters.TEXT & filters.Regex(f'^{GET_NUMBER_TEXT}$'), handle_get_number))
    bot_app.add_handler(MessageHandler(filters.TEXT & filters.Regex(f'^{MY_STATS_TEXT}$'), handle_my_stats))
    bot_app.add_handler(MessageHandler(filters.TEXT & filters.Regex(f'^{SUPPORT_TEXT}$'), handle_support))
    bot_app.add_handler(MessageHandler(filters.TEXT & filters.Regex(f'^{LANGUAGE_TEXT}$'), handle_language_button))
    bot_app.add_handler(MessageHandler(filters.TEXT & filters.Regex(f'^{ADMIN_PANEL_TEXT}$'), admin_panel_command))

    bot_app.add_handler(CallbackQueryHandler(handle_button_press))
    bot_app.add_handler(CallbackQueryHandler(admin_panel_callback, pattern='^admin_guideline$'))
    
    bot_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, start_command))

    logger.info("Telegram Bot starting polling...")
    bot_app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
