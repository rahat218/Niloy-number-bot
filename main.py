#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
A sophisticated Telegram bot that provides temporary phone numbers for OTP verification.
Built for deployment on free hosting services like Render.com using the Flask trick.
"""

import logging
import datetime
import psycopg
import os
from enum import Enum
from threading import Thread
from flask import Flask
from psycopg.rows import dict_row
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)
from telegram.error import TelegramError

# -----------------------------------------------------------------------------
# |                      ⚙️ বটের সকল কনফিগারেশন এখানে ⚙️                       |
# -----------------------------------------------------------------------------
class Config:
    """
    বটের সকল সেটিংস এবং গোপন তথ্য একটি ক্লাসের মধ্যে রাখা হয়েছে।
    """
    # -------------------------------------------------------------------------
    # |      ⚠️ অত্যন্ত জরুরি সতর্কবার্তা: আপনার সকল গোপন তথ্য এখানে ⚠️      |
    # |   এই তথ্যগুলো সরাসরি কোডে লেখা একটি মারাত্মক নিরাপত্তা ঝুঁকি।          |
    # |   সুযোগ পেলে এগুলোকে Environment Variables হিসেবে ব্যবহার করুন।        |
    # -------------------------------------------------------------------------
    BOT_TOKEN = "7925556669:AAE5F9zUGOK37niSd0x-YEQX8rn-xGd8Pl8"
    DATABASE_URL = "postgresql://niloy_number_bot_user:p2pmOrN2Kx7WjiC611qPGk1cVBqEbfeq@dpg-d20ii8nfte5s738v6elg-a/niloy_number_bot"
    ADMIN_CHANNEL_ID = -4611753759
    ADMIN_USER_ID = 7052442701
    SUPPORT_USERNAME = "t.me/Ngrony" # @ চিহ্ন ছাড়া

    # --- বটের কার্যকরী সেটিংস ---
    LEASE_TIME_MINUTES = 10
    COOLDOWN_MINUTES = 2
    MAX_STRIKES = 3
    BAN_HOURS = 24
    
    # --- ছবির লিঙ্ক ---
    MAIN_PHOTO_URL = "https://telegra.ph/file/02194911f26a7962c454e.jpg"


# -----------------------------------------------------------------------------
# |                      📝 কলব্যাক ডেটার জন্য Enum                          |
# -----------------------------------------------------------------------------
class CallbackPrefix(str, Enum):
    """কলব্যাক ডেটার জন্য প্রিফিক্স, যাতে কোডে কোনো ম্যাজিক স্ট্রিং না থাকে।"""
    GET_NUMBER = "get_number_"
    RELEASE_SUCCESS = "release_success_"
    RELEASE_FAIL = "release_fail_"
    MY_STATS = "my_stats"
    ADMIN_PANEL = "admin_panel"


# -----------------------------------------------------------------------------
# |                      🌐 Render.com-এর জন্য ওয়েব সার্ভার 🌐                    |
# -----------------------------------------------------------------------------
flask_app = Flask(__name__)

@flask_app.route('/')
def health_check() -> str:
    """Render.com এই URL ভিজিট করে বুঝবে যে অ্যাপটি সচল আছে।"""
    return "Bot is alive and running!"

def run_flask() -> None:
    """Render.com দ্বারা প্রদত্ত পোর্টে ফ্লাস্ক সার্ভারটি চালায়।"""
    port = int(os.environ.get('PORT', 8080))
    flask_app.run(host='0.0.0.0', port=port)


# -----------------------------------------------------------------------------
# |                      📜 লগিং এবং ডাটাবেস সেটআপ 📜                        |
# -----------------------------------------------------------------------------
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

async def get_db_conn() -> psycopg.AsyncConnection:
    """ডাটাবেসের সাথে সংযোগ স্থাপন করে এবং ডিকশনারি কার্সর রিটার্ন করে।"""
    return await psycopg.AsyncConnection.connect(Config.DATABASE_URL, row_factory=dict_row)

async def setup_database(app: Application) -> None:
    """বট চালু হওয়ার সময় স্বয়ংক্রিয়ভাবে ডাটাবেস ও টেবিল তৈরি করবে।"""
    logger.info("Connecting to database...")
    try:
        async with (await get_db_conn()) as aconn:
            async with aconn.cursor() as acur:
                await acur.execute("""
                    CREATE TABLE IF NOT EXISTS users (
                        user_id BIGINT PRIMARY KEY,
                        first_name VARCHAR(255),
                        strikes INT DEFAULT 0,
                        is_banned BOOLEAN DEFAULT FALSE,
                        ban_until TIMESTAMP,
                        last_number_request_time TIMESTAMP
                    );
                """)
                await acur.execute("""
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
        logger.info("✅ SUCCESS: Database setup complete.")
    except Exception as e:
        logger.critical(f"❌ CRITICAL: Database connection failed! Bot cannot start. Error: {e}")
        # এখানে আপনি চাইলে অ্যাডমিনকে একটি জরুরি নোটিফিকেশন পাঠাতে পারেন
        os._exit(1) # ডাটাবেস ছাড়া বট চলতে পারবে না, তাই বন্ধ করে দেওয়া হচ্ছে

# -----------------------------------------------------------------------------
# |                          ⌨️ কীবোর্ড তৈরি ⌨️                            |
# -----------------------------------------------------------------------------
async def get_main_menu_keyboard(user_id: int) -> InlineKeyboardMarkup:
    """ব্যবহারকারীর জন্য প্রধান মেন্যুর ইনলাইন কীবোর্ড তৈরি করে।"""
    keyboard = [
        [InlineKeyboardButton("💎 Get Facebook Number", callback_data=f"{CallbackPrefix.GET_NUMBER}facebook")],
        [InlineKeyboardButton("✈️ Get Telegram Number", callback_data=f"{CallbackPrefix.GET_NUMBER}telegram")],
        [InlineKeyboardButton("💬 Get WhatsApp Number", callback_data=f"{CallbackPrefix.GET_NUMBER}whatsapp")],
        [
            InlineKeyboardButton("📞 Support", url=f"https://t.me/{Config.SUPPORT_USERNAME}"),
            InlineKeyboardButton("📊 My Stats", callback_data=CallbackPrefix.MY_STATS)
        ]
    ]
    if user_id == Config.ADMIN_USER_ID:
        keyboard.append([InlineKeyboardButton("👑 Admin Panel 👑", callback_data=CallbackPrefix.ADMIN_PANEL)])
    return InlineKeyboardMarkup(keyboard)

# -----------------------------------------------------------------------------
# |                           🤖 বটের মূল লজিক 🤖                            |
# -----------------------------------------------------------------------------

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/start কমান্ড হ্যান্ডেল করে এবং ব্যবহারকারীকে ডাটাবেসে যোগ করে।"""
    user = update.effective_user
    logger.info(f"New user started: {user.first_name} (ID: {user.id})")
    
    try:
        async with (await get_db_conn()) as aconn:
            async with aconn.cursor() as acur:
                await acur.execute(
                    "INSERT INTO users (user_id, first_name) VALUES (%s, %s) ON CONFLICT (user_id) DO NOTHING",
                    (user.id, user.first_name)
                )
    except Exception as e:
        logger.error(f"DB error on start for user {user.id}: {e}")
    
    reply_markup = await get_main_menu_keyboard(user.id)
    await update.message.reply_photo(
        photo=Config.MAIN_PHOTO_URL,
        caption=f"👋 **Welcome, {user.first_name}!**\n\nChoose a service below to get a temporary number.",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def handle_get_number(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """'Get Number' বাটনে ক্লিক করলে এই ফাংশন কাজ করে।"""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    
    try:
        async with (await get_db_conn()) as aconn:
            async with aconn.cursor() as acur:
                # ১. ব্যবহারকারীর তথ্য সংগ্রহ করা
                await acur.execute("SELECT * FROM users WHERE user_id = %s", (user_id,))
                user_data = await acur.fetchone()
                if not user_data:
                    await acur.execute("INSERT INTO users (user_id, first_name) VALUES (%s, %s)", (user_id, query.from_user.first_name))
                    await acur.execute("SELECT * FROM users WHERE user_id = %s", (user_id,))
                    user_data = await acur.fetchone()

                # ২. ব্যবহারকারী ব্যানড কিনা তা পরীক্ষা করা
                if user_data['is_banned'] and user_data['ban_until'] and datetime.datetime.now(datetime.timezone.utc) < user_data['ban_until']:
                    remaining_time = user_data['ban_until'] - datetime.datetime.now(datetime.timezone.utc)
                    await query.edit_message_caption(caption=f"❌ **You are Banned!**\n\nBan will be lifted in: `{str(remaining_time).split('.')[0]}`", parse_mode='Markdown')
                    return

                # ৩. কুলডাউন পিরিয়ড পরীক্ষা করা
                if user_data['last_number_request_time']:
                    cooldown_end = user_data['last_number_request_time'] + datetime.timedelta(minutes=Config.COOLDOWN_MINUTES)
                    if datetime.datetime.now(datetime.timezone.utc) < cooldown_end:
                        await query.answer(f"⏳ Please wait {Config.COOLDOWN_MINUTES} minutes before next request!", show_alert=True)
                        return
                
                # ৪. একটি সহজলভ্য নম্বর খোঁজা
                service = query.data.replace(CallbackPrefix.GET_NUMBER, "")
                await acur.execute(
                    "SELECT * FROM numbers WHERE service = %s AND is_available = TRUE AND is_reported = FALSE ORDER BY RANDOM() LIMIT 1 FOR UPDATE",
                    (service,)
                )
                number_record = await acur.fetchone()
                
                if number_record:
                    # ৫. নম্বর পাওয়া গেলে ডাটাবেস আপডেট করা
                    number_id = number_record['id']
                    phone_number = number_record['phone_number']
                    now_utc = datetime.datetime.now(datetime.timezone.utc)
                    
                    await acur.execute("UPDATE numbers SET is_available = FALSE, assigned_to = %s, assigned_at = %s WHERE id = %s", (user_id, now_utc, number_id))
                    await acur.execute("UPDATE users SET last_number_request_time = %s WHERE user_id = %s", (now_utc, user_id))

                    # ৬. ব্যবহারকারীকে নম্বর এবং নতুন বাটন পাঠানো
                    keyboard = [
                        [InlineKeyboardButton("✅ OTP Received, Release Now", callback_data=f"{CallbackPrefix.RELEASE_SUCCESS}{number_id}")],
                        [InlineKeyboardButton("❌ Report & Get New One", callback_data=f"{CallbackPrefix.RELEASE_FAIL}{number_id}")]
                    ]
                    reply_markup = InlineKeyboardMarkup(keyboard)
                    await query.edit_message_caption(
                        caption=f"**Your {service.capitalize()} Number:**\n\n`{phone_number}`\n\n_This number is yours for **{Config.LEASE_TIME_MINUTES} minutes**._",
                        reply_markup=reply_markup,
                        parse_mode='Markdown'
                    )
                    
                    # ৭. স্বয়ংক্রিয় রিলিজের জন্য জব শিডিউল করা
                    job_name = f"release_{user_id}_{number_id}"
                    context.job_queue.run_once(auto_release_callback, Config.LEASE_TIME_MINUTES * 60, data={'user_id': user_id, 'number_id': number_id}, name=job_name)
                    logger.info(f"Number {phone_number} assigned to user {user_id}. Job '{job_name}' scheduled.")
                else:
                    await query.answer(f"Sorry, no numbers available for {service.capitalize()} right now. Please try again later.", show_alert=True)
    
    except (psycopg.Error, TelegramError) as e:
        logger.error(f"Error in handle_get_number for user {user_id}: {e}")
        await query.answer("An unexpected error occurred. Please try again.", show_alert=True)

async def handle_release_number(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """নম্বর রিলিজ বা রিপোর্ট করার বাটন চাপলে কাজ করবে।"""
    query = update.callback_query
    user_id = query.from_user.id
    
    try:
        if query.data.startswith(CallbackPrefix.RELEASE_SUCCESS):
            action = "success"
            number_id = int(query.data.replace(CallbackPrefix.RELEASE_SUCCESS, ""))
        else:
            action = "fail"
            number_id = int(query.data.replace(CallbackPrefix.RELEASE_FAIL, ""))

        await query.answer()

        async with (await get_db_conn()) as aconn:
            async with aconn.cursor() as acur:
                if action == "success":
                    await acur.execute("UPDATE numbers SET is_available = TRUE, assigned_to = NULL, assigned_at = NULL WHERE id = %s", (number_id,))
                    await acur.execute("UPDATE users SET strikes = 0 WHERE user_id = %s", (user_id,))
                    caption = "✅ **Number Released!**\n\nYour strikes have been cleared. You can get another number now."
                
                elif action == "fail":
                    await acur.execute("UPDATE numbers SET is_available = TRUE, assigned_to = NULL, is_reported = TRUE WHERE id = %s", (number_id,))
                    await acur.execute("SELECT phone_number, service FROM numbers WHERE id = %s", (number_id,))
                    number_info = await acur.fetchone()
                    report_message = f"🚨 **Number Reported!**\nUser: `{user_id}`\nNumber: `{number_info['phone_number']}` ({number_info['service']})"
                    await context.bot.send_message(Config.ADMIN_CHANNEL_ID, report_message, parse_mode='Markdown')
                    caption = "📝 **Number Reported!**\n\nThe admin has been notified. You can now request a new number."

                await query.edit_message_caption(caption=caption, reply_markup=await get_main_menu_keyboard(user_id), parse_mode='Markdown')

        # রিলিজ হয়ে গেলে স্বয়ংক্রিয় জবটি বাতিল করা
        job_name = f"release_{user_id}_{number_id}"
        current_jobs = context.job_queue.get_jobs_by_name(job_name)
        for job in current_jobs:
            job.schedule_removal()
            logger.info(f"Scheduled job '{job.name}' removed successfully by user.")

    except (psycopg.Error, TelegramError, IndexError) as e:
        logger.error(f"Error in handle_release_number for user {user_id}: {e}")
        await query.answer("Could not process your request. Please try again.", show_alert=True)


async def auto_release_callback(context: ContextTypes.DEFAULT_TYPE) -> None:
    """নির্দিষ্ট সময় পর স্বয়ংক্রিয়ভাবে নম্বর রিলিজ ও স্ট্রাইক দেওয়ার ফাংশন।"""
    job_data = context.job.data
    user_id, number_id = job_data['user_id'], job_data['number_id']

    logger.warning(f"Lease expired for user {user_id} and number {number_id}. Applying strike.")
    try:
        async with (await get_db_conn()) as aconn:
            async with aconn.cursor() as acur:
                # নিশ্চিত করা যে নম্বরটি এখনও এই ব্যবহারকারীর কাছেই আছে কিনা
                await acur.execute("SELECT assigned_to FROM numbers WHERE id = %s", (number_id,))
                record = await acur.fetchone()
                if not record or record['assigned_to'] != user_id:
                    logger.info(f"Auto-release for number {number_id} cancelled. Already released by user {user_id}.")
                    return

                await acur.execute("UPDATE numbers SET is_available = TRUE, assigned_to = NULL, assigned_at = NULL WHERE id = %s", (number_id,))
                await acur.execute("UPDATE users SET strikes = strikes + 1 WHERE user_id = %s RETURNING strikes", (user_id,))
                result = await acur.fetchone()
                new_strikes = result['strikes'] if result else 0

                admin_message = f"⏰ **Lease Expired & Strike!**\nUser: `{user_id}`\nStrikes: **{new_strikes}/{Config.MAX_STRIKES}**."
                await context.bot.send_message(Config.ADMIN_CHANNEL_ID, admin_message, parse_mode='Markdown')

                if new_strikes >= Config.MAX_STRIKES:
                    ban_until = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=Config.BAN_HOURS)
                    await acur.execute("UPDATE users SET is_banned = TRUE, ban_until = %s, strikes = 0 WHERE user_id = %s", (ban_until, user_id))
                    await context.bot.send_message(user_id, f"❌ **You are BANNED for {Config.BAN_HOURS} hours for not releasing numbers on time!**")
                else:
                    await context.bot.send_message(user_id, f"⚠️ **Number Expired!**\nYou received 1 strike for not releasing the number. Total: `{new_strikes}/{Config.MAX_STRIKES}`.")
    except (psycopg.Error, TelegramError) as e:
        logger.error(f"Error in auto_release_callback for user {user_id}: {e}")

async def my_stats_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """ব্যবহারকারীর বর্তমান পরিসংখ্যান দেখায়।"""
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()

    try:
        async with (await get_db_conn()) as aconn:
            async with aconn.cursor() as acur:
                await acur.execute("SELECT strikes, is_banned, ban_until FROM users WHERE user_id = %s", (user_id,))
                user_data = await acur.fetchone()
                if user_data:
                    if user_data['is_banned']:
                        message = f"📊 **Your Stats**\n\nStatus: **Banned** 🟥\nReason: Reached maximum strikes.\nBan Lifts: `{user_data['ban_until']}`"
                    else:
                        message = f"📊 **Your Stats**\n\nCurrent Strikes: **{user_data['strikes']}/{Config.MAX_STRIKES}** 🟩\n\n_Remember to release numbers after use to avoid strikes!_"
                else:
                    message = "Could not find your stats. Press /start to register."
        
        await query.edit_message_caption(caption=message, reply_markup=await get_main_menu_keyboard(user_id), parse_mode='Markdown')

    except (psycopg.Error, TelegramError) as e:
        logger.error(f"Error in my_stats_callback for user {user_id}: {e}")
        await query.answer("Could not fetch your stats. Please try again.", show_alert=True)

async def admin_panel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """অ্যাডমিন প্যানেলের জন্য একটি প্লেসহোল্ডার।"""
    query = update.callback_query
    await query.answer("Welcome, Admin!", show_alert=True)
    # এখানে আপনি অ্যাডমিনের জন্য বিশেষ ফাংশন যোগ করতে পারেন

# -----------------------------------------------------------------------------
# |                           🚀 অ্যাপ্লিকেশন চালু করা 🚀                         |
# -----------------------------------------------------------------------------
def run_bot() -> None:
    """মূল বট অ্যাপ্লিকেশনটি সেটআপ এবং পোলিং মোডে চালু করে।"""
    app = Application.builder().token(Config.BOT_TOKEN).post_start(setup_database).build()
    
    # হ্যান্ডলার যোগ করা
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CallbackQueryHandler(handle_get_number, pattern=f"^{CallbackPrefix.GET_NUMBER}"))
    app.add_handler(CallbackQueryHandler(handle_release_number, pattern=f"^(?:{CallbackPrefix.RELEASE_SUCCESS}|{CallbackPrefix.RELEASE_FAIL})"))
    app.add_handler(CallbackQueryHandler(my_stats_callback, pattern=f"^{CallbackPrefix.MY_STATS}$"))
    app.add_handler(CallbackQueryHandler(admin_panel_callback, pattern=f"^{CallbackPrefix.ADMIN_PANEL}$"))
    
    logger.info("🤖 TELEGRAM BOT IS STARTING WITH POLLING...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    logger.info("🚀 Starting application...")
    
    # প্রথমে ফ্লাস্ক সার্ভারটিকে একটি আলাদা থ্রেডে চালু করা হচ্ছে
    logger.info("🌐 Starting Flask server in a background thread for health checks...")
    flask_thread = Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()

    # এখন মূল বটটি চালু করা হচ্ছে
    run_bot()
