import logging
import datetime
import psycopg
import threading
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ForceReply
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
    ConversationHandler,
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
MENU_ICON = "❖" # মেন্যু আইকন

# -----------------------------------------------------------------------------
# |          Flask অ্যাপ (UptimeRobot ছাড়াই বটকে সচল রাখার জন্য)          |
# -----------------------------------------------------------------------------
flask_app = Flask(__name__)
@flask_app.route('/')
def index():
    return "Bot is running perfectly!", 200

# -----------------------------------------------------------------------------
# |                      লগিং সেটআপ (অপ্রয়োজনীয় লগ বন্ধ)                       |
# -----------------------------------------------------------------------------
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

# -----------------------------------------------------------------------------
# |                      ডাটাবেস সেটআপ এবং সংযোগ                            |
# -----------------------------------------------------------------------------
async def get_db_conn():
    return await psycopg.AsyncConnection.connect(DATABASE_URL)

async def setup_database(app: Application):
    logger.info("Connecting to database and creating/updating tables...")
    try:
        async with await get_db_conn() as aconn:
            async with aconn.cursor() as acur:
                # users টেবিল (নতুন last_notification_id কলাম সহ)
                await acur.execute("""
                    CREATE TABLE IF NOT EXISTS users (
                        user_id BIGINT PRIMARY KEY,
                        first_name VARCHAR(255),
                        strikes INT DEFAULT 0,
                        is_banned BOOLEAN DEFAULT FALSE,
                        ban_until TIMESTAMP,
                        last_number_request_time TIMESTAMP,
                        last_notification_id INT
                    );
                """)
                # numbers টেবিল
                await acur.execute("""
                    CREATE TABLE IF NOT EXISTS numbers (
                        id SERIAL PRIMARY KEY, phone_number VARCHAR(25) UNIQUE NOT NULL, service VARCHAR(50) NOT NULL,
                        is_available BOOLEAN DEFAULT TRUE, is_reported BOOLEAN DEFAULT FALSE,
                        assigned_to BIGINT, assigned_at TIMESTAMP
                    );
                """)
        logger.info("SUCCESS: Database setup complete.")
    except Exception as e:
        logger.error(f"CRITICAL: Database connection failed! Error: {e}")

# -----------------------------------------------------------------------------
# |                          বটের মেন্যু ও বাটন                              |
# -----------------------------------------------------------------------------
async def get_main_menu_keyboard():
    keyboard = [[InlineKeyboardButton(f"{MENU_ICON} Show Options", callback_data="show_services")]]
    return InlineKeyboardMarkup(keyboard)

async def get_services_menu_keyboard(user_id):
    keyboard = [
        [InlineKeyboardButton("💎 Facebook", callback_data="get_number_facebook"), InlineKeyboardButton("✈️ Telegram", callback_data="get_number_telegram")],
        [InlineKeyboardButton("💬 WhatsApp", callback_data="get_number_whatsapp"), InlineKeyboardButton("📞 Support", url=f"https://t.me/{SUPPORT_USERNAME}")],
        [InlineKeyboardButton("🔙 Back", callback_data="back_to_main")]
    ]
    # শুধু অ্যাডমিনের জন্য 'Admin Panel' বাটন দেখানো হবে
    if user_id == ADMIN_USER_ID:
        keyboard.append([InlineKeyboardButton("👑 Admin Panel 👑", callback_data="admin_panel_main")])
    return InlineKeyboardMarkup(keyboard)

# -----------------------------------------------------------------------------
# |                          প্রধান কমান্ড এবং বাটন ক্লিক                       |
# -----------------------------------------------------------------------------
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    logger.info(f"User started: {user.first_name} (ID: {user.id})")
    async with await get_db_conn() as aconn:
        async with aconn.cursor() as acur:
            # নতুন ব্যবহারকারীকে যোগ করা বা পুরনো ব্যবহারকারীর নাম আপডেট করা
            await acur.execute("""
                INSERT INTO users (user_id, first_name) VALUES (%s, %s)
                ON CONFLICT (user_id) DO UPDATE SET first_name = %s
            """, (user.id, user.first_name, user.first_name))
    
    await update.message.reply_photo(
        photo="https://telegra.ph/file/a4092929015c721c5970c.jpg",
        caption=f"👋 **Welcome, {user.first_name}!**\n\nClick the button below to see available services for OTP verification.",
        reply_markup=await get_main_menu_keyboard(),
        parse_mode='Markdown'
    )

async def handle_button_clicks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if query.data == "show_services":
        await query.edit_message_caption(
            caption="**Please select a service:**\n\nChoose one of the options below to get a number.",
            reply_markup=await get_services_menu_keyboard(user_id),
            parse_mode='Markdown'
        )
    elif query.data == "back_to_main":
        await query.edit_message_caption(
            caption=f"👋 **Welcome!**\n\nClick the button below to see available services for OTP verification.",
            reply_markup=await get_main_menu_keyboard(),
            parse_mode='Markdown'
        )

async def handle_get_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    service = query.data.split("_")[2]

    async with await get_db_conn() as aconn:
        async with aconn.cursor() as acur:
            await acur.execute("SELECT id, phone_number FROM numbers WHERE service = %s AND is_available = TRUE AND is_reported = FALSE ORDER BY RANDOM() LIMIT 1", (service,))
            number_record = await acur.fetchone()
            
            if number_record:
                # নম্বর বরাদ্দ করার লজিক এখানে আসবে...
                await query.edit_message_caption(caption=f"Your number is: `{number_record[1]}`", parse_mode='Markdown')
            else:
                await query.answer("Sorry, no numbers available for this service right now.", show_alert=True)
                await query.edit_message_caption(
                    caption=f"**No Numbers for {service.capitalize()}!** 😔\n\nThe admin will add new numbers soon. You will be notified automatically when they are available.",
                    reply_markup=await get_services_menu_keyboard(user_id),
                    parse_mode='Markdown'
                )

# -----------------------------------------------------------------------------
# |                অ্যাডমিন প্যানেল এবং নোটিফিকেশন সিস্টেম                       |
# -----------------------------------------------------------------------------
SERVICE, NUMBERS = range(2)

async def admin_panel_main(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    keyboard = [
        [InlineKeyboardButton("➕ Add Numbers", callback_data="admin_add_numbers")],
        [InlineKeyboardButton("📊 Get Stats", callback_data="admin_get_stats")],
        [InlineKeyboardButton("🔙 Back to Options", callback_data="show_services")]
    ]
    await query.edit_message_caption(caption="👑 **Admin Panel**\n\nWelcome, Admin! What do you want to do?", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def add_numbers_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    keyboard = [
        [InlineKeyboardButton("Facebook", callback_data="service_facebook"), InlineKeyboardButton("Telegram", callback_data="service_telegram")],
        [InlineKeyboardButton("WhatsApp", callback_data="service_whatsapp"), InlineKeyboardButton("Cancel", callback_data="admin_cancel")]
    ]
    await query.edit_message_caption(caption="**Step 1:** Select the service for adding numbers.", reply_markup=InlineKeyboardMarkup(keyboard))
    return SERVICE

async def add_numbers_ask(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    service = query.data.split("_")[1]
    context.user_data['service_to_add'] = service
    await query.edit_message_caption(caption=f"**Step 2:** Send me the numbers for **{service.capitalize()}**.\n\nSend each number on a new line. Send 'cancel' to stop.", parse_mode='Markdown')
    return NUMBERS

async def add_numbers_receive(update: Update, context: ContextTypes.DEFAULT_TYPE):
    service = context.user_data.get('service_to_add')
    if not service: return ConversationHandler.END

    phone_numbers = [num.strip() for num in update.message.text.split('\n') if num.strip()]
    if not phone_numbers: return NUMBERS

    count = 0
    async with await get_db_conn() as aconn:
        async with aconn.cursor() as acur:
            for number in phone_numbers:
                try:
                    await acur.execute("INSERT INTO numbers (phone_number, service) VALUES (%s, %s)", (number, service))
                    count += 1
                except Exception:
                    logger.warning(f"Could not add duplicate number: {number}")
    
    await update.message.reply_text(f"✅ Success! Added **{count}** new numbers for **{service.capitalize()}**.", parse_mode='Markdown')
    
    logger.info(f"Admin added {count} numbers. Notifying all users...")
    context.job_queue.run_once(notify_all_users, 5, data={'service_name': service.capitalize()})
    
    await start_command(update, context) # অ্যাডমিনকে মূল মেন্যু দেখানো
    return ConversationHandler.END

async def notify_all_users(context: ContextTypes.DEFAULT_TYPE):
    service_name = context.job.data['service_name']
    message_text = (
        f"🎉 **Numbers Available!**\n\n"
        f"Good news! New numbers for **{service_name}** have just been added.\n\n"
        f"🗓️ Date: {datetime.datetime.now().strftime('%d %B, %Y')}\n\n"
        "Click the button below to get one now!"
    )
    
    async with await get_db_conn() as aconn:
        async with aconn.cursor() as acur:
            await acur.execute("SELECT user_id, last_notification_id FROM users WHERE is_banned = FALSE")
            all_users = await acur.fetchall()

            for user_id, last_notification_id in all_users:
                # ধাপ ১: আগের নোটিফিকেশন ডিলিট করা
                if last_notification_id:
                    try:
                        await context.bot.delete_message(chat_id=user_id, message_id=last_notification_id)
                    except Exception:
                        logger.info(f"Could not delete old notification for user {user_id}")
                
                # ধাপ ২: নতুন নোটিফিকেশন পাঠানো
                try:
                    sent_message = await context.bot.send_message(
                        chat_id=user_id, 
                        text=message_text, 
                        parse_mode='Markdown',
                        reply_markup=await get_main_menu_keyboard()
                    )
                    # ধাপ ৩: নতুন মেসেজের আইডি ডাটাবেসে সেভ করা
                    await acur.execute("UPDATE users SET last_notification_id = %s WHERE user_id = %s", (sent_message.message_id, user_id))
                except Exception as e:
                    logger.error(f"Failed to send/update notification for user {user_id}: {e}")

async def cancel_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_caption(caption="Operation cancelled.", reply_markup=await get_services_menu_keyboard(update.effective_user.id))
    return ConversationHandler.END

# -----------------------------------------------------------------------------
# |                           অ্যাপ্লিকেশন চালু করা                          |
# -----------------------------------------------------------------------------
def run_bot(app: Application):
    logger.info("Starting bot polling in a separate thread...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

def main() -> None:
    app = Application.builder().token(BOT_TOKEN).post_init(setup_database).build()
    
    add_numbers_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(add_numbers_start, pattern='^admin_add_numbers$')],
        states={
            SERVICE: [CallbackQueryHandler(add_numbers_ask, pattern='^service_')],
            NUMBERS: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_numbers_receive)],
        },
        fallbacks=[CallbackQueryHandler(cancel_conversation, pattern='^admin_cancel$')],
    )
    
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CallbackQueryHandler(handle_button_clicks))
    app.add_handler(CallbackQueryHandler(handle_get_number, pattern="^get_number_"))
    app.add_handler(CallbackQueryHandler(admin_panel_main, pattern="^admin_panel_main$"))
    app.add_handler(add_numbers_handler)
    
    logger.info("BOT CONFIGURED. STARTING WEB SERVER & POLLING...")
    
    bot_thread = threading.Thread(target=run_bot, args=(app,))
    bot_thread.start()
    
    # Render-এর জন্য এই পোর্ট ব্যবহার করা হয়
    flask_app.run(host='0.0.0.0', port=10000)

if __name__ == "__main__":
    main()
