import logging
import datetime
import psycopg
import threading
import os
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

# -----------------------------------------------------------------------------
# |                      ⚠️ আপনার সকল গোপন তথ্য এখানে ⚠️                      |
# -----------------------------------------------------------------------------
BOT_TOKEN = "7925556669:AAE5F9zUGOK37niSd0x-YEQX8rn-xGd8Pl8" # প্রয়োজনে নতুন টোকেন ব্যবহার করুন
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

# --- বহুভাষিক টেক্সট ---
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
        "back_button": "⬅️ Back",
        "main_menu_prompt": "Choose an option from the main menu.",
    }
}

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

# --- ডাটাবেস সেটআপ ফাংশন (সমস্যা সমাধান করা হয়েছে) ---
async def setup_database(app: Application):
    logger.info("Connecting to database and verifying schema...")
    try:
        async with await get_db_conn() as aconn:
            async with aconn.cursor() as acur:
                # ধাপ ১: টেবিলগুলো তৈরি আছে কিনা তা নিশ্চিত করা
                await acur.execute("""
                    CREATE TABLE IF NOT EXISTS users (
                        user_id BIGINT PRIMARY KEY,
                        first_name VARCHAR(255),
                        strikes INT DEFAULT 0,
                        is_banned BOOLEAN DEFAULT FALSE,
                        ban_until TIMESTAMP
                    );
                    CREATE TABLE IF NOT EXISTS numbers (
                        id SERIAL PRIMARY KEY,
                        phone_number VARCHAR(25) UNIQUE NOT NULL,
                        service VARCHAR(50) NOT NULL,
                        is_available BOOLEAN DEFAULT TRUE,
                        is_reported BOOLEAN DEFAULT FALSE,
                        assigned_to BIGINT,
                        assigned_at TIMESTAMP
                    );
                """)
                
                # ধাপ ২: 'language' কলামটি 'users' টেবিলে আছে কিনা তা চেক করা
                await acur.execute("""
                    SELECT 1 FROM information_schema.columns 
                    WHERE table_name='users' AND column_name='language'
                """)
                column_exists = await acur.fetchone()

                # ধাপ ৩: যদি কলামটি না থাকে, তবে এটিকে ডিফল্ট মান দিয়ে যোগ করা
                if not column_exists:
                    logger.warning("Column 'language' not found in 'users' table. Adding it now...")
                    await acur.execute("ALTER TABLE users ADD COLUMN language VARCHAR(5) DEFAULT 'bn';")
                    logger.info("SUCCESS: Column 'language' added to 'users' table.")
        
        logger.info("SUCCESS: Database schema is up-to-date.")
        await app.bot.send_message(
            chat_id=ADMIN_USER_ID, 
            text="✅ **Bot Deployed/Restarted Successfully!**\nDatabase schema is up-to-date.", 
            parse_mode='Markdown'
        )
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

def get_main_reply_keyboard():
    keyboard = [
        [GET_NUMBER_TEXT],
        [MY_STATS_TEXT, SUPPORT_TEXT],
        [LANGUAGE_TEXT]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, input_field_placeholder="Choose an option...")

async def get_number_options_keyboard(lang: str):
    keyboard = [
        [InlineKeyboardButton("💎 Facebook", callback_data="get_number_facebook")],
        [InlineKeyboardButton("✈️ Telegram", callback_data="get_number_telegram")],
        [InlineKeyboardButton("💬 WhatsApp", callback_data="get_number_whatsapp")],
        [InlineKeyboardButton(LANG_TEXT[lang]['back_button'], callback_data="back_to_main")]
    ]
    return InlineKeyboardMarkup(keyboard)

# --- প্রধান কমান্ড হ্যান্ডলার ---
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    logger.info(f"User started: {user.first_name} ({user.id})")
    async with await get_db_conn() as aconn:
        async with aconn.cursor() as acur:
            await acur.execute("INSERT INTO users (user_id, first_name) VALUES (%s, %s) ON CONFLICT (user_id) DO UPDATE SET first_name = EXCLUDED.first_name", (user.id, user.first_name))
    
    lang = await get_user_lang(user.id)
    await update.message.reply_text(
        text=LANG_TEXT[lang]['welcome'].format(first_name=user.first_name),
        reply_markup=get_main_reply_keyboard(),
        parse_mode='Markdown'
    )

async def hide_keyboard_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = await get_user_lang(update.effective_user.id)
    await update.message.reply_text(
        LANG_TEXT[lang]['keyboard_hidden'],
        reply_markup=ReplyKeyboardRemove()
    )

# --- কীবোর্ড বাটন হ্যান্ডলার ---
async def handle_get_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = await get_user_lang(update.effective_user.id)
    reply_markup = await get_number_options_keyboard(lang)
    await update.message.reply_text(text=LANG_TEXT[lang]['choose_service'], reply_markup=reply_markup)

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
                    message += f"{LANG_TEXT[lang]['spam_count']}: `{MAX_STRIKES}/{MAX_STRIKES}`\n"
                    message += f"{LANG_TEXT[lang]['status_banned'].format(hours=BAN_HOURS)}"
                else:
                    message += f"{LANG_TEXT[lang]['status_normal']}"
            else:
                message = LANG_TEXT[lang]['stats_not_found']
    await update.message.reply_text(text=message, parse_mode='Markdown')

async def handle_support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = await get_user_lang(update.effective_user.id)
    support_button = InlineKeyboardButton(
        text=LANG_TEXT[lang]['support_button'],
        url=f"https://t.me/{SUPPORT_USERNAME.lstrip('@')}"
    )
    reply_markup = InlineKeyboardMarkup([[support_button]])
    await update.message.reply_text(text=LANG_TEXT[lang]['support_prompt'], reply_markup=reply_markup)

async def handle_language_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = await get_user_lang(update.effective_user.id)
    keyboard = [
        [InlineKeyboardButton("🇧🇩 বাংলা", callback_data="set_lang_bn")],
        [InlineKeyboardButton("🇬🇧 English", callback_data="set_lang_en")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(text=LANG_TEXT[lang]['choose_language'], reply_markup=reply_markup)

# --- ইনলাইন বাটন ক্লিক হ্যান্ডলার ---
async def handle_button_press(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data
    lang = await get_user_lang(user_id)

    if data.startswith("get_number_"):
        service = data.split("_")[2].capitalize()
        await query.edit_message_text(text=LANG_TEXT[lang]['searching_number'].format(service=service), parse_mode='Markdown')
    
    elif data.startswith("set_lang_"):
        new_lang = data.split("_")[2]
        async with await get_db_conn() as aconn:
            async with aconn.cursor() as acur:
                await acur.execute("UPDATE users SET language = %s WHERE user_id = %s", (new_lang, user_id))
        await query.message.delete()
        await query.message.reply_text(LANG_TEXT[new_lang]['lang_changed'])

    elif data == "back_to_main":
        await query.message.delete()
        await query.message.reply_text(LANG_TEXT[lang]['main_menu_prompt'])

async def handle_unknown_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = await get_user_lang(update.effective_user.id)
    await update.message.reply_text(LANG_TEXT[lang]['unknown_command'])

# -----------------------------------------------------------------------------
# |                         ফাইনাল অ্যাপ্লিকেশন চালু করা                        |
# -----------------------------------------------------------------------------
def main() -> None:
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    logger.info("Keep-alive server started.")

    bot_app = Application.builder().token(BOT_TOKEN).post_init(setup_database).build()
    
    # --- কমান্ড হ্যান্ডলার ---
    bot_app.add_handler(CommandHandler("start", start_command))
    bot_app.add_handler(CommandHandler("hide", hide_keyboard_command))

    # --- ReplyKeyboard বাটনগুলোর জন্য MessageHandler ---
    bot_app.add_handler(MessageHandler(filters.TEXT & filters.Regex(f'^{GET_NUMBER_TEXT}$'), handle_get_number))
    bot_app.add_handler(MessageHandler(filters.TEXT & filters.Regex(f'^{MY_STATS_TEXT}$'), handle_my_stats))
    bot_app.add_handler(MessageHandler(filters.TEXT & filters.Regex(f'^{SUPPORT_TEXT}$'), handle_support))
    bot_app.add_handler(MessageHandler(filters.TEXT & filters.Regex(f'^{LANGUAGE_TEXT}$'), handle_language_button))

    # --- ইনলাইন বাটনের জন্য CallbackQueryHandler ---
    bot_app.add_handler(CallbackQueryHandler(handle_button_press))
    
    # --- অজানা টেক্সট হ্যান্ডেল করার জন্য ---
    bot_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_unknown_text))

    logger.info("Telegram Bot starting polling...")
    bot_app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
