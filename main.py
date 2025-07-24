import logging
import datetime
import asyncpg
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

# -----------------------------------------------------------------------------
# |                      ⚠️ আপনার সকল গোপন তথ্য এখানে ⚠️                      |
# |      এই কোড কারো সাথে শেয়ার করলে আপনার বট এবং ডাটাবেস হ্যাক হতে পারে।       |
# -----------------------------------------------------------------------------
BOT_TOKEN = "7925556669:AAEs8Qpj0jlRAv6FKqhIZplIQ6jlMxs4dHg"
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
# |          লগিং সেটআপ (Render এর অপ্রয়োজনীয় লগ বন্ধ করার জন্য)           |
# -----------------------------------------------------------------------------
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
# নিচের লাইনটি টেলিগ্রাম লাইব্রেরির অপ্রয়োজনীয় ডিবাগ মেসেজ বন্ধ করে দেবে
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

# -----------------------------------------------------------------------------
# |                         ডাটাবেস ফাংশন (সবকিছু এখানে)                       |
# -----------------------------------------------------------------------------
async def setup_database(app: Application):
    """বট চালু হওয়ার সময় স্বয়ংক্রিয়ভাবে ডাটাবেস ও টেবিল তৈরি করবে"""
    logger.info("Connecting to database and creating tables if they don't exist...")
    try:
        conn = await asyncpg.connect(DATABASE_URL)
        # users টেবিল তৈরি
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY, first_name VARCHAR(255), strikes INT DEFAULT 0,
                is_banned BOOLEAN DEFAULT FALSE, ban_until TIMESTAMP, last_number_request_time TIMESTAMP
            );
        """)
        # numbers টেবিল তৈরি
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS numbers (
                id SERIAL PRIMARY KEY, phone_number VARCHAR(25) UNIQUE NOT NULL, service VARCHAR(50) NOT NULL,
                is_available BOOLEAN DEFAULT TRUE, is_reported BOOLEAN DEFAULT FALSE,
                assigned_to BIGINT, assigned_at TIMESTAMP
            );
        """)
        await conn.close()
        logger.info("SUCCESS: Database setup complete.")
    except Exception as e:
        logger.error(f"CRITICAL: Database connection failed! Error: {e}")

# -----------------------------------------------------------------------------
# |                              বটের মূল লজিক                             |
# -----------------------------------------------------------------------------

async def get_main_menu_keyboard(user_id):
    """প্রিমিয়াম ডিজাইনের বাটনসহ প্রধান মেন্যু তৈরি করে"""
    keyboard = [
        [InlineKeyboardButton("💎 Get Facebook Number", callback_data="get_number_facebook")],
        [InlineKeyboardButton("✈️ Get Telegram Number", callback_data="get_number_telegram")],
        [InlineKeyboardButton("💬 Get WhatsApp Number", callback_data="get_number_whatsapp")],
        [
            InlineKeyboardButton("📞 Support", url=f"https://t.me/{SUPPORT_USERNAME}"),
            InlineKeyboardButton("📊 My Stats", callback_data="my_stats")
        ]
    ]
    if user_id == ADMIN_USER_ID:
        keyboard.append([InlineKeyboardButton("👑 Admin Panel 👑", callback_data="admin_panel")])
    return InlineKeyboardMarkup(keyboard)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/start কমান্ড দিলে এই ফাংশন কাজ করবে"""
    user = update.effective_user
    logger.info(f"New user started the bot: {user.first_name} (ID: {user.id})")
    
    # নতুন ব্যবহারকারীকে ডাটাবেসে যোগ করা
    conn = await asyncpg.connect(DATABASE_URL)
    await conn.execute("INSERT INTO users (user_id, first_name) VALUES ($1, $2) ON CONFLICT (user_id) DO NOTHING", user.id, user.first_name)
    await conn.close()
    
    reply_markup = await get_main_menu_keyboard(user.id)
    await update.message.reply_photo(
        photo="https://telegra.ph/file/02194911f26a7962c454e.jpg",
        caption=f"👋 **Welcome, {user.first_name}!**\n\nChoose a service below to get a temporary number. This bot provides premium service for OTP verification.",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def handle_get_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """'Get Number' বাটনে ক্লিক করলে এই ফাংশন কাজ করবে"""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    
    conn = await asyncpg.connect(DATABASE_URL)
    
    # ব্যবহারকারী ব্যানড কিনা চেক করা
    user_data = await conn.fetchrow("SELECT * FROM users WHERE user_id = $1", user_id)
    if user_data['is_banned'] and user_data['ban_until'] and datetime.datetime.utcnow() < user_data['ban_until']:
        remaining_ban = user_data['ban_until'] - datetime.datetime.utcnow()
        await query.edit_message_caption(caption=f"❌ **You are Banned!**\n\nYou are temporarily blocked. Please try again after `{str(remaining_ban).split('.')[0]}`.", parse_mode='Markdown')
        await conn.close()
        return

    # কুলডাউন চেক করা
    if user_data['last_number_request_time']:
        cooldown_end_time = user_data['last_number_request_time'] + datetime.timedelta(minutes=COOLDOWN_MINUTES)
        if datetime.datetime.utcnow() < cooldown_end_time:
            remaining_time = round((cooldown_end_time - datetime.datetime.utcnow()).total_seconds())
            await query.answer(f"Please wait {remaining_time} seconds!", show_alert=True)
            await conn.close()
            return
            
    service = query.data.split("_")[2]
    
    # একটি খালি নম্বর খুঁজে বের করে ব্যবহারকারীকে দেওয়া
    async with conn.transaction():
        number_record = await conn.fetchrow("SELECT * FROM numbers WHERE service = $1 AND is_available = TRUE AND is_reported = FALSE ORDER BY RANDOM() LIMIT 1 FOR UPDATE", service)
        if number_record:
            now_utc = datetime.datetime.utcnow()
            await conn.execute("UPDATE numbers SET is_available = FALSE, assigned_to = $1, assigned_at = $2 WHERE id = $3", user_id, now_utc, number_record['id'])
            await conn.execute("UPDATE users SET last_number_request_time = $1 WHERE user_id = $2", now_utc, user_id)
            phone_number = number_record['phone_number']

            keyboard = [[InlineKeyboardButton("✅ OTP Received, Release Now", callback_data=f"release_success_{number_record['id']}")],
                        [InlineKeyboardButton("❌ Report & Get New One", callback_data=f"release_fail_{number_record['id']}")]
                       ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_caption(
                caption=f"**Your {service.capitalize()} Number:**\n\n`{phone_number}`\n\n_This number is yours for **{LEASE_TIME_MINUTES} minutes**. Copy it and use it quickly!_",
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
            # ১০ মিনিট পর অটো-রিলিজের জন্য কাজ শিডিউল করা
            context.job_queue.run_once(auto_release_callback, LEASE_TIME_MINUTES * 60, data={'user_id': user_id, 'number_id': number_record['id'], 'number_str': phone_number}, name=f"release_{user_id}")
        else:
            await query.answer(f"Sorry, no numbers available for {service.capitalize()} right now.", show_alert=True)
    
    await conn.close()

async def handle_release_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """নম্বর রিলিজ বা রিপোর্ট করার বাটন চাপলে কাজ করবে"""
    query = update.callback_query
    user_id = query.from_user.id
    
    action, status, number_id_str = query.data.split("_")
    number_id = int(number_id_str)
    
    conn = await asyncpg.connect(DATABASE_URL)
    
    if status == "success":
        await query.answer("✅ Great! Releasing number...", show_alert=True)
        await conn.execute("UPDATE numbers SET is_available = TRUE, assigned_to = NULL, assigned_at = NULL WHERE id = $1", number_id)
        await conn.execute("UPDATE users SET strikes = 0 WHERE user_id = $1", user_id)
        await query.edit_message_caption(caption="✅ **Number Released!**\n\nThank you for being responsible! Your previous strikes have been cleared. What's next?", reply_markup=await get_main_menu_keyboard(user_id), parse_mode='Markdown')
    
    elif status == "fail":
        await query.answer("📝 Reporting number and getting you a new one...", show_alert=True)
        # নম্বরটিকে রিপোর্ট করা এবং আবার ব্যবহারের জন্য উন্মুক্ত করা
        await conn.execute("UPDATE numbers SET is_available = TRUE, assigned_to = NULL, is_reported = TRUE WHERE id = $1", number_id)
        number_str_record = await conn.fetchrow("SELECT phone_number, service FROM numbers WHERE id = $1", number_id)
        # অ্যাডমিনকে নোটিফিকেশন পাঠানো
        report_message = (f"🚨 **Number Reported!**\n"
                        f"User: `{user_id}`\n"
                        f"Number: `{number_str_record['phone_number']}` ({number_str_record['service']})\n"
                        f"Status: Marked as 'Not Working'.")
        await context.bot.send_message(ADMIN_CHANNEL_ID, report_message, parse_mode='Markdown')
        # ব্যবহারকারীকে নতুন নম্বর নেওয়ার জন্য প্রধান মেন্যু দেখানো
        await query.edit_message_caption(caption="📝 **Number Reported!**\n\nWe've marked this number for review. You can now request a new number from the main menu without any cooldown.", reply_markup=await get_main_menu_keyboard(user_id), parse_mode='Markdown')

    await conn.close()
    
    # অটো-রিলিজ জবটি খুঁজে বের করে বাতিল করা
    current_jobs = context.job_queue.get_jobs_by_name(f"release_{user_id}")
    for job in current_jobs:
        job.schedule_removal()

async def auto_release_callback(context: ContextTypes.DEFAULT_TYPE):
    """১০ মিনিট পর স্বয়ংক্রিয়ভাবে নম্বর রিলিজ ও স্ট্রাইক দেওয়ার ফাংশন"""
    job_data = context.job.data
    user_id, number_id, number_str = job_data['user_id'], job_data['number_id'], job_data['number_str']

    logger.warning(f"Lease expired for user {user_id} and number {number_str}. Applying strike.")
    conn = await asyncpg.connect(DATABASE_URL)
    
    # নম্বরটি ফেরত নেওয়া
    await conn.execute("UPDATE numbers SET is_available = TRUE, assigned_to = NULL, assigned_at = NULL WHERE id = $1", number_id)
    
    # স্ট্রাইক দেওয়া
    new_strikes = await conn.fetchval("UPDATE users SET strikes = strikes + 1 WHERE user_id = $1 RETURNING strikes", user_id)
    
    # অ্যাডমিনকে নোটিফাই করা
    admin_message = (f"⏰ **Lease Expired & Strike Added!**\n"
                     f"User ID: `{user_id}`\n"
                     f"Number: `{number_str}`\n"
                     f"Action: Auto-released, 1 strike added. Total strikes: **{new_strikes}/{MAX_STRIKES}**.")
    await context.bot.send_message(ADMIN_CHANNEL_ID, admin_message, parse_mode='Markdown')

    # ব্যবহারকারীকে ব্যান করা যদি সর্বোচ্চ স্ট্রাইক হয়ে যায়
    if new_strikes >= MAX_STRIKES:
        ban_until = datetime.datetime.utcnow() + datetime.timedelta(hours=BAN_HOURS)
        await conn.execute("UPDATE users SET is_banned = TRUE, ban_until = $1, strikes = 0 WHERE user_id = $2", ban_until, user_id)
        await context.bot.send_message(user_id, f"❌ **You have been BANNED for {BAN_HOURS} hours!**\n\nYou failed to release numbers {MAX_STRIKES} times in a row. Your strikes have been reset.", parse_mode='Markdown')
        await context.bot.send_message(ADMIN_CHANNEL_ID, f"🚫 **User Banned!**\nUser ID: `{user_id}` has been automatically banned for {BAN_HOURS} hours.", parse_mode='Markdown')
    else:
        await context.bot.send_message(user_id, f"⚠️ **Number Lease Expired!**\n\nYour lease for `{number_str}` has ended. It has been auto-released and you have received **1 strike**.\n\nTotal Strikes: `{new_strikes}/{MAX_STRIKES}`.", parse_mode='Markdown')
        
    await conn.close()

# -----------------------------------------------------------------------------
# |                           অ্যাপ্লিকেশন চালু করা                          |
# -----------------------------------------------------------------------------
def main() -> None:
    """বটটিকে চালু এবং চলমান রাখে"""
    # post_init=setup_database মানে হলো, বট চালু হওয়ার আগেই ডাটাবেস সেটআপ ফাংশনটি কাজ করবে
    app = Application.builder().token(BOT_TOKEN).post_init(setup_database).build()
    
    # কোন কমান্ড বা বাটনে কোন ফাংশন কাজ করবে তা নির্ধারণ করা
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CallbackQueryHandler(handle_get_number, pattern="^get_number_"))
    app.add_handler(CallbackQueryHandler(handle_release_number, pattern="^release_"))
    # এখানে অ্যাডমিন প্যানেলের জন্য আরও হ্যান্ডলার যোগ করতে হবে
    
    logger.info("BOT HAS STARTED SUCCESSFULLY! Polling for updates...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
