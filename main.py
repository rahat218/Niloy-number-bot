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
    MessageHandler,
    filters,
    ContextTypes,
)

# -----------------------------------------------------------------------------
# |                      ⚠️ আপনার সকল গোপন তথ্য এখানে ⚠️                      |
# -----------------------------------------------------------------------------
# অনুগ্রহ করে আপনার নিজের টোকেন এবং ডাটাবেস ইউআরএল ব্যবহার করুন
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

# --- মেনু তৈরির ফাংশন (আপনার অনুরোধ অনুযায়ী পরিবর্তিত) ---
async def get_main_menu_keyboard(user_id):
    # প্রধান মেনুতে এখন শুধু একটি "সকল অপশন" বাটন থাকবে
    keyboard = [
        [InlineKeyboardButton("🎛️ সকল অপশন দেখুন 🎛️", callback_data="show_all_options")]
    ]
    # ব্যবহারকারী যদি অ্যাডমিন হন, তবেই কেবল অ্যাডমিন প্যানেল বাটনটি দেখানো হবে
    if user_id == ADMIN_USER_ID:
        keyboard.append([InlineKeyboardButton("👑 Admin Panel 👑", callback_data="admin_panel")])
    return InlineKeyboardMarkup(keyboard)

async def get_all_options_keyboard():
    # এই ফাংশনটি আগের সব বাটনগুলো দেখাবে
    keyboard = [
        [InlineKeyboardButton("💎 Get Facebook Number", callback_data="get_number_facebook")],
        [InlineKeyboardButton("✈️ Get Telegram Number", callback_data="get_number_telegram")],
        [InlineKeyboardButton("💬 Get WhatsApp Number", callback_data="get_number_whatsapp")],
        [InlineKeyboardButton("📞 Support", url=f"https://t.me/{SUPPORT_USERNAME}"), InlineKeyboardButton("📊 My Stats", callback_data="my_stats")],
        [InlineKeyboardButton("⬅️ প্রধান মেনু", callback_data="back_to_main")] # পিছনে যাওয়ার বাটন
    ]
    return InlineKeyboardMarkup(keyboard)

async def get_admin_panel_keyboard():
    keyboard = [
        [InlineKeyboardButton("➕ Add Number", callback_data="admin_add_number"), InlineKeyboardButton("📊 View Stats", callback_data="admin_view_stats")],
        [InlineKeyboardButton("🚫 Manage Bans", callback_data="admin_manage_bans")],
        [InlineKeyboardButton("⬅️ Back to Main Menu", callback_data="back_to_main")]
    ]
    return InlineKeyboardMarkup(keyboard)


# --- কমান্ড হ্যান্ডলার ---
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    logger.info(f"User started: {user.first_name} ({user.id})")
    async with await get_db_conn() as aconn:
        async with aconn.cursor() as acur:
            await acur.execute("INSERT INTO users (user_id, first_name) VALUES (%s, %s) ON CONFLICT (user_id) DO UPDATE SET first_name = EXCLUDED.first_name", (user.id, user.first_name))
    
    reply_markup = await get_main_menu_keyboard(user.id)
    await update.message.reply_text(
        text=f"👋 **Welcome, {user.first_name}!**\n\nChoose a service below to get a temporary number.",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )


# --- টেক্সট মেসেজ হ্যান্ডলার ---
async def handle_unknown_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """কোনো ব্যবহারকারী আজেবাজে বা অজানা টেক্সট পাঠালে এই ফাংশনটি কাজ করবে"""
    logger.info(f"Received unknown text from user {update.effective_user.id}: '{update.message.text}'")
    reply_markup = await get_main_menu_keyboard(update.effective_user.id)
    await update.message.reply_text(
        text="🤔 দুঃখিত, আমি আপনার কথাটি বুঝতে পারিনি।\n\nঅনুগ্রহ করে নিচের বাটনগুলো ব্যবহার করে আপনার প্রয়োজনীয় সেবাটি বেছে নিন।",
        reply_markup=reply_markup
    )


# --- বাটন ক্লিক হ্যান্ডলার (সম্পূর্ণ সংশোধিত) ---
async def handle_button_press(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()  # বাটন ক্লিকের "লোডিং" অ্যানিমেশন বন্ধ করার জন্য এটি জরুরি
    user_id = query.from_user.id
    data = query.data
    logger.info(f"Button '{data}' pressed by user {user_id}")
    
    # --- নতুন "সকল অপশন" বাটন হ্যান্ডেল করা ---
    if data == "show_all_options":
        reply_markup = await get_all_options_keyboard()
        await query.edit_message_text(
            text="⚙️ **সকল অপশন**\n\nঅনুগ্রহ করে আপনার প্রয়োজনীয় সেবাটি বেছে নিন:",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

    # --- প্রধান মেনু থেকে আসা ডেটা হ্যান্ডেল করা ---
    elif data.startswith("get_number_"):
        service = data.split("_")[2].capitalize()
        
        async with await get_db_conn() as aconn:
            async with aconn.cursor(row_factory=psycopg.rows.dict_row) as acur:
                await acur.execute("SELECT * FROM users WHERE user_id = %s", (user_id,))
                user_data = await acur.fetchone()

                if user_data and user_data['is_banned']:
                    await query.edit_message_text(text="❌ **আপনি বর্তমানে নিষিদ্ধ!**\n\nনির্দিষ্ট সময় পর আবার চেষ্টা করুন।", parse_mode='Markdown')
                    return
                
                # To-Do: কুলডাউন চেক করার লজিক এখানে যোগ করতে হবে

        # নম্বর খোঁজার মেসেজ দেখানো
        await query.edit_message_text(
            text=f"🔍 আপনার জন্য একটি অস্থায়ী **{service}** নম্বর খোঁজা হচ্ছে...\nঅনুগ্রহ করে অপেক্ষা করুন।",
            parse_mode='Markdown'
        )
        # To-Do: এখানে ডাটাবেস থেকে নম্বর খুঁজে এনে ব্যবহারকারীকে পাঠানোর আসল কোড লিখতে হবে।
        # উদাহরণ:
        # number = await find_available_number(service)
        # if number:
        #     await query.edit_message_text(f"আপনার নম্বর: {number}")
        # else:
        #     await query.edit_message_text("দুঃখিত, এই মুহূর্তে কোনো নম্বর উপলব্ধ নেই।")

    elif data == "my_stats":
        async with await get_db_conn() as aconn:
            async with aconn.cursor(row_factory=psycopg.rows.dict_row) as acur:
                await acur.execute("SELECT strikes, is_banned, ban_until FROM users WHERE user_id = %s", (user_id,))
                stats = await acur.fetchone()
                if stats:
                    ban_status = "হ্যাঁ" if stats['is_banned'] else "না"
                    message = (
                        f"📊 **আপনার পরিসংখ্যান**\n\n"
                        f"স্ট্রাইক: `{stats['strikes']}/{MAX_STRIKES}`\n"
                        f"নিষিদ্ধ: `{ban_status}`"
                    )
                    if stats['is_banned'] and stats['ban_until']:
                        message += f"\nনিষেধাজ্ঞা শেষ হবে: `{stats['ban_until'].strftime('%Y-%m-%d %H:%M:%S')}`"
                else:
                    message = "আপনার পরিসংখ্যান খুঁজে পাওয়া যায়নি। অনুগ্রহ করে /start কমান্ড দিন।"
        
        # এখানে 'পিছনে' বাটনটিকে 'back_to_main' এর পরিবর্তে 'show_all_options' এ পাঠানো হলো যাতে এটি ড্রপ-ডাউন মেনুতে ফিরে যায়
        reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ পিছনে", callback_data="show_all_options")]])
        await query.edit_message_text(text=message, reply_markup=reply_markup, parse_mode='Markdown')

    elif data == "admin_panel":
        if user_id == ADMIN_USER_ID:
            reply_markup = await get_admin_panel_keyboard()
            await query.edit_message_text(text="👑 **অ্যাডমিন প্যানেলে স্বাগতম**\n\nনিচের একটি অপশন বেছে নিন:", reply_markup=reply_markup, parse_mode='Markdown')
        else:
            await query.answer("আপনি এই মেনুটি ব্যবহার করার জন্য অনুমোদিত নন।", show_alert=True)

    # --- অ্যাডমিন প্যানেলের বাটনগুলো হ্যান্ডেল করা ---
    elif data == "admin_add_number":
        await query.edit_message_text(text="নম্বর যোগ করতে, অনুগ্রহ করে এই ফরম্যাটে পাঠান: `+1234567890, ServiceName` (যেমন, `+99123456, Facebook`)", parse_mode='Markdown')
        # To-Do: এরপর MessageHandler দিয়ে ইনপুট নেওয়ার লজিক বানাতে হবে।

    elif data == "admin_view_stats":
        # To-Do: ডাটাবেস থেকে মোট ইউজার, ব্যানড ইউজার, উপলব্ধ নম্বর ইত্যাদির তথ্য দেখানোর কোড।
        await query.edit_message_text(text="সিস্টেমের পরিসংখ্যান দেখা হচ্ছে... (এই ফিচারটি এখনো তৈরি করা হয়নি)", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ পিছনে", callback_data="admin_panel")]]))

    # --- পিছনে যাওয়ার বাটন ---
    elif data == "back_to_main":
        user = query.from_user
        reply_markup = await get_main_menu_keyboard(user.id)
        await query.edit_message_text(
            text=f"👋 **স্বাগতম, {user.first_name}!**\n\nএকটি অস্থায়ী নম্বর পেতে নিচের সেবাগুলো থেকে বেছে নিন।",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

# --- সময় শেষ হলে নম্বর রিলিজ করার কলব্যাক (এখনও খালি) ---
async def auto_release_callback(context: ContextTypes.DEFAULT_TYPE):
    # To-Do: এই ফাংশনটি পরে ডেভেলপ করতে হবে
    pass

# -----------------------------------------------------------------------------
# |                         ফাইনাল অ্যাপ্লিকেশন চালু করা                        |
# -----------------------------------------------------------------------------
def main() -> None:
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    logger.info("Keep-alive server started.")

    bot_app = Application.builder().token(BOT_TOKEN).post_init(setup_database).build()
    
    # --- হ্যান্ডলারগুলো যোগ করা ---
    bot_app.add_handler(CommandHandler("start", start_command))
    bot_app.add_handler(CallbackQueryHandler(handle_button_press))
    
    # এই লাইনটি যেকোনো টেক্সট মেসেজ (যা কমান্ড নয়) হ্যান্ডেল করার জন্য
    bot_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_unknown_text))

    logger.info("Telegram Bot starting polling...")
    bot_app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
