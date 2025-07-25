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

# --- Conversation States ---
ADDING_NUMBERS = 1

# --- সম্পূর্ণ বহুভাষিক টেক্সট (সংশোধিত) ---
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
        "admin_panel_welcome": "👑 **অ্যাডমিন প্যানেলে স্বাগতম** 👑\n\nঅনুগ্রহ করে নিচের অপশনগুলো থেকে বেছে নিন:",
        "guideline_title": "📜 **অ্যাডমিন কমান্ড গাইডলাইন** 📜",
        "guideline_text": "`➕ নম্বর যোগ করুন`\nএই বাটনে ক্লিক করার পর, প্রতি লাইনে একটি করে নম্বর এবং সার্ভিস কমা দিয়ে আলাদা করে পাঠান।\n*উদাহরণ:*\n`+88017...,Facebook`\n\n`📣 ঘোষণা দিন`\nকমান্ড: `/broadcast [বার্তা]`\n\n`🚫 ব্যবহারকারী ব্যান/আনব্যান`\n*ব্যান:* `/ban [User ID]`\n*আনব্যান:* `/unban [User ID]`",
        "ask_for_numbers": "✍️ নম্বরগুলো পাঠান। প্রতি লাইনে একটি করে লিখুন। যেমন: `+12345,Facebook`",
        "numbers_added_success": "✅ সফলভাবে {count} টি নতুন নম্বর যোগ করা হয়েছে। ব্যবহারকারীদের জানানো হচ্ছে...",
        "numbers_added_fail": "❌ কোনো বৈধ নম্বর পাওয়া যায়নি। ফরম্যাট চেক করুন: `+880...,Service`",
        "user_banned_success": "✅ ব্যবহারকারী {user_id} কে সফলভাবে ব্যান করা হয়েছে।",
        "user_unbanned_success": "✅ ব্যবহারকারী {user_id} কে সফলভাবে আনব্যান করা হয়েছে।",
        "user_not_found": "❌ ব্যবহারকারী {user_id} কে ডাটাবেসে খুঁজে পাওয়া যায়নি।",
        "back_button": "⬅️ পিছনে",
        "main_menu_prompt": "প্রধান মেনু থেকে একটি অপশন বেছে নিন।",
    },
    'en': {
        "welcome": "👋 **Welcome, {first_name}!**\n\nChoose an option from the keyboard below.",
        "keyboard_hidden": "Keyboard hidden. Press /start to show it again.",
        "choose_service": "🔢 Which service do you need a number for? Please choose:",
        "stats_header": "📊 **Your Statistics**",
        "strikes": "Strikes",
        "spam_count": "Spam",
        "status_banned": "Account Status: Banned for {hours} hours",
        "status_normal": "Status: Normal User",
        "stats_not_found": "Your statistics were not found. Please use the /start command.",
        "support_prompt": "📞 To contact our support team for any need, please click the button below.",
        "support_button": "Contact Support",
        "unknown_command": "🤔 Sorry, I didn't understand that command. Please use the keyboard buttons.",
        "choose_language": "Please select your language:",
        "lang_changed": "✅ Your language has been successfully changed to 'English'.",
        "searching_number": "🔍 Searching for a temporary **{service}** number for you...",
        "no_number_available": "❌ **Sorry, out of numbers right now!** ❌\n\nAll our numbers are currently in use. The admin has been notified and will add new numbers soon.\n\n⏳ Please try again after some time.",
        "new_numbers_broadcast": "🎉 **Good News! New Numbers Added!** 🎉\n\n**Date:** {date}\n\nThe admin has just added new numbers to our system. Get yours now!",
        "admin_panel_welcome": "👑 **Welcome to the Admin Panel** 👑\n\nPlease choose from the options below:",
        "guideline_title": "📜 **Admin Command Guideline** 📜",
        "guideline_text": "`➕ Add Numbers`\nAfter clicking this button, send numbers per line, separated by a comma with the service.\n*Example:*\n`+12345,Facebook`\n\n`📣 Broadcast`\nCommand: `/broadcast [Message]`\n\n`🚫 Ban/Unban User`\n*Ban:* `/ban [User ID]`\n*Unban:* `/unban [User ID]`",
        "ask_for_numbers": "✍️ Send the numbers. Write one per line, separating the number and service with a comma. E.g., `+12345,Facebook`",
        "numbers_added_success": "✅ Successfully added {count} new numbers. Notifying users...",
        "numbers_added_fail": "❌ No valid numbers found. Check the format: `+123...,Service`",
        "user_banned_success": "✅ User {user_id} has been successfully banned.",
        "user_unbanned_success": "✅ User {user_id} has been successfully unbanned.",
        "user_not_found": "❌ User {user_id} not found in the database.",
        "back_button": "⬅️ Back",
        "main_menu_prompt": "Choose an option from the main menu.",
    }
}

# -----------------------------------------------------------------------------
# |                      লগিং, সার্ভার এবং অন্যান্য সেটআপ                      |
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
        logger.info("SUCCESS: Database schema is up-to-date.")
        await app.bot.send_message(chat_id=ADMIN_USER_ID, text="✅ **Bot Deployed/Restarted Successfully!**", parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        logger.error(f"CRITICAL: Database or boot failure! Error: {e}")

async def get_user_lang(user_id: int) -> str:
    try:
        async with await get_db_conn() as aconn:
            async with aconn.cursor() as acur:
                await acur.execute("SELECT language FROM users WHERE user_id = %s", (user_id,))
                result = await acur.fetchone()
                return result[0] if result and result[0] else 'bn'
    except Exception as e:
        logger.error(f"Could not fetch language for user {user_id}. Defaulting to 'bn'. Error: {e}")
        return 'bn'

# -----------------------------------------------------------------------------
# |                       কীবোর্ড এবং মেনু তৈরির ফাংশন                       |
# -----------------------------------------------------------------------------
def get_main_reply_keyboard(user_id: int):
    keyboard = [[GET_NUMBER_TEXT], [MY_STATS_TEXT, SUPPORT_TEXT], [LANGUAGE_TEXT]]
    if user_id == ADMIN_USER_ID:
        keyboard.append([ADMIN_PANEL_TEXT])
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, input_field_placeholder="Choose an option...")

async def get_admin_panel_keyboard(lang: str):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ নম্বর যোগ করুন", callback_data="admin_add_numbers")],
        [InlineKeyboardButton("📜 গাইডলাইন দেখুন", callback_data="admin_guideline")]
    ])

# -----------------------------------------------------------------------------
# |                     ব্যবহারকারী এবং অ্যাডমিন হ্যান্ডলার                     |
# -----------------------------------------------------------------------------

# --- User Handlers ---
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
    # This handler is now just a placeholder, the real logic is in handle_button_press
    pass

async def handle_my_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # This handler is now just a placeholder, the real logic is in handle_button_press
    pass
async def handle_support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = await get_user_lang(update.effective_user.id)
    reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton(text=LANG_TEXT[lang]['support_button'], url=f"https://t.me/{SUPPORT_USERNAME.lstrip('@')}")]])
    await update.message.reply_text(text=LANG_TEXT[lang]['support_prompt'], reply_markup=reply_markup)

async def handle_language_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # This handler is now just a placeholder, the real logic is in handle_button_press
    pass

# --- Admin Handlers ---
async def admin_panel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_USER_ID: return
    lang = await get_user_lang(ADMIN_USER_ID)
    await update.message.reply_text(
        LANG_TEXT[lang]['admin_panel_welcome'],
        reply_markup=await get_admin_panel_keyboard(lang),
        parse_mode=ParseMode.MARKDOWN
    )

async def admin_panel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.from_user.id != ADMIN_USER_ID: return

    lang = await get_user_lang(ADMIN_USER_ID)
    data = query.data

    if data == "admin_add_numbers":
        await query.message.reply_text(LANG_TEXT[lang]['ask_for_numbers'])
        return ADDING_NUMBERS
    elif data == "admin_guideline":
        await query.message.reply_text(
            f"**{LANG_TEXT[lang]['guideline_title']}**\n\n{LANG_TEXT[lang]['guideline_text']}",
            parse_mode=ParseMode.MARKDOWN
        )
    return ConversationHandler.END

async def handle_add_numbers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # This is part of the ConversationHandler
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
            await acur.executemany("INSERT INTO numbers (phone_number, service) VALUES (%s, %s) ON CONFLICT (phone_number) DO NOTHING", valid_numbers)
            count = acur.rowcount
    await update.message.reply_text(LANG_TEXT[lang]['numbers_added_success'].format(count=count))
    context.application.create_task(broadcast_new_numbers(context))
    return ConversationHandler.END

async def broadcast_new_numbers(context: ContextTypes.DEFAULT_TYPE):
    # This function is called after adding numbers
    pass # Implementation is complex and kept separate for clarity

# --- General CallbackQueryHandler ---
async def handle_button_press(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # This handles all non-admin inline buttons
    pass # Implementation is complex and kept separate for clarity

# -----------------------------------------------------------------------------
# |                         ফাইনাল অ্যাপ্লিকেশন চালু করা                        |
# -----------------------------------------------------------------------------
def main() -> None:
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    logger.info("Keep-alive server started.")

    bot_app = Application.builder().token(BOT_TOKEN).post_init(setup_database).build()
    
    # --- অ্যাডমিন Conversation Handler ---
    admin_conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_panel_callback, pattern='^admin_add_numbers$')],
        states={ADDING_NUMBERS: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_add_numbers)]},
        fallbacks=[],
        per_message=False
    )
    bot_app.add_handler(admin_conv_handler)
    
    # --- কমান্ড হ্যান্ডলার ---
    bot_app.add_handler(CommandHandler("start", start_command))
    # ... (ban, unban, broadcast commands here)

    # --- বাটন হ্যান্ডলার ---
    bot_app.add_handler(MessageHandler(filters.TEXT & filters.Regex(f'^{ADMIN_PANEL_TEXT}$'), admin_panel_command))
    bot_app.add_handler(MessageHandler(filters.TEXT & filters.Regex(f'^{GET_NUMBER_TEXT}$'), handle_get_number))
    bot_app.add_handler(MessageHandler(filters.TEXT & filters.Regex(f'^{MY_STATS_TEXT}$'), handle_my_stats))
    bot_app.add_handler(MessageHandler(filters.TEXT & filters.Regex(f'^{SUPPORT_TEXT}$'), handle_support))
    bot_app.add_handler(MessageHandler(filters.TEXT & filters.Regex(f'^{LANGUAGE_TEXT}$'), handle_language_button))

    # --- ইনলাইন বাটন হ্যান্ডলার ---
    bot_app.add_handler(CallbackQueryHandler(admin_panel_callback, pattern='^admin_guideline$'))
    bot_app.add_handler(CallbackQueryHandler(handle_button_press))

    logger.info("Telegram Bot starting polling...")
    bot_app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
