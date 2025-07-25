import logging
import datetime
import psycopg
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

# --- বহুভাষিক টেক্সট ---
# (LANG_TEXT dictionary অপরিবর্তিত থাকবে)
LANG_TEXT = {
    'bn': {
        "welcome": "👋 **স্বাগতম, {first_name}!**\n\nনিচের কীবোর্ড থেকে একটি অপশন বেছে নিন।",
        "keyboard_hidden": "কীবোর্ড লুকানো হয়েছে। আবার দেখতে /start চাপুন।",
        "choose_service": "🔢 কোন সার্ভিসের জন্য নম্বর প্রয়োজন? অনুগ্রহ করে বেছে নিন:",
        "stats_header": "📊 **আপনার পরিসংখ্যান**",
        "strikes": "স্ট্রাইক",
        "spam_count": "স্প্যাম",
        "status_banned": "অ্যাকাউন্ট স্ট্যাটাস: {hours} ঘণ্টার জন্য নিষিদ্ধ",
        "status_normal": "স্ট্যাটাস: সাধারণ ব্যবহারকারী",
        "stats_not_found": "আপনার পরিসংখ্যান খুঁজে পাওয়া যায়নি। অনুগ্রহ করে /start কমান্ড দিন।",
        "support_prompt": "📞 যে কোন প্রয়োজনে আমাদের সাপোর্ট টিমের সাথে যোগাযোগ করতে নিচের বাটনে ক্লিক করুন।",
        "support_button": "সাপোর্টে যোগাযোগ করুন",
        "unknown_command": "🤔 দুঃখিত, কমান্ডটি বুঝতে পারিনি। অনুগ্রহ করে কীবোর্ডের বাটন ব্যবহার করুন।",
        "choose_language": "অনুগ্রহ করে আপনার ভাষা নির্বাচন করুন:",
        "lang_changed": "✅ আপনার ভাষা সফলভাবে 'বাংলা' করা হয়েছে।",
        "searching_number": "🔍 আপনার জন্য একটি **{service}** নম্বর খোঁজা হচ্ছে...",
        "no_number_available": "❌ **দুঃখিত, এই মুহূর্তে নম্বর শেষ!** ❌\n\nআমাদের সকল নম্বর বর্তমানে ব্যবহৃত হচ্ছে। অ্যাডমিনকে বিষয়টি জানানো হয়েছে এবং তিনি খুব শীঘ্রই নতুন নম্বর যোগ করবেন।\n\n⏳ অনুগ্রহ করে কিছুক্ষণ পর আবার চেষ্টা করুন।",
        "new_numbers_broadcast": "🎉 **সুখবর! নতুন নম্বর যোগ করা হয়েছে!** 🎉\n\n**তারিখ:** {date}\n\nঅ্যাডমিন এইমাত্র আমাদের সিস্টেমে নতুন নম্বর যোগ করেছেন। এখনই আপনার প্রয়োজনীয় নম্বরটি নিয়ে নিন!",
        "broadcast_sent": "✅ বার্তাটি সফলভাবে {count} জন ব্যবহারকারীকে পাঠানো হয়েছে।",
        "broadcast_no_message": "❌ অনুগ্রহ করে /broadcast কমান্ডের সাথে একটি বার্তা দিন।",
        "admin_announcement": "📣 অ্যাডমিনের ঘোষণা 📣",
        "back_button": "⬅️ পিছনে",
        "main_menu_prompt": "প্রধান মেনু থেকে একটি অপশন বেছে নিন।",
        "admin_panel_welcome": "👑 **অ্যাডমিন প্যানেলে স্বাগতম** 👑\n\nঅনুগ্রহ করে নিচের অপশনগুলো থেকে বেছে নিন:",
        "guideline_title": "📜 **অ্যাডমিন কমান্ড গাইডলাইন** 📜",
        "guideline_text": """
        `➕ নম্বর যোগ করুন`
        এই বাটনে ক্লিক করার পর, প্রতি লাইনে একটি করে নম্বর এবং সার্ভিস কমা দিয়ে আলাদা করে পাঠান।
        *উদাহরণ:*
        `+8801711111111,Facebook`
        `+8801822222222,Telegram`

        `📣 ঘোষণা দিন (Broadcast)`
        কমান্ড: `/broadcast [আপনার বার্তা]`
        সকল ব্যবহারকারীকে একটি ফর্ম্যাট করা বার্তা পাঠায়।

        `🚫 ব্যবহারকারী ব্যান/আনব্যান করুন`
        ব্যবহারকারীর User ID দিয়ে তাকে ব্যান বা আনব্যান করুন।
        *ব্যান:* `/ban [User ID]`
        *আনব্যান:* `/unban [User ID]`
        """,
        "numbers_added_success": "✅ সফলভাবে {count} টি নতুন নম্বর যোগ করা হয়েছে। ব্যবহারকারীদের জানানো হচ্ছে...",
        "numbers_added_fail": "❌ কোনো বৈধ নম্বর পাওয়া যায়নি। ফরম্যাট চেক করুন: `+880...,Service`",
        "ask_for_numbers": "✍️ নম্বরগুলো পাঠান। প্রতি লাইনে একটি করে নম্বর এবং সার্ভিস কমা দিয়ে আলাদা করে লিখুন। যেমন: `+12345,Facebook`",
        "user_banned_success": "✅ ব্যবহারকারী {user_id} কে সফলভাবে ব্যান করা হয়েছে।",
        "user_unbanned_success": "✅ ব্যবহারকারী {user_id} কে সফলভাবে আনব্যান করা হয়েছে।",
        "user_not_found": "❌ ব্যবহারকারী {user_id} কে ডাটাবেসে খুঁজে পাওয়া যায়নি।",
    },
    'en': { # English translations for new features
        "admin_panel_welcome": "👑 **Welcome to the Admin Panel** 👑\n\nPlease choose from the options below:",
        "guideline_title": "📜 **Admin Command Guideline** 📜",
        "guideline_text": """
        `➕ Add Numbers`
        After clicking this button, send numbers per line, separated by a comma with the service.
        *Example:*
        `+1234567890,Facebook`
        `+9876543210,Telegram`

        `📣 Broadcast`
        Command: `/broadcast [Your Message]`
        Sends a formatted message to all users.

        `🚫 Ban/Unban User`
        Ban or unban a user with their User ID.
        *Ban:* `/ban [User ID]`
        *Unban:* `/unban [User ID]`
        """,
        "numbers_added_success": "✅ Successfully added {count} new numbers. Notifying users...",
        "numbers_added_fail": "❌ No valid numbers found. Check the format: `+123...,Service`",
        "ask_for_numbers": "✍️ Send the numbers. Write one per line, separating the number and service with a comma. E.g., `+12345,Facebook`",
        "user_banned_success": "✅ User {user_id} has been successfully banned.",
        "user_unbanned_success": "✅ User {user_id} has been successfully unbanned.",
        "user_not_found": "❌ User {user_id} not found in the database.",
        "new_numbers_broadcast": "🎉 **Good News! New Numbers Added!** 🎉\n\n**Date:** {date}\n\nThe admin has just added new numbers to our system. Get yours now!",
    }
}


# -----------------------------------------------------------------------------
# |                      লগিং, সার্ভার এবং Conversation States              |
# -----------------------------------------------------------------------------
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

# Conversation states for admin
ADDING_NUMBERS = 1

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
    logger.info("Connecting to database and verifying schema...")
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
                        is_available BOOLEAN DEFAULT TRUE, is_reported BOOLEAN DEFAULT FALSE,
                        assigned_to BIGINT, assigned_at TIMESTAMP
                    );
                """)
                # কলামগুলো না থাকলে যোগ করার জন্য স্বয়ংক্রিয় ব্যবস্থা
                await acur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='users'")
                columns = [row[0] for row in await acur.fetchall()]
                if 'language' not in columns:
                    await acur.execute("ALTER TABLE users ADD COLUMN language VARCHAR(5) DEFAULT 'bn';")
                if 'last_number_broadcast_id' not in columns:
                    await acur.execute("ALTER TABLE users ADD COLUMN last_number_broadcast_id BIGINT;")

        logger.info("SUCCESS: Database schema is up-to-date.")
        await app.bot.send_message(chat_id=ADMIN_USER_ID, text="✅ **Bot Deployed/Restarted Successfully!**", parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        logger.error(f"CRITICAL: Database or boot failure! Error: {e}")

async def get_user_lang(user_id: int) -> str:
    async with await get_db_conn() as aconn:
        async with aconn.cursor() as acur:
            await acur.execute("SELECT language FROM users WHERE user_id = %s", (user_id,))
            result = await acur.fetchone()
            return result[0] if result and result[0] else 'bn'

# -----------------------------------------------------------------------------
# |                      টেলিগ্রাম বটের সকল হ্যান্ডলার                       |
# -----------------------------------------------------------------------------

def get_main_reply_keyboard(user_id: int):
    keyboard = [
        [GET_NUMBER_TEXT],
        [MY_STATS_TEXT, SUPPORT_TEXT],
        [LANGUAGE_TEXT]
    ]
    if user_id == ADMIN_USER_ID:
        keyboard.append([ADMIN_PANEL_TEXT])
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

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

# --- Admin Panel Handlers ---
async def admin_panel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_USER_ID: return
    lang = await get_user_lang(ADMIN_USER_ID)
    keyboard = [
        [InlineKeyboardButton("➕ নম্বর যোগ করুন", callback_data="admin_add_numbers")],
        [InlineKeyboardButton("📣 ঘোষণা দিন", callback_data="admin_broadcast_guide")],
        [InlineKeyboardButton("🚫 ব্যবহারকারী ব্যান/আনব্যান করুন", callback_data="admin_ban_guide")],
        [InlineKeyboardButton("📜 গাইডলাইন দেখুন", callback_data="admin_guideline")]
    ]
    await update.message.reply_text(LANG_TEXT[lang]['admin_panel_welcome'], reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)

async def admin_panel_callback(query: Update.callback_query, context: ContextTypes.DEFAULT_TYPE):
    data = query.data
    lang = await get_user_lang(ADMIN_USER_ID)

    if data == "admin_add_numbers":
        await query.message.reply_text(LANG_TEXT[lang]['ask_for_numbers'])
        return ADDING_NUMBERS
    elif data == "admin_guideline":
        await query.message.reply_text(f"**{LANG_TEXT[lang]['guideline_title']}**\n{LANG_TEXT[lang]['guideline_text']}", parse_mode=ParseMode.MARKDOWN)
    elif data == "admin_broadcast_guide" or data == "admin_ban_guide":
         await query.message.reply_text(f"**{LANG_TEXT[lang]['guideline_title']}**\n{LANG_TEXT[lang]['guideline_text']}", parse_mode=ParseMode.MARKDOWN)


async def handle_add_numbers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = await get_user_lang(ADMIN_USER_ID)
    numbers_text = update.message.text
    lines = numbers_text.strip().split('\n')
    valid_numbers = []
    for line in lines:
        parts = line.split(',')
        if len(parts) == 2 and parts[0].strip().startswith('+'):
            valid_numbers.append((parts[0].strip(), parts[1].strip().capitalize()))

    if not valid_numbers:
        await update.message.reply_text(LANG_TEXT[lang]['numbers_added_fail'])
        return ConversationHandler.END

    async with await get_db_conn() as aconn:
        async with aconn.cursor() as acur:
            await acur.executemany(
                "INSERT INTO numbers (phone_number, service) VALUES (%s, %s) ON CONFLICT (phone_number) DO NOTHING",
                valid_numbers
            )
            count = acur.rowcount

    await update.message.reply_text(LANG_TEXT[lang]['numbers_added_success'].format(count=count))
    
    # নতুন নম্বর যোগ করার পর ব্রডকাস্ট পাঠানো
    context.application.create_task(broadcast_new_numbers(context))
    
    return ConversationHandler.END

async def broadcast_new_numbers(context: ContextTypes.DEFAULT_TYPE):
    async with await get_db_conn() as aconn:
        async with aconn.cursor() as acur:
            await acur.execute("SELECT user_id, language, last_number_broadcast_id FROM users")
            all_users = await acur.fetchall()
            
    today_date = datetime.datetime.now().strftime("%d %B, %Y")

    for user_id, lang, last_msg_id in all_users:
        # আগের মেসেজ ডিলিট করা
        if last_msg_id:
            try:
                await context.bot.delete_message(chat_id=user_id, message_id=last_msg_id)
            except Forbidden:
                pass # বট ব্লক থাকলে কিছু করার নেই
            except Exception:
                pass # মেসেজ খুঁজে না পাওয়া গেলে বা অন্য কোনো সমস্যা হলে

        # নতুন মেসেজ পাঠানো
        user_lang_code = lang if lang in LANG_TEXT else 'bn'
        message_text = LANG_TEXT[user_lang_code]['new_numbers_broadcast'].format(date=today_date)
        try:
            sent_message = await context.bot.send_message(chat_id=user_id, text=message_text, parse_mode=ParseMode.MARKDOWN)
            # নতুন মেসেজ আইডি সেভ করা
            async with aconn.cursor() as acur_update:
                await acur_update.execute("UPDATE users SET last_number_broadcast_id = %s WHERE user_id = %s", (sent_message.message_id, user_id))
        except Forbidden:
            logger.warning(f"User {user_id} has blocked the bot. Skipping broadcast.")
        except Exception as e:
            logger.error(f"Failed to send new number broadcast to {user_id}: {e}")
        await asyncio.sleep(0.1)


async def ban_user_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_USER_ID: return
    lang = await get_user_lang(ADMIN_USER_ID)
    try:
        user_to_ban = int(context.args[0])
        ban_time = datetime.datetime.now() + datetime.timedelta(hours=BAN_HOURS)
        async with await get_db_conn() as aconn:
            async with aconn.cursor() as acur:
                await acur.execute(
                    "UPDATE users SET is_banned = TRUE, ban_until = %s, strikes = %s WHERE user_id = %s",
                    (ban_time, MAX_STRIKES, user_to_ban)
                )
                if acur.rowcount > 0:
                    await update.message.reply_text(LANG_TEXT[lang]['user_banned_success'].format(user_id=user_to_ban))
                else:
                    await update.message.reply_text(LANG_TEXT[lang]['user_not_found'].format(user_id=user_to_ban))
    except (IndexError, ValueError):
        await update.message.reply_text("ব্যবহার: /ban [User ID]")

async def unban_user_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_USER_ID: return
    lang = await get_user_lang(ADMIN_USER_ID)
    try:
        user_to_unban = int(context.args[0])
        async with await get_db_conn() as aconn:
            async with aconn.cursor() as acur:
                await acur.execute(
                    "UPDATE users SET is_banned = FALSE, ban_until = NULL, strikes = 0 WHERE user_id = %s",
                    (user_to_unban,)
                )
                if acur.rowcount > 0:
                    await update.message.reply_text(LANG_TEXT[lang]['user_unbanned_success'].format(user_id=user_to_unban))
                else:
                    await update.message.reply_text(LANG_TEXT[lang]['user_not_found'].format(user_id=user_to_unban))
    except (IndexError, ValueError):
        await update.message.reply_text("ব্যবহার: /unban [User ID]")


async def data_cleanup_job(context: ContextTypes.DEFAULT_TYPE):
    logger.info("Running daily data cleanup job...")
    try:
        async with await get_db_conn() as aconn:
            async with aconn.cursor() as acur:
                await acur.execute("DELETE FROM users WHERE strikes = 0 AND (is_banned = FALSE OR ban_until < NOW())")
                logger.info(f"Cleanup complete. Deleted {acur.rowcount} users.")
    except Exception as e:
        logger.error(f"Error during data cleanup job: {e}")

# ... (বাকি হ্যান্ডলারগুলো অপরিবর্তিত)
# (handle_get_number, handle_my_stats, etc. will remain the same as the last provided code)

# -----------------------------------------------------------------------------
# |                         ফাইনাল অ্যাপ্লিকেশন চালু করা                        |
# -----------------------------------------------------------------------------
def main() -> None:
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    logger.info("Keep-alive server started.")

    bot_app = Application.builder().token(BOT_TOKEN).post_init(setup_database).build()
    
    # --- স্বয়ংক্রিয় ক্লিনার জব সেটআপ ---
    job_queue = bot_app.job_queue
    job_queue.run_daily(data_cleanup_job, time=datetime.time(hour=21, minute=0, second=0)) # UTC 21:00 = GMT+6 03:00

    # --- অ্যাডমিন Conversation Handler ---
    admin_conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_panel_callback, pattern='^admin_add_numbers$')],
        states={
            ADDING_NUMBERS: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_add_numbers)],
        },
        fallbacks=[],
        per_message=False
    )
    
    bot_app.add_handler(admin_conv_handler)
    
    # --- কমান্ড হ্যান্ডলার ---
    bot_app.add_handler(CommandHandler("start", start_command))
    bot_app.add_handler(CommandHandler("ban", ban_user_command))
    bot_app.add_handler(CommandHandler("unban", unban_user_command))
    # ... (broadcast and other commands will be added here if needed)

    # --- বাটন হ্যান্ডলার ---
    bot_app.add_handler(MessageHandler(filters.TEXT & filters.Regex(f'^{ADMIN_PANEL_TEXT}$'), admin_panel_command))
    # ... (other ReplyKeyboard handlers remain the same)
    
    # --- ইনলাইন বাটন হ্যান্ডলার ---
    # We need a general callback handler for other admin buttons that don't start a conversation
    bot_app.add_handler(CallbackQueryHandler(admin_panel_callback, pattern='^admin_guideline$|^admin_broadcast_guide$|^admin_ban_guide$'))
    # ... (the main button press handler for users remains the same)

    logger.info("Telegram Bot starting polling...")
    bot_app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
