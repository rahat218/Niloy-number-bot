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
ADMIN_CHANNEL_ID = -4611753759
ADMIN_USER_ID = 7052442701
SUPPORT_USERNAME = "@NgRony"

# --- বটের সেটিংস ---
LEASE_TIME_MINUTES = 10
COOLDOWN_MINUTES = 2
MAX_STRIKES = 3
BAN_HOURS = 24

# --- বাটন টেক্সট (ইমোজি সহ) ---
GET_NUMBER_TEXT = "☎️ Get Number ☎️"
MY_STATS_TEXT = "📊 My Stats"
SUPPORT_TEXT = "📞 Support"
ADMIN_PANEL_TEXT = "👑 Admin Panel 👑"


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
        await app.bot.send_message(chat_id=ADMIN_USER_ID, text="✅ **Bot Deployed/Restarted Successfully!**\nEverything is online and working.", parse_mode='Markdown')
    except Exception as e:
        logger.error(f"CRITICAL: Database or boot failure! Error: {e}")

# -----------------------------------------------------------------------------
# |                      টেলিগ্রাম বটের সকল হ্যান্ডলার                       |
# -----------------------------------------------------------------------------

# --- ReplyKeyboardMarkup (স্থায়ী কীবোর্ড) তৈরির ফাংশন ---
def get_main_reply_keyboard():
    keyboard = [
        [GET_NUMBER_TEXT],
        [MY_STATS_TEXT, SUPPORT_TEXT]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, input_field_placeholder="Choose an option...")

# --- InlineKeyboardMarkup (অ্যাডমিনের জন্য) ---
async def get_number_options_keyboard():
    keyboard = [
        [InlineKeyboardButton("💎 Facebook", callback_data="get_number_facebook")],
        [InlineKeyboardButton("✈️ Telegram", callback_data="get_number_telegram")],
        [InlineKeyboardButton("💬 WhatsApp", callback_data="get_number_whatsapp")],
        [InlineKeyboardButton("⬅️ পিছনে", callback_data="back_to_main")]
    ]
    return InlineKeyboardMarkup(keyboard)

async def get_admin_panel_keyboard():
    keyboard = [
        [InlineKeyboardButton("➕ Add Number", callback_data="admin_add_number"), InlineKeyboardButton("📊 View Stats", callback_data="admin_view_stats")],
        [InlineKeyboardButton("🚫 Manage Bans", callback_data="admin_manage_bans")],
        [InlineKeyboardButton("⬅️ Back to Main Menu", callback_data="back_to_main")]
    ]
    return InlineKeyboardMarkup(keyboard)


# --- প্রধান কমান্ড হ্যান্ডলার ---
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    logger.info(f"User started: {user.first_name} ({user.id})")
    async with await get_db_conn() as aconn:
        async with aconn.cursor() as acur:
            await acur.execute("INSERT INTO users (user_id, first_name) VALUES (%s, %s) ON CONFLICT (user_id) DO UPDATE SET first_name = EXCLUDED.first_name", (user.id, user.first_name))
    
    reply_markup = get_main_reply_keyboard()
    await update.message.reply_text(
        text=f"👋 **স্বাগতম, {user.first_name}!**\n\nনিচের কীবোর্ড থেকে একটি অপশন বেছে নিন।",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

# --- কীবোর্ড বাটন হ্যান্ডলার (MessageHandler ব্যবহার করে) ---
async def handle_get_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ 'Get Number' বাটনের জন্য কাজ করে """
    reply_markup = await get_number_options_keyboard()
    await update.message.reply_text(
        text="🔢 কোন সার্ভিসের জন্য নম্বর প্রয়োজন? অনুগ্রহ করে বেছে নিন:",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def handle_my_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ 'My Stats' বাটনের জন্য কাজ করে """
    user_id = update.effective_user.id
    async with await get_db_conn() as aconn:
        async with aconn.cursor(row_factory=psycopg.rows.dict_row) as acur:
            await acur.execute("SELECT strikes, is_banned, ban_until FROM users WHERE user_id = %s", (user_id,))
            stats = await acur.fetchone()
            if stats:
                ban_status = "হ্যাঁ" if stats['is_banned'] else "না"
                message = (
                    f"📊 **আপনার পরিসংখ্যান**\n\n"
                    f"ஸ்ட்ரைக்: `{stats['strikes']}/{MAX_STRIKES}`\n"
                    f"নিষিদ্ধ: `{ban_status}`"
                )
                if stats['is_banned'] and stats['ban_until']:
                    message += f"\nনিষেধাজ্ঞা শেষ হবে: `{stats['ban_until'].strftime('%Y-%m-%d %H:%M:%S')}`"
            else:
                message = "আপনার পরিসংখ্যান খুঁজে পাওয়া যায়নি। অনুগ্রহ করে /start কমান্ড দিন।"
    await update.message.reply_text(text=message, parse_mode='Markdown')

async def handle_support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ 'Support' বাটনের জন্য কাজ করে """
    await update.message.reply_text(
        text=f"📞 যে কোন প্রয়োজনে আমাদের সাপোর্ট টিমের সাথে যোগাযোগ করুন: {SUPPORT_USERNAME}",
        parse_mode='Markdown'
    )

# --- শুধুমাত্র অ্যাডমিনের জন্য বিশেষ কমান্ড ---
async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id == ADMIN_USER_ID:
        reply_markup = await get_admin_panel_keyboard()
        await update.message.reply_text(
            text="👑 **অ্যাডমিন প্যানেলে স্বাগতম**\n\nএকটি অপশন বেছে নিন:",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    else:
        await update.message.reply_text("❌ এই কমান্ডটি শুধুমাত্র অ্যাডমিনের জন্য সংরক্ষিত।")


# --- ইনলাইন বাটন ক্লিক হ্যান্ডলার ---
async def handle_button_press(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data
    logger.info(f"Button '{data}' pressed by user {user_id}")

    if data.startswith("get_number_"):
        service = data.split("_")[2].capitalize()
        async with await get_db_conn() as aconn:
            async with aconn.cursor(row_factory=psycopg.rows.dict_row) as acur:
                await acur.execute("SELECT is_banned FROM users WHERE user_id = %s", (user_id,))
                user_data = await acur.fetchone()
                if user_data and user_data['is_banned']:
                    await query.edit_message_text(text="❌ **আপনি বর্তমানে নিষিদ্ধ!**", parse_mode='Markdown')
                    return
        await query.edit_message_text(
            text=f"🔍 আপনার জন্য একটি অস্থায়ী **{service}** নম্বর খোঁজা হচ্ছে...",
            parse_mode='Markdown'
        )
        # To-Do: নম্বর খোঁজার লজিক এখানে যুক্ত হবে।

    elif data == "admin_panel": # অ্যাডমিন প্যানেলে ফেরার জন্য
        if user_id == ADMIN_USER_ID:
            reply_markup = await get_admin_panel_keyboard()
            await query.edit_message_text(text="👑 **অ্যাডমিন প্যানেলে স্বাগতম**", reply_markup=reply_markup, parse_mode='Markdown')

    elif data == "admin_add_number":
        await query.edit_message_text(text="নম্বর যোগ করতে, ফরম্যাটে পাঠান: `+1234567890, ServiceName`", parse_mode='Markdown')

    elif data == "admin_view_stats":
        await query.edit_message_text(text="সিস্টেমের পরিসংখ্যান (এখনও তৈরি হয়নি)", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ পিছনে", callback_data="admin_panel")]]))

    elif data == "back_to_main":
        await query.edit_message_text(
            text="প্রধান মেনু থেকে একটি অপশন বেছে নিন।",
            parse_mode='Markdown'
        )


async def handle_unknown_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"Received unknown text from user {update.effective_user.id}: '{update.message.text}'")
    await update.message.reply_text(text="🤔 দুঃখিত, কমান্ডটি বুঝতে পারিনি। অনুগ্রহ করে কীবোর্ডের বাটন ব্যবহার করুন।")


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
    bot_app.add_handler(CommandHandler("admin", admin_command)) # অ্যাডমিন কমান্ড

    # --- ReplyKeyboard বাটনগুলোর জন্য MessageHandler ---
    bot_app.add_handler(MessageHandler(filters.TEXT & filters.Regex(f'^{GET_NUMBER_TEXT}$'), handle_get_number))
    bot_app.add_handler(MessageHandler(filters.TEXT & filters.Regex(f'^{MY_STATS_TEXT}$'), handle_my_stats))
    bot_app.add_handler(MessageHandler(filters.TEXT & filters.Regex(f'^{SUPPORT_TEXT}$'), handle_support))

    # --- ইনলাইন বাটনের জন্য CallbackQueryHandler ---
    bot_app.add_handler(CallbackQueryHandler(handle_button_press))
    
    # --- অজানা টেক্সট হ্যান্ডেল করার জন্য ---
    bot_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_unknown_text))

    logger.info("Telegram Bot starting polling...")
    bot_app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
