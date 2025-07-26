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
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
    JobQueue,
)
from telegram.error import Forbidden, BadRequest

# -----------------------------------------------------------------------------
# |                      ⚠️ আপনার সকল গোপন তথ্য এখানে ⚠️                      |
# -----------------------------------------------------------------------------

BOT_TOKEN = "7925556669:AAE5F9zUGOK37niSd0x-YEQX8rn-xGd8Pl8"  # প্রয়োজনে নতুন টোকেন ব্যবহার করুন
DATABASE_URL = "postgresql://number_bot_running_user:kpQLHQIuZF68uc7fMlgFiaNoV7JzemyL@dpg-d21qr663jp1c73871p20-a/number_bot_running"
ADMIN_USER_ID = 7052442701
SUPPORT_USERNAME = "@NgRony"

# --- বটের সেটিংস ---
MAX_STRIKES = 3
BAN_HOURS = 24
COOLDOWN_MINUTES = 2  # সফলভাবে নম্বর ব্যবহারের পর কুলডাউন (মিনিট)
INACTIVITY_MINUTES = 5  # নম্বর নিয়ে OTP ইনপুট না দিলে স্ট্রাইক (মিনিট)

# --- বাটন টেক্সট ---
GET_NUMBER_TEXT = "✨ Get Number 🎗️"
MY_STATS_TEXT = "📊 My Stats"
SUPPORT_TEXT = "📞 Support"
LANGUAGE_TEXT = "🌐 Language"
ADMIN_PANEL_TEXT = "👑 Admin Panel 👑"

# --- বহুভাষিক টেক্সট ---
LANG_TEXT = {
    'bn': {
        "welcome": "👋 স্বাগতম, {first_name}!\n\nনিচের কীবোর্ড থেকে একটি অপশন বেছে নিন।",
        "keyboard_hidden": "কীবোর্ড লুকানো হয়েছে। আবার দেখতে /start চাপুন।",
        "choose_service": "🔢 কোন সার্ভিসের জন্য নম্বর প্রয়োজন? অনুগ্রহ করে বেছে নিন:",
        "stats_header": "📊 আপনার পরিসংখ্যান",
        "strikes": "স্ট্রাইক",
        "status_banned": "অ্যাকাউন্ট স্ট্যাটাস: {hours} ঘণ্টার জন্য নিষিদ্ধ। সমাপ্তির সময়: {unban_time}",
        "status_normal": "স্ট্যাটাস: সাধারণ ব্যবহারকারী",
        "stats_not_found": "আপনার পরিসংখ্যান খুঁজে পাওয়া যায়নি। অনুগ্রহ করে /start কমান্ড দিন।",
        "support_prompt": "📞 যে কোন প্রয়োজনে আমাদের সাপোর্ট টিমের সাথে যোগাযোগ করতে নিচের বাটনে ক্লিক করুন।",
        "support_button": "সাপোর্টে যোগাযোগ করুন",
        "unknown_command": "🤔 দুঃখিত, কমান্ডটি বুঝতে পারিনি। অনুগ্রহ করে কীবোর্ডের বাটন ব্যবহার করুন।",
        "choose_language": "অনুগ্রহ করে আপনার ভাষা নির্বাচন করুন:",
        "lang_changed": "✅ আপনার ভাষা সফলভাবে 'বাংলা' করা হয়েছে।",
        "searching_number": "🔍 আপনার জন্য একটি {service} নম্বর খোঁজা হচ্ছে...",
        "no_number_available": "❌ দুঃখিত, এই মুহূর্তে {service} সার্ভিসের জন্য কোনো নম্বর খালি নেই! ❌\n\nঅ্যাডমিনকে বিষয়টি জানানো হয়েছে এবং তিনি খুব শীঘ্রই নতুন নম্বর যোগ করবেন।\n\n⏳ অনুগ্রহ করে কিছুক্ষণ পর আবার চেষ্টা করুন।",
        "number_found": "✅ আপনার নম্বরটি নিচে দেওয়া হলো:\n\n`{phone_number}`\n\nএই নম্বরটি ৫ মিনিটের জন্য আপনার। OTP পাওয়ার পর নিচের বাটনে ক্লিক করুন।",
        "otp_received_button": "✅ OTP পেয়েছি",
        "otp_failed_button": "❌ OTP আসেনি (নতুন নম্বর)",
        "report_success": "✅ নম্বরটি সফলভাবে রিপোর্ট করা হয়েছে। আপনার জন্য নতুন নম্বর খোঁজা হচ্ছে...",
        "thank_you_for_otp": "🎉 ধন্যবাদ! আপনার কাজ সফল হয়েছে। আপনি {minutes} মিনিট পর আবার নতুন নম্বর নিতে পারবেন।",
        "cooldown_message": "⏳ অনুগ্রহ করে অপেক্ষা করুন! আপনি শেষবার নম্বর নেওয়ার পর এখনো {minutes} মিনিট পূর্ণ হয়নি।",
        "strike_warning": "⚠️ সতর্কবার্তা! ⚠️\n\nআপনি একটি নম্বর নেওয়ার পর {minutes} মিনিটের মধ্যে কোনো উত্তর দেননি। আপনার বর্তমান স্ট্রাইক: {strikes}/{max_strikes}।",
        "ban_message": "🚫 আপনি নিষিদ্ধ! 🚫\n\nআপনি {max_strikes} বার নিয়ম লঙ্ঘন করায় আপনাকে স্বয়ংক্রিয়ভাবে {hours} ঘণ্টার জন্য ব্যান করা হয়েছে।",
        "unban_message": "🎉 নিষেধাজ্ঞা তুলে নেওয়া হয়েছে! 🎉\n\nআপনার ২৪ ঘণ্টার নিষেধাজ্ঞা শেষ হয়েছে। আপনার স্ট্রাইক রিসেট করা হয়েছে।",
        "admin_panel_prompt": "👑 অ্যাডমিন প্যানেলে স্বাগতম 👑",
        "add_number_prompt": "➕ নম্বর যোগ করতে, ফরম্যাট অনুসরণ করুন:\n`/add <Service> <Number1> <Number2> ...`\nউদাহরণ:\n`/add Facebook 12345 67890`",
        "number_added_success": "✅ সফলভাবে {count} টি নতুন {service} নম্বর যোগ করা হয়েছে।",
        "new_number_broadcast": "🎉 সুখবর! নতুন {service} নম্বর যোগ করা হয়েছে! 🎉\n\nএখনই নম্বর নিতে {get_number_button} বাটনে ক্লিক করুন!",
        "broadcast_deleted": "✅ পূর্বের 'নতুন নম্বর' ঘোষণাটি সফলভাবে ডিলিট করা হয়েছে।",
        "delnum_prompt": "🗑️ নম্বর ডিলিট করতে, ফরম্যাট অনুসরণ করুন:\n`/delnumber <Number>`\nউদাহরণ:\n`/delnumber 12345`",
        "delnum_success": "✅ নম্বর `{number}` সফলভাবে ডিলিট করা হয়েছে।",
        "delnum_not_found": "❌ নম্বর `{number}` খুঁজে পাওয়া যায়নি।",
        "reactivate_prompt": "🔄 নম্বর পুনরায় সক্রিয় করতে:\n`/reactivate <Number>`",
        "reactivate_success": "✅ নম্বর `{number}` সফলভাবে পুনরায় সক্রিয় করা হয়েছে।",
        "view_reported_header": "📄 রিপোর্ট করা নম্বরের তালিকা:",
        "view_expired_header": "⌛ এক্সপায়ার হওয়া নম্বরের তালিকা:",
        "no_reported_numbers": "👍 কোনো রিপোর্ট করা নম্বর নেই।",
        "no_expired_numbers": "👍 কোনো এক্সপায়ার হওয়া নম্বর নেই।",
        "ban_user_prompt": "🚫 ব্যবহারকারী ব্যান করতে:\n`/ban <User_ID>`",
        "ban_success": "✅ ব্যবহারকারী `{user_id}`-কে সফলভাবে ব্যান করা হয়েছে।",
        "unban_user_prompt": "✅ ব্যবহারকারী আনব্যান করতে:\n`/unban <User_ID>`",
        "unban_success": "✅ ব্যবহারকারী `{user_id}`-কে সফলভাবে আনব্যান করা হয়েছে।",
        "user_not_found": "🤷 ব্যবহারকারী `{user_id}`-কে খুঁজে পাওয়া যায়নি।",
        "broadcast_sent": "✅ বার্তাটি সফলভাবে {count} জন ব্যবহারকারীকে পাঠানো হয়েছে।",
        "broadcast_no_message": "❌ অনুগ্রহ করে /broadcast কমান্ডের সাথে একটি বার্তা দিন।",
        "delbroadcast_success": "✅ সর্বশেষ কাস্টম ঘোষণাটি সফলভাবে ডিলিট করা শুরু হয়েছে।",
        "admin_announcement": "📣 অ্যাডমিনের ঘোষণা 📣",
        "back_button": "⬅️ পিছনে",
        "main_menu_prompt": "প্রধান মেনু থেকে একটি অপশন বেছে নিন।",
    },
    'en': {
        "welcome": "👋 Welcome, {first_name}!\n\nChoose an option from the keyboard below.",
        "keyboard_hidden": "Keyboard hidden. Press /start to show it again.",
        "choose_service": "🔢 Which service do you need a number for? Please choose:",
        "stats_header": "📊 Your Statistics",
        "strikes": "Strikes",
        "status_banned": "Account Status: Banned for {hours} hours. Ends at: {unban_time}",
        "status_normal": "Status: Normal User",
        "stats_not_found": "Your statistics were not found. Please use the /start command.",
        "support_prompt": "📞 To contact our support team for any need, please click the button below.",
        "support_button": "Contact Support",
        "unknown_command": "🤔 Sorry, I didn't understand that command. Please use the keyboard buttons.",
        "choose_language": "Please select your language:",
        "lang_changed": "✅ Your language has been successfully changed to 'English'.",
        "searching_number": "🔍 Searching for a {service} number for you...",
        "no_number_available": "❌ Sorry, no numbers are available for the {service} service right now! ❌\n\nThe admin has been notified and will add new numbers soon.\n\n⏳ Please try again later.",
        "number_found": "✅ Here is your number:\n\n`{phone_number}`\n\nThis number is yours for 5 minutes. Click the button below after receiving the OTP.",
        "otp_received_button": "✅ Got OTP",
        "otp_failed_button": "❌ Didn't get OTP (New Number)",
        "report_success": "✅ Number successfully reported. Searching for a new number for you...",
        "thank_you_for_otp": "🎉 Thank you! Your task was successful. You can get a new number in {minutes} minutes.",
        "cooldown_message": "⏳ Please wait! {minutes} minutes have not yet passed since your last successful use.",
        "strike_warning": "⚠️ Warning! ⚠️\n\nYou did not respond within {minutes} minutes after taking a number. Your current strikes: {strikes}/{max_strikes}.",
        "ban_message": "🚫 You are banned! 🚫\n\nAs you have violated the rules {max_strikes} times, you have been automatically banned for {hours} hours.",
        "unban_message": "🎉 Ban lifted! 🎉\n\nYour 24-hour ban has ended. Your strikes have been reset.",
        "admin_panel_prompt": "👑 Welcome to the Admin Panel 👑",
        "add_number_prompt": "➕ To add numbers, use the format:\n`/add <Service> <Number1> <Number2> ...`\nExample:\n`/add Facebook 12345 67890`",
        "number_added_success": "✅ Successfully added {count} new {service} numbers.",
        "new_number_broadcast": "🎉 Good news! New {service} numbers have been added! 🎉\n\nClick the {get_number_button} button to get one now!",
        "broadcast_deleted": "✅ The previous 'new number' announcement has been successfully deleted.",
        "delnum_prompt": "🗑️ To delete a number, use the format:\n`/delnumber <Number>`\nExample:\n`/delnumber 12345`",
        "delnum_success": "✅ Number `{number}` successfully deleted.",
        "delnum_not_found": "❌ Number `{number}` not found.",
        "reactivate_prompt": "🔄 To reactivate a number:\n`/reactivate <Number>`",
        "reactivate_success": "✅ Number `{number}` successfully reactivated.",
        "view_reported_header": "📄 List of Reported Numbers:",
        "view_expired_header": "⌛ List of Expired Numbers:",
        "no_reported_numbers": "👍 No reported numbers.",
        "no_expired_numbers": "👍 No expired numbers.",
        "ban_user_prompt": "🚫 To ban a user:\n`/ban <User_ID>`",
        "ban_success": "✅ User `{user_id}` has been successfully banned.",
        "unban_user_prompt": "✅ To unban a user:\n`/unban <User_ID>`",
        "unban_success": "✅ User `{user_id}` has been successfully unbanned.",
        "user_not_found": "🤷 User `{user_id}` not found.",
        "broadcast_sent": "✅ Message successfully sent to {count} users.",
        "broadcast_no_message": "❌ Please provide a message with the /broadcast command.",
        "delbroadcast_success": "✅ Deletion of the last custom broadcast has been initiated.",
        "admin_announcement": "📣 Admin Announcement 📣",
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

async def setup_database(app: Application):
    logger.info("Connecting to database and verifying schema...")
    try:
        async with await get_db_conn() as aconn:
            async with aconn.cursor() as acur:
                # টেবিলগুলো তৈরি করা
                await acur.execute("""
                    CREATE TABLE IF NOT EXISTS users (
                        user_id BIGINT PRIMARY KEY,
                        first_name VARCHAR(255),
                        language VARCHAR(5) DEFAULT 'bn',
                        strikes INT DEFAULT 0,
                        is_banned BOOLEAN DEFAULT FALSE,
                        ban_until TIMESTAMP,
                        last_number_success_at TIMESTAMP
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
                    CREATE TABLE IF NOT EXISTS broadcast_messages (
                        id SERIAL PRIMARY KEY,
                        user_id BIGINT NOT NULL,
                        message_id BIGINT NOT NULL,
                        broadcast_type VARCHAR(50) NOT NULL
                    );
                """)
                
                # যদি ডাটাবেস আগে থেকেই তৈরি থাকে, তাহলে কলামটি যোগ করা
                await acur.execute("""
                    SELECT 1 FROM information_schema.columns 
                    WHERE table_name='users' AND column_name='last_number_success_at';
                """)
                if not await acur.fetchone():
                    await acur.execute("ALTER TABLE users ADD COLUMN last_number_success_at TIMESTAMP;")

        logger.info("SUCCESS: Database schema is up-to-date.")
        await app.bot.send_message(chat_id=ADMIN_USER_ID, text="✅ Bot Deployed/Restarted Successfully!", parse_mode='Markdown')
    except Exception as e:
        logger.error(f"CRITICAL: Database or boot failure! Error: {e}")


async def get_user_lang(user_id: int) -> str:
    async with await get_db_conn() as aconn:
        async with aconn.cursor() as acur:
            await acur.execute("SELECT language FROM users WHERE user_id = %s", (user_id,))
            result = await acur.fetchone()
            return result[0] if result and result[0] else 'bn'

# -----FIX: 'is_reported' কলামের নাম এখানে সঠিক করা হয়েছে-----
async def find_available_number(service: str):
    """ডাটাবেস থেকে একটি নির্দিষ্ট সার্ভিসের জন্য উপলব্ধ নম্বর খুঁজে বের করে।"""
    async with await get_db_conn() as aconn:
        async with aconn.cursor(row_factory=psycopg.rows.dict_row) as acur:
            await acur.execute(
                "SELECT id, phone_number FROM numbers WHERE service ILIKE %s AND is_available = TRUE AND is_reported = FALSE ORDER BY id LIMIT 1",
                (service,)
            )
            return await acur.fetchone()

# -----------------------------------------------------------------------------
# |                      স্বয়ংক্রিয় সিস্টেমের জবস (Jobs)                       |
# -----------------------------------------------------------------------------

async def inactivity_strike_job(context: ContextTypes.DEFAULT_TYPE):
    """ব্যবহারকারী নিষ্ক্রিয় থাকলে স্ট্রাইক দেয়।"""
    job = context.job
    user_id = job.data['user_id']
    number_id = job.data['number_id']
    lang = await get_user_lang(user_id)

    async with await get_db_conn() as aconn:
        async with aconn.cursor(row_factory=psycopg.rows.dict_row) as acur:
            # চেক করুন নম্বরটি এখনো সেই ব্যবহারকারীর কাছে আছে কিনা
            await acur.execute("SELECT assigned_to FROM numbers WHERE id = %s", (number_id,))
            result = await acur.fetchone()
            if not result or result['assigned_to'] != user_id:
                return # নম্বরটি ইতিমধ্যে রিলিজ বা রিপোর্ট করা হয়েছে

            # স্ট্রাইক বাড়ান
            await acur.execute("UPDATE users SET strikes = strikes + 1 WHERE user_id = %s RETURNING strikes", (user_id,))
            user_data = await acur.fetchone()
            new_strikes = user_data['strikes']

            # নম্বরটিকে আবার উপলব্ধ করুন (এক্সপায়ারড)
            await acur.execute("UPDATE numbers SET is_available = TRUE, assigned_to = NULL, assigned_at = NULL WHERE id = %s", (number_id,))

            if new_strikes >= MAX_STRIKES:
                ban_until = datetime.datetime.now() + datetime.timedelta(hours=BAN_HOURS)
                await acur.execute("UPDATE users SET is_banned = TRUE, ban_until = %s WHERE user_id = %s", (ban_until, user_id))
                await context.bot.send_message(user_id, LANG_TEXT[lang]['ban_message'].format(max_strikes=MAX_STRIKES, hours=BAN_HOURS))
                
                # আনব্যান করার জন্য জব সেট করুন
                context.job_queue.run_once(auto_unban_job, BAN_HOURS * 3600, data={'user_id': user_id}, name=f"unban_{user_id}")
            else:
                await context.bot.send_message(user_id, LANG_TEXT[lang]['strike_warning'].format(minutes=INACTIVITY_MINUTES, strikes=new_strikes, max_strikes=MAX_STRIKES))

async def auto_unban_job(context: ContextTypes.DEFAULT_TYPE):
    """ব্যবহারকারীকে স্বয়ংক্রিয়ভাবে আনব্যান করে।"""
    user_id = context.job.data['user_id']
    lang = await get_user_lang(user_id)
    async with await get_db_conn() as aconn:
        async with aconn.cursor() as acur:
            await acur.execute("UPDATE users SET strikes = 0, is_banned = FALSE, ban_until = NULL WHERE user_id = %s", (user_id,))
    try:
        await context.bot.send_message(user_id, LANG_TEXT[lang]['unban_message'])
    except Forbidden:
        logger.warning(f"User {user_id} blocked the bot, could not send unban message.")

async def daily_cleanup_job(context: ContextTypes.DEFAULT_TYPE):
    """প্রতিদিন ডাটাবেস থেকে غير فعال ব্যবহারকারীদের তথ্য মুছে ফেলে।"""
    logger.info("Running daily database cleanup...")
    async with await get_db_conn() as aconn:
        async with aconn.cursor() as acur:
            await acur.execute("DELETE FROM users WHERE strikes = 0 AND is_banned = FALSE;")
            logger.info(f"{acur.rowcount} inactive users cleaned up from the database.")


# -----------------------------------------------------------------------------
# |                      টেলিগ্রাম বটের সকল হ্যান্ডলার                       |
# -----------------------------------------------------------------------------

def get_main_reply_keyboard(user_id: int):
    keyboard = [[GET_NUMBER_TEXT], [MY_STATS_TEXT, SUPPORT_TEXT], [LANGUAGE_TEXT]]
    if user_id == ADMIN_USER_ID:
        keyboard.insert(0, [ADMIN_PANEL_TEXT]) # অ্যাডমিনের জন্য অতিরিক্ত বাটন
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

async def get_number_options_keyboard(lang: str):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💎 Facebook", callback_data="get_number_facebook")],
        [InlineKeyboardButton("✈️ Telegram", callback_data="get_number_telegram")],
        [InlineKeyboardButton("💬 WhatsApp", callback_data="get_number_whatsapp")],
        [InlineKeyboardButton(LANG_TEXT[lang]['back_button'], callback_data="back_to_main")]
    ])

# --- প্রধান কমান্ড এবং বাটন হ্যান্ডলার ---
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    lang = await get_user_lang(user.id)
    async with await get_db_conn() as aconn:
        async with aconn.cursor() as acur:
            await acur.execute(
                "INSERT INTO users (user_id, first_name, language) VALUES (%s, %s, %s) ON CONFLICT (user_id) DO UPDATE SET first_name = EXCLUDED.first_name",
                (user.id, user.first_name, lang)
            )
    await update.message.reply_text(
        text=LANG_TEXT[lang]['welcome'].format(first_name=user.first_name),
        reply_markup=get_main_reply_keyboard(user.id)
    )

async def handle_get_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = await get_user_lang(user_id)

    # ব্যান স্ট্যাটাস চেক
    async with await get_db_conn() as aconn:
        async with aconn.cursor(row_factory=psycopg.rows.dict_row) as acur:
            await acur.execute("SELECT is_banned, ban_until FROM users WHERE user_id = %s", (user_id,))
            user_status = await acur.fetchone()
            if user_status and user_status['is_banned']:
                unban_time = user_status['ban_until'].strftime('%Y-%m-%d %H:%M')
                await update.message.reply_text(LANG_TEXT[lang]['status_banned'].format(hours=BAN_HOURS, unban_time=unban_time))
                return

    await update.message.reply_text(text=LANG_TEXT[lang]['choose_service'], reply_markup=await get_number_options_keyboard(lang))

async def handle_my_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = await get_user_lang(user_id)
    async with await get_db_conn() as aconn:
        async with aconn.cursor(row_factory=psycopg.rows.dict_row) as acur:
            await acur.execute("SELECT strikes, is_banned, ban_until FROM users WHERE user_id = %s", (user_id,))
            stats = await acur.fetchone()
            if stats:
                message = f"{LANG_TEXT[lang]['stats_header']}\n\n{LANG_TEXT[lang]['strikes']}: {stats['strikes']}/{MAX_STRIKES}\n"
                if stats['is_banned']:
                    unban_time = stats['ban_until'].strftime('%Y-%m-%d %H:%M') if stats['ban_until'] else 'N/A'
                    message += LANG_TEXT[lang]['status_banned'].format(hours=BAN_HOURS, unban_time=unban_time)
                else:
                    message += f"{LANG_TEXT[lang]['status_normal']}"
            else:
                message = LANG_TEXT[lang]['stats_not_found']
    await update.message.reply_text(text=message)

async def handle_support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = await get_user_lang(update.effective_user.id)
    reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton(text=LANG_TEXT[lang]['support_button'], url=f"https://t.me/{SUPPORT_USERNAME.lstrip('@')}")]])
    await update.message.reply_text(text=LANG_TEXT[lang]['support_prompt'], reply_markup=reply_markup)

async def handle_language_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = await get_user_lang(update.effective_user.id)
    reply_markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("🇧🇩 বাংলা", callback_data="set_lang_bn")],
        [InlineKeyboardButton("🇬🇧 English", callback_data="set_lang_en")]
    ])
    await update.message.reply_text(text=LANG_TEXT[lang]['choose_language'], reply_markup=reply_markup)

# --- ইনলাইন বাটন ক্লিক হ্যান্ডলার (নতুন ফিচারসহ) ---

async def handle_button_press(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data
    lang = await get_user_lang(user_id)
    
    # ইনলাইন কিবোর্ড বাটন হ্যান্ডলিং
    if data.startswith("get_number_"):
        service = data.split("_")[2].capitalize()
        await query.edit_message_text(text=LANG_TEXT[lang]['searching_number'].format(service=service))

        # কুলডাউন চেক
        async with await get_db_conn() as aconn:
            async with aconn.cursor(row_factory=psycopg.rows.dict_row) as acur:
                await acur.execute("SELECT last_number_success_at FROM users WHERE user_id = %s", (user_id,))
                user = await acur.fetchone()
                if user and user['last_number_success_at']:
                    if datetime.datetime.now() < user['last_number_success_at'] + datetime.timedelta(minutes=COOLDOWN_MINUTES):
                        await query.edit_message_text(LANG_TEXT[lang]['cooldown_message'].format(minutes=COOLDOWN_MINUTES))
                        return
        
        number_data = await find_available_number(service)
        if number_data:
            number_id = number_data['id']
            async with await get_db_conn() as aconn:
                async with aconn.cursor() as acur:
                    await acur.execute(
                        "UPDATE numbers SET is_available = FALSE, assigned_to = %s, assigned_at = NOW() WHERE id = %s",
                        (user_id, number_id)
                    )
            
            otp_keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton(LANG_TEXT[lang]['otp_received_button'], callback_data=f"otp_ok_{number_id}")],
                [InlineKeyboardButton(LANG_TEXT[lang]['otp_failed_button'], callback_data=f"otp_fail_{number_id}")]
            ])
            await query.edit_message_text(
                text=LANG_TEXT[lang]['number_found'].format(phone_number=number_data['phone_number']),
                reply_markup=otp_keyboard,
                parse_mode='Markdown'
            )
            # ইনঅ্যাক্টিভিটি স্ট্রাইক জব সেট করা
            context.job_queue.run_once(inactivity_strike_job, INACTIVITY_MINUTES * 60, data={'user_id': user_id, 'number_id': number_id}, name=f"strike_{user_id}_{number_id}")
        else:
            await query.edit_message_text(text=LANG_TEXT[lang]['no_number_available'].format(service=service))

    elif data.startswith("otp_ok_"):
        number_id = int(data.split("_")[2])
        # স্ট্রাইক জব রিমুভ করা
        jobs = context.job_queue.get_jobs_by_name(f"strike_{user_id}_{number_id}")
        for job in jobs:
            job.schedule_removal()

        async with await get_db_conn() as aconn:
            async with aconn.cursor() as acur:
                # কুলডাউন সেট করা
                await acur.execute("UPDATE users SET last_number_success_at = NOW() WHERE user_id = %s", (user_id,))
                # নম্বরকে ব্যবহৃত হিসেবে রাখা (কিন্তু available নয়)
                await acur.execute("UPDATE numbers SET assigned_to = NULL WHERE id = %s", (number_id,)) # কিন্তু is_available=FALSE থাকবে
        await query.edit_message_text(LANG_TEXT[lang]['thank_you_for_otp'].format(minutes=COOLDOWN_MINUTES))

    elif data.startswith("otp_fail_"):
        number_id = int(data.split("_")[2])
        # স্ট্রাইক জব রিমুভ করা
        jobs = context.job_queue.get_jobs_by_name(f"strike_{user_id}_{number_id}")
        for job in jobs:
            job.schedule_removal()

        async with await get_db_conn() as aconn:
            async with aconn.cursor() as acur:
                await acur.execute("UPDATE numbers SET is_reported = TRUE, is_available = FALSE, assigned_to = NULL WHERE id = %s", (number_id,))

        await query.edit_message_text(LANG_TEXT[lang]['report_success'])
        # ব্যবহারকারীকে আবার সার্ভিস সিলেকশন মেনু দেখানো
        await query.message.reply_text(text=LANG_TEXT[lang]['choose_service'], reply_markup=await get_number_options_keyboard(lang))

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

# -----------------------------------------------------------------------------
# |                      👑 অ্যাডমিন প্যানেল হ্যান্ডলার 👑                      |
# -----------------------------------------------------------------------------
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_USER_ID: return
    lang = await get_user_lang(ADMIN_USER_ID)
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Add Number", callback_data="admin_add"), InlineKeyboardButton("🗑️ Delete Number", callback_data="admin_del")],
        [InlineKeyboardButton("🔄 Reactivate Number", callback_data="admin_reactivate")],
        [InlineKeyboardButton("📄 View Reported", callback_data="admin_view_reported"), InlineKeyboardButton("⌛ View Expired", callback_data="admin_view_expired")],
        [InlineKeyboardButton("📢 Broadcast Msg", callback_data="admin_broadcast"), InlineKeyboardButton("🗑️ Delete Broadcast", callback_data="admin_del_broadcast")],
        [InlineKeyboardButton("🚫 Ban User", callback_data="admin_ban"), InlineKeyboardButton("✅ Unban User", callback_data="admin_unban")],
        [InlineKeyboardButton(LANG_TEXT[lang]['back_button'], callback_data="back_to_main")]
    ])
    await update.message.reply_text(LANG_TEXT[lang]['admin_panel_prompt'], reply_markup=keyboard)

async def handle_admin_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    if user_id != ADMIN_USER_ID: return
    
    data = query.data
    lang = await get_user_lang(user_id)
    
    prompts = {
        "admin_add": LANG_TEXT[lang]['add_number_prompt'],
        "admin_del": LANG_TEXT[lang]['delnum_prompt'],
        "admin_reactivate": LANG_TEXT[lang]['reactivate_prompt'],
        "admin_broadcast": "➡️ Send your broadcast message now.",
        "admin_del_broadcast": "Are you sure you want to delete the last custom broadcast?",
        "admin_ban": LANG_TEXT[lang]['ban_user_prompt'],
        "admin_unban": LANG_TEXT[lang]['unban_user_prompt'],
    }
    
    if data in prompts:
        await query.edit_message_text(prompts[data])
    
    elif data == "admin_view_reported":
        async with await get_db_conn() as aconn:
            async with aconn.cursor(row_factory=psycopg.rows.dict_row) as acur:
                await acur.execute("SELECT phone_number, service FROM numbers WHERE is_reported = TRUE")
                numbers = await acur.fetchall()
        if numbers:
            message = LANG_TEXT[lang]['view_reported_header'] + "\n\n"
            message += "\n".join([f"`{n['phone_number']}` ({n['service']})" for n in numbers])
        else:
            message = LANG_TEXT[lang]['no_reported_numbers']
        await query.edit_message_text(message, parse_mode='Markdown')

    elif data == "admin_view_expired":
         async with await get_db_conn() as aconn:
            async with aconn.cursor(row_factory=psycopg.rows.dict_row) as acur:
                # যে নম্বরগুলো ৫ মিনিটের বেশি সময় ধরে assigned কিন্তু কোনো OTP ফিডব্যাক আসেনি
                await acur.execute("SELECT phone_number, service FROM numbers WHERE assigned_to IS NOT NULL AND assigned_at < NOW() - INTERVAL '5 minutes'")
                numbers = await acur.fetchall()
         if numbers:
             message = LANG_TEXT[lang]['view_expired_header'] + "\n\n"
             message += "\n".join([f"`{n['phone_number']}` ({n['service']})" for n in numbers])
         else:
             message = LANG_TEXT[lang]['no_expired_numbers']
         await query.edit_message_text(message, parse_mode='Markdown')


# --- অ্যাডমিন কমান্ড হ্যান্ডলার ---

async def add_number_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_USER_ID: return
    lang = await get_user_lang(ADMIN_USER_ID)
    
    args = context.args
    if len(args) < 2:
        await update.message.reply_text(LANG_TEXT[lang]['add_number_prompt'])
        return
        
    service = args[0].capitalize()
    numbers_to_add = args[1:]
    added_count = 0
    
    async with await get_db_conn() as aconn:
        async with aconn.cursor() as acur:
            for number in numbers_to_add:
                try:
                    await acur.execute(
                        "INSERT INTO numbers (phone_number, service, is_available) VALUES (%s, %s, TRUE)",
                        (number, service)
                    )
                    added_count += 1
                except psycopg.errors.UniqueViolation:
                    logger.warning(f"Number {number} already exists. Skipping.")
    
    if added_count > 0:
        await update.message.reply_text(LANG_TEXT[lang]['number_added_success'].format(count=added_count, service=service))
        # স্বয়ংক্রিয় ঘোষণা পাঠানো
        await auto_broadcast_new_numbers(context, service, lang)
    else:
        await update.message.reply_text("No new numbers were added.")

async def auto_broadcast_new_numbers(context: ContextTypes.DEFAULT_TYPE, service: str, lang: str):
    """নতুন নম্বর যোগ করার পর সকল ব্যবহারকারীকে ঘোষণা পাঠায় এবং পুরানোটা ডিলিট করে।"""
    bot = context.bot
    # ধাপ ১: পুরানো ঘোষণা ডিলিট করা
    async with await get_db_conn() as aconn:
        async with aconn.cursor(row_factory=psycopg.rows.dict_row) as acur:
            await acur.execute("SELECT user_id, message_id FROM broadcast_messages WHERE broadcast_type = 'auto_new_number'")
            old_messages = await acur.fetchall()
            for msg in old_messages:
                try:
                    await bot.delete_message(chat_id=msg['user_id'], message_id=msg['message_id'])
                except (Forbidden, BadRequest):
                    pass # ব্যবহারকারী বট ব্লক করলে বা মেসেজ না থাকলে সমস্যা নেই
            await acur.execute("DELETE FROM broadcast_messages WHERE broadcast_type = 'auto_new_number'")
    await bot.send_message(ADMIN_USER_ID, LANG_TEXT[lang]['broadcast_deleted'])

    # ধাপ ২: নতুন ঘোষণা পাঠানো
    async with await get_db_conn() as aconn:
        async with aconn.cursor(row_factory=psycopg.rows.dict_row) as acur:
            await acur.execute("SELECT user_id, language FROM users WHERE is_banned = FALSE")
            all_users = await acur.fetchall()

    new_message_ids = []
    for user in all_users:
        user_lang = user['language']
        text = LANG_TEXT[user_lang]['new_number_broadcast'].format(service=service, get_number_button=GET_NUMBER_TEXT)
        try:
            sent_message = await bot.send_message(chat_id=user['user_id'], text=text)
            new_message_ids.append((user['user_id'], sent_message.message_id, 'auto_new_number'))
        except Forbidden:
            logger.warning(f"User {user['user_id']} has blocked the bot. Skipping broadcast.")

    # ধাপ ৩: নতুন মেসেজ আইডি সেভ করা
    async with await get_db_conn() as aconn:
        async with aconn.cursor() as acur:
            await acur.executemany("INSERT INTO broadcast_messages (user_id, message_id, broadcast_type) VALUES (%s, %s, %s)", new_message_ids)

async def del_number_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_USER_ID: return
    lang = await get_user_lang(ADMIN_USER_ID)
    if not context.args:
        await update.message.reply_text(LANG_TEXT[lang]['delnum_prompt'])
        return
    
    number_to_del = context.args[0]
    async with await get_db_conn() as aconn:
        async with aconn.cursor() as acur:
            await acur.execute("DELETE FROM numbers WHERE phone_number = %s", (number_to_del,))
            if acur.rowcount > 0:
                await update.message.reply_text(LANG_TEXT[lang]['delnum_success'].format(number=number_to_del))
            else:
                await update.message.reply_text(LANG_TEXT[lang]['delnum_not_found'].format(number=number_to_del))

async def reactivate_number_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_USER_ID: return
    lang = await get_user_lang(ADMIN_USER_ID)
    if not context.args:
        await update.message.reply_text(LANG_TEXT[lang]['reactivate_prompt'])
        return

    number_to_reactivate = context.args[0]
    async with await get_db_conn() as aconn:
        async with aconn.cursor() as acur:
            await acur.execute(
                "UPDATE numbers SET is_available = TRUE, is_reported = FALSE, assigned_to = NULL, assigned_at = NULL WHERE phone_number = %s",
                (number_to_reactivate,)
            )
            if acur.rowcount > 0:
                await update.message.reply_text(LANG_TEXT[lang]['reactivate_success'].format(number=number_to_reactivate))
            else:
                await update.message.reply_text(LANG_TEXT[lang]['delnum_not_found'].format(number=number_to_reactivate))


async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_USER_ID: return
    lang = await get_user_lang(ADMIN_USER_ID)
    if not context.args:
        await update.message.reply_text(LANG_TEXT[lang]['broadcast_no_message'])
        return

    message_to_send = ' '.join(context.args)
    
    # আগের ম্যানুয়াল ব্রডকাস্ট মেসেজ আইডি মুছে ফেলা
    async with await get_db_conn() as aconn:
        async with aconn.cursor() as acur:
            await acur.execute("DELETE FROM broadcast_messages WHERE broadcast_type = 'manual'")
    
    async with await get_db_conn() as aconn:
        async with aconn.cursor(row_factory=psycopg.rows.dict_row) as acur:
            await acur.execute("SELECT user_id, language FROM users")
            all_users = await acur.fetchall()

    sent_count = 0
    new_message_ids = []
    for user in all_users:
        header = LANG_TEXT[user['language']]['admin_announcement']
        formatted_message = f"**{header}**\n\n{message_to_send}"
        try:
            sent_message = await context.bot.send_message(chat_id=user['user_id'], text=formatted_message, parse_mode='Markdown')
            new_message_ids.append((user['user_id'], sent_message.message_id, 'manual'))
            sent_count += 1
            await asyncio.sleep(0.1)
        except Forbidden:
            logger.warning(f"User {user['user_id']} has blocked the bot. Skipping.")
        except Exception as e:
            logger.error(f"Failed to send message to {user['user_id']}: {e}")
    
    # নতুন মেসেজ আইডি সেভ করা
    async with await get_db_conn() as aconn:
        async with aconn.cursor() as acur:
            await acur.executemany("INSERT INTO broadcast_messages (user_id, message_id, broadcast_type) VALUES (%s, %s, %s)", new_message_ids)

    await update.message.reply_text(LANG_TEXT[lang]['broadcast_sent'].format(count=sent_count))

async def del_broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_USER_ID: return
    lang = await get_user_lang(ADMIN_USER_ID)
    
    async with await get_db_conn() as aconn:
        async with aconn.cursor(row_factory=psycopg.rows.dict_row) as acur:
            await acur.execute("SELECT user_id, message_id FROM broadcast_messages WHERE broadcast_type = 'manual'")
            messages_to_delete = await acur.fetchall()

            for msg in messages_to_delete:
                try:
                    await context.bot.delete_message(chat_id=msg['user_id'], message_id=msg['message_id'])
                except (Forbidden, BadRequest):
                    pass
            
            await acur.execute("DELETE FROM broadcast_messages WHERE broadcast_type = 'manual'")
    
    await update.message.reply_text(LANG_TEXT[lang]['delbroadcast_success'])

async def ban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_USER_ID: return
    lang = await get_user_lang(ADMIN_USER_ID)
    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text(LANG_TEXT[lang]['ban_user_prompt'])
        return

    user_id_to_ban = int(context.args[0])
    ban_until = datetime.datetime.now() + datetime.timedelta(days=999) # ম্যানুয়াল ব্যান
    async with await get_db_conn() as aconn:
        async with aconn.cursor() as acur:
            await acur.execute("UPDATE users SET is_banned = TRUE, ban_until = %s WHERE user_id = %s", (ban_until, user_id_to_ban))
            if acur.rowcount > 0:
                await update.message.reply_text(LANG_TEXT[lang]['ban_success'].format(user_id=user_id_to_ban))
            else:
                await update.message.reply_text(LANG_TEXT[lang]['user_not_found'].format(user_id=user_id_to_ban))

async def unban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_USER_ID: return
    lang = await get_user_lang(ADMIN_USER_ID)
    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text(LANG_TEXT[lang]['unban_user_prompt'])
        return
        
    user_id_to_unban = int(context.args[0])
    async with await get_db_conn() as aconn:
        async with aconn.cursor() as acur:
            await acur.execute("UPDATE users SET is_banned = FALSE, ban_until = NULL, strikes = 0 WHERE user_id = %s", (user_id_to_unban,))
            if acur.rowcount > 0:
                await update.message.reply_text(LANG_TEXT[lang]['unban_success'].format(user_id=user_id_to_unban))
            else:
                await update.message.reply_text(LANG_TEXT[lang]['user_not_found'].format(user_id=user_id_to_unban))

# -----------------------------------------------------------------------------
# |                         ফাইনাল অ্যাপ্লিকেশন চালু করা                        |
# -----------------------------------------------------------------------------
def main() -> None:
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    logger.info("Keep-alive server started.")

    bot_app = Application.builder().token(BOT_TOKEN).post_init(setup_database).build()
    
    # জব কিউ সেটআপ
    job_queue = bot_app.job_queue
    job_queue.run_daily(daily_cleanup_job, time=datetime.time(hour=21, minute=0, tzinfo=datetime.timezone.utc)) # রাত ৩টা (UTC+6)

    # --- অ্যাডমিন কমান্ড হ্যান্ডলার ---
    bot_app.add_handler(CommandHandler("add", add_number_command))
    bot_app.add_handler(CommandHandler("delnumber", del_number_command))
    bot_app.add_handler(CommandHandler("reactivate", reactivate_number_command))
    bot_app.add_handler(CommandHandler("broadcast", broadcast_command))
    bot_app.add_handler(CommandHandler("delbroadcast", del_broadcast_command))
    bot_app.add_handler(CommandHandler("ban", ban_command))
    bot_app.add_handler(CommandHandler("unban", unban_command))
    
    # --- ব্যবহারকারী কমান্ড হ্যান্ডলার ---
    bot_app.add_handler(CommandHandler("start", start_command))
    
    # --- ReplyKeyboard বাটনগুলোর জন্য MessageHandler ---
    bot_app.add_handler(MessageHandler(filters.TEXT & filters.Regex(f'^{GET_NUMBER_TEXT}$'), handle_get_number))
    bot_app.add_handler(MessageHandler(filters.TEXT & filters.Regex(f'^{MY_STATS_TEXT}$'), handle_my_stats))
    bot_app.add_handler(MessageHandler(filters.TEXT & filters.Regex(f'^{SUPPORT_TEXT}$'), handle_support))
    bot_app.add_handler(MessageHandler(filters.TEXT & filters.Regex(f'^{LANGUAGE_TEXT}$'), handle_language_button))
    bot_app.add_handler(MessageHandler(filters.TEXT & filters.Regex(f'^{ADMIN_PANEL_TEXT}$'), admin_panel))

    # --- ইনলাইন বাটনের জন্য CallbackQueryHandler ---
    bot_app.add_handler(CallbackQueryHandler(handle_button_press, pattern="^(get_number_|otp_ok_|otp_fail_|set_lang_|back_to_main)"))
    bot_app.add_handler(CallbackQueryHandler(handle_admin_callbacks, pattern="^admin_"))

    logger.info("Telegram Bot starting polling...")
    bot_app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
