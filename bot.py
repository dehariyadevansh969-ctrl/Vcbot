import telebot
import requests
import json
import time
import sqlite3
import os
import threading
from flask import Flask, jsonify
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from datetime import datetime

# ==================== CONFIGURATION ====================
BOT_TOKEN = os.environ.get('BOT_TOKEN', "8756118508:AAGA06F7DfF9A0T_bYQ1ymoGfNRe_UfGgNY")

# ===== APNI API CONFIG =====
API_BASE_URL = "https://apple-apixdev.onrender.com/api"
API_KEY = "DevKing77"

# GROUP & CHANNEL
GROUP_LINK = "https://t.me/+3I9rJfeh5XVkZDM1"
GROUP_ID = -1003758601788
CHANNEL_LINK = "https://t.me/+1Jqq3-0RKpEyNTM1"
CHANNEL_ID = -1003791928633

# IMAGE & VIDEO
START_IMAGE = "https://i.ibb.co/LjY2dHQ/Picsart-26-02-23-10-49-39-278.jpg"
WELCOME_VIDEO = "https://drive.google.com/uc?export=download&id=1FBbOYsTzDF5gN170A-pDAn3jGb2IcVNi"

# BRAND
BRAND = "꧁💠⃟‌⃟ 𝕯єν꧂"
CREATOR = "Dev"

# ===== OWNER CONFIG =====
OWNER_ID = 8066199853

# ===== BOT CONFIG =====
FREE_CREDITS = 2
REFERRAL_BONUS = 2
REFERRALS_NEEDED = 5

# ==================== DATABASE SETUP ====================
db_path = '/tmp/bot_database.db'
conn = sqlite3.connect(db_path, check_same_thread=False)
c = conn.cursor()

# Users table
c.execute('''CREATE TABLE IF NOT EXISTS users
             (user_id INTEGER PRIMARY KEY,
              username TEXT,
              verified INTEGER DEFAULT 0,
              is_admin INTEGER DEFAULT 0,
              is_owner INTEGER DEFAULT 0,
              is_banned INTEGER DEFAULT 0,
              credits_used INTEGER DEFAULT 0,
              total_credits INTEGER DEFAULT 2,
              referrals_count INTEGER DEFAULT 0,
              batch_type TEXT DEFAULT 'free',
              joined_date TEXT)''')

# Referrals table
c.execute('''CREATE TABLE IF NOT EXISTS referrals
             (referrer_id INTEGER,
              referred_id INTEGER,
              referred_date TEXT,
              PRIMARY KEY (referrer_id, referred_id))''')

# Banned users table
c.execute('''CREATE TABLE IF NOT EXISTS banned_users
             (user_id INTEGER PRIMARY KEY,
              banned_by INTEGER,
              ban_reason TEXT,
              ban_date TEXT)''')

# Bot settings table
c.execute('''CREATE TABLE IF NOT EXISTS bot_settings
             (setting_name TEXT PRIMARY KEY,
              setting_value TEXT,
              changed_by INTEGER,
              changed_date TEXT)''')

# Insert default settings
c.execute("INSERT OR IGNORE INTO bot_settings VALUES ('bot_active', 'true', ?, ?)", (OWNER_ID, datetime.now()))
c.execute("INSERT OR IGNORE INTO bot_settings VALUES ('maintenance', 'false', ?, ?)", (OWNER_ID, datetime.now()))
c.execute("INSERT OR IGNORE INTO bot_settings VALUES ('join_check', 'true', ?, ?)", (OWNER_ID, datetime.now()))
c.execute("INSERT OR IGNORE INTO bot_settings VALUES ('credit_system', 'true', ?, ?)", (OWNER_ID, datetime.now()))

conn.commit()

# ==================== DATABASE FUNCTIONS ====================

def ensure_owner_in_db():
    c.execute("INSERT OR REPLACE INTO users (user_id, is_owner, is_admin, verified, total_credits, batch_type, joined_date) VALUES (?, 1, 1, 1, 999999, 'owner', ?)",
              (OWNER_ID, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()

ensure_owner_in_db()

def is_admin_user(user_id):
    if user_id == OWNER_ID:
        return True
    c.execute("SELECT is_admin FROM users WHERE user_id = ?", (user_id,))
    result = c.fetchone()
    return result and result[0] == 1

def is_owner_user(user_id):
    return user_id == OWNER_ID

def is_user_banned(user_id):
    c.execute("SELECT * FROM banned_users WHERE user_id = ?", (user_id,))
    return c.fetchone() is not None

def get_setting(setting_name):
    c.execute("SELECT setting_value FROM bot_settings WHERE setting_name = ?", (setting_name,))
    result = c.fetchone()
    return result[0] if result else 'true'

def update_setting(setting_name, value, changed_by):
    c.execute("UPDATE bot_settings SET setting_value = ?, changed_by = ?, changed_date = ? WHERE setting_name = ?",
              (value, changed_by, datetime.now(), setting_name))
    conn.commit()

# ==================== BAN/UNBAN FUNCTIONS ====================

def ban_user(user_id, banned_by, reason="No reason"):
    c.execute("INSERT OR REPLACE INTO banned_users VALUES (?, ?, ?, ?)",
              (user_id, banned_by, reason, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    c.execute("UPDATE users SET is_banned = 1 WHERE user_id = ?", (user_id,))
    conn.commit()

def unban_user(user_id):
    c.execute("DELETE FROM banned_users WHERE user_id = ?", (user_id,))
    c.execute("UPDATE users SET is_banned = 0 WHERE user_id = ?", (user_id,))
    conn.commit()

# ==================== ADMIN FUNCTIONS ====================

def add_admin(user_id):
    c.execute("UPDATE users SET is_admin = 1, batch_type = 'admin', total_credits = 999999 WHERE user_id = ?", (user_id,))
    conn.commit()

def remove_admin(user_id):
    if user_id != OWNER_ID:
        c.execute("UPDATE users SET is_admin = 0, batch_type = 'free', total_credits = ? WHERE user_id = ?", (FREE_CREDITS, user_id))
        conn.commit()

def block_admin(user_id, blocked_by, reason="No reason"):
    if user_id != OWNER_ID:
        c.execute("UPDATE users SET is_admin = 0, is_banned = 1, batch_type = 'banned' WHERE user_id = ?", (user_id,))
        c.execute("INSERT OR REPLACE INTO banned_users VALUES (?, ?, ?, ?)",
                  (user_id, blocked_by, reason, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()

def set_admin_limit(user_id, limit):
    if user_id != OWNER_ID:
        c.execute("UPDATE users SET total_credits = ? WHERE user_id = ?", (limit, user_id))
        conn.commit()

# ==================== USER CREDITS FUNCTIONS ====================

def get_user_credits(user_id):
    if is_user_banned(user_id):
        return {'used': 0, 'total': 0, 'left': 0, 'referrals': 0, 'batch': 'banned'}
    
    c.execute("SELECT credits_used, total_credits, referrals_count, batch_type FROM users WHERE user_id = ?", (user_id,))
    result = c.fetchone()
    
    if result:
        used, total, referrals, batch = result
        return {
            'used': used,
            'total': total,
            'left': total - used,
            'referrals': referrals,
            'batch': batch
        }
    else:
        c.execute("INSERT INTO users (user_id, total_credits, joined_date) VALUES (?, ?, ?)",
                 (user_id, FREE_CREDITS, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
        return {'used': 0, 'total': FREE_CREDITS, 'left': FREE_CREDITS, 'referrals': 0, 'batch': 'free'}

def use_credit(user_id):
    if user_id == OWNER_ID or is_admin_user(user_id):
        return True
    
    if is_user_banned(user_id):
        return False
    
    credit_system = get_setting('credit_system')
    if credit_system == 'false':
        return True
    
    credits = get_user_credits(user_id)
    if credits['left'] > 0:
        c.execute("UPDATE users SET credits_used = credits_used + 1 WHERE user_id = ?", (user_id,))
        conn.commit()
        return True
    return False

def add_referral(referrer_id, referred_id):
    c.execute("SELECT * FROM referrals WHERE referrer_id = ? AND referred_id = ?", (referrer_id, referred_id))
    if c.fetchone():
        return False
    
    c.execute("INSERT INTO referrals VALUES (?, ?, ?)",
             (referrer_id, referred_id, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    c.execute("UPDATE users SET referrals_count = referrals_count + 1 WHERE user_id = ?", (referrer_id,))
    
    c.execute("SELECT referrals_count FROM users WHERE user_id = ?", (referrer_id,))
    count = c.fetchone()[0]
    
    if count % REFERRALS_NEEDED == 0:
        c.execute("UPDATE users SET total_credits = total_credits + ? WHERE user_id = ?", (REFERRAL_BONUS, referrer_id))
        conn.commit()
        return True
    else:
        conn.commit()
        return False

def set_user_credits(user_id, amount):
    c.execute("UPDATE users SET total_credits = ? WHERE user_id = ?", (amount, user_id))
    conn.commit()

def add_user_credits(user_id, amount):
    c.execute("UPDATE users SET total_credits = total_credits + ? WHERE user_id = ?", (amount, user_id))
    conn.commit()

def remove_user_credits(user_id, amount):
    c.execute("UPDATE users SET total_credits = total_credits - ? WHERE user_id = ?", (amount, user_id))
    conn.commit()

def reset_user_credits(user_id):
    c.execute("UPDATE users SET credits_used = 0, total_credits = ? WHERE user_id = ?", (FREE_CREDITS, user_id))
    conn.commit()

def set_user_batch(user_id, batch_type):
    c.execute("UPDATE users SET batch_type = ? WHERE user_id = ?", (batch_type, user_id))
    if batch_type == 'premium':
        c.execute("UPDATE users SET total_credits = 50 WHERE user_id = ?", (user_id,))
    elif batch_type == 'star':
        c.execute("UPDATE users SET total_credits = 100 WHERE user_id = ?", (user_id,))
    elif batch_type == 'admin':
        c.execute("UPDATE users SET total_credits = 999999, is_admin = 1 WHERE user_id = ?", (user_id,))
    conn.commit()

# ==================== BOT INIT ====================
bot = telebot.TeleBot(BOT_TOKEN)

# Dictionary to store user's last message IDs for cleanup
user_last_messages = {}

def cleanup_previous_messages(chat_id, user_id, exclude_msg_id=None):
    """Delete user's previous messages to keep chat clean"""
    if user_id in user_last_messages:
        for msg_id in user_last_messages[user_id]:
            if exclude_msg_id and msg_id == exclude_msg_id:
                continue
            try:
                bot.delete_message(chat_id, msg_id)
            except:
                pass
    user_last_messages[user_id] = []

def track_message(user_id, message_id):
    """Track user's messages for later cleanup"""
    if user_id not in user_last_messages:
        user_last_messages[user_id] = []
    user_last_messages[user_id].append(message_id)
    # Keep only last 5 messages
    if len(user_last_messages[user_id]) > 5:
        user_last_messages[user_id] = user_last_messages[user_id][-5:]

# ==================== CHECK MEMBERSHIP ====================
def check_membership(user_id):
    join_check = get_setting('join_check')
    if join_check == 'false':
        return True
    
    try:
        group_member = bot.get_chat_member(GROUP_ID, user_id)
        group_ok = group_member.status in ['member', 'administrator', 'creator']
        
        channel_member = bot.get_chat_member(CHANNEL_ID, user_id)
        channel_ok = channel_member.status in ['member', 'administrator', 'creator']
        
        return group_ok and channel_ok
    except:
        return False

def is_user_verified(user_id):
    c.execute("SELECT verified FROM users WHERE user_id = ?", (user_id,))
    result = c.fetchone()
    return result and result[0] == 1

def mark_user_verified(user_id):
    c.execute("UPDATE users SET verified = 1 WHERE user_id = ?", (user_id,))
    conn.commit()

# ==================== API FUNCTION ====================
def fetch_data(endpoint, query):
    start_time = time.time()
    try:
        url = f"{API_BASE_URL}/{endpoint}?key={API_KEY}&num={query}"
        print(f"Fetching: {url}")
        
        response = requests.get(url, timeout=15)
        data = response.json()
        
        elapsed = round(time.time() - start_time, 2)
        
        final_data = {
            "brand": BRAND,
            "creator": CREATOR,
            "time": f"{elapsed}s",
            "success": True
        }
        
        if isinstance(data, dict):
            if 'data' in data:
                final_data['data'] = data['data']
            else:
                final_data['data'] = data
        elif isinstance(data, list):
            final_data['data'] = data
        else:
            final_data['data'] = {"result": data}
        
        formatted = json.dumps(final_data, indent=2, ensure_ascii=False)
        return f"**{BRAND}**\n\n```json\n{formatted}\n```"
        
    except requests.exceptions.Timeout:
        return f"**{BRAND}**\n\n❌ API Timeout! Server slow."
    except requests.exceptions.ConnectionError:
        return f"**{BRAND}**\n\n❌ Connection Error! API down."
    except Exception as e:
        return f"**{BRAND}**\n\n❌ Error: {str(e)}"

# ==================== API COMMANDS LIST ====================
API_COMMANDS = {
    'num': '📱 Phone Number Lookup',
    'insta': '📸 Instagram Profile Info',
    'rto': '🚗 RTO Vehicle Details',
    'ff': '🎮 Free Fire UID Info',
    'ip': '🌐 IP Address Geolocation',
    'pan': '💳 PAN Card Details',
    'ifsc': '🏦 IFSC Code Bank Info',
    'aadhar': '🆔 Aadhar Card Info',
    'vehicle': '🚘 Vehicle Registration Details',
    'mail': '📧 Email Address Lookup'
}

# ==================== MESSAGES ====================

HELP_MESSAGE = f"""
╔══════════════════════════════╗
║     🌀 HELP MENU 🌀          ║
╠══════════════════════════════╣
║   {BRAND}                    ║
╠══════════════════════════════╣
║   📌 BASIC COMMANDS:         ║
║   ━━━━━━━━━━━━━━━━━━━━━       ║
║   /start - Start Bot         ║
║   /help - This Menu          ║
║   /profile - Your Stats      ║
║   /share - Referral Link     ║
║   /verify - Verify Member    ║
║   /admins - Contact Team     ║
╠══════════════════════════════╣
║   🔍 INFO COMMANDS:          ║
║   ━━━━━━━━━━━━━━━━━━━━━       ║
"""

for cmd, desc in API_COMMANDS.items():
    HELP_MESSAGE += f"║   /{cmd} [value] - {desc}\n"

HELP_MESSAGE += f"""
╠══════════════════════════════╣
║   💡 Examples:               ║
║   /num 9876543210           ║
║   /insta virat.kohli        ║
║   /aadhar 123456789012      ║
╠══════════════════════════════╣
║   ⚡ FREE: {FREE_CREDITS} Credits     ║
║   🔥 Refer {REFERRALS_NEEDED} = +{REFERRAL_BONUS} ║
║   👑 {BRAND}                  ║
╚══════════════════════════════╝
"""

WELCOME_CAPTION = f"""
╔══════════════════════════════╗
║     🌀 WELCOME TO BOT 🌀     ║
╠══════════════════════════════╣
║   {BRAND}                    ║
╠══════════════════════════════╣
║   ✅ VERIFICATION SUCCESSFUL ║
║   ━━━━━━━━━━━━━━━━━━━━━       ║
║   ✨ You can now use the bot! ║
║   ⚡ Free: {FREE_CREDITS} Credits    ║
║   📌 Use /help for commands   ║
║   👑 {BRAND}                  ║
╚══════════════════════════════╝
"""

# ==================== START COMMAND ====================
@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    # Cleanup previous messages
    cleanup_previous_messages(chat_id, user_id)
    
    if is_user_banned(user_id) and user_id != OWNER_ID:
        msg = bot.reply_to(message, "🚫 You are banned from using this bot!")
        track_message(user_id, msg.message_id)
        return
    
    # Check for referral
    args = message.text.split()
    if len(args) > 1 and args[1].startswith('ref_'):
        try:
            referrer_id = int(args[1].replace('ref_', ''))
            if referrer_id != user_id:
                add_referral(referrer_id, user_id)
        except:
            pass
    
    # Step 1: Image bhejo
    try:
        img_msg = bot.send_photo(chat_id, START_IMAGE, caption="🌀 **Tatsumaki Bot**", parse_mode="Markdown")
        track_message(user_id, img_msg.message_id)
    except:
        img_msg = bot.send_message(chat_id, "🌀 **Tatsumaki Bot**", parse_mode="Markdown")
        track_message(user_id, img_msg.message_id)
    
    time.sleep(1)
    
    # Step 2: Check if already verified
    if is_user_verified(user_id):
        # Cleanup again before welcome video
        cleanup_previous_messages(chat_id, user_id, img_msg.message_id)
        
        try:
            video_msg = bot.send_video(chat_id, WELCOME_VIDEO, caption=WELCOME_CAPTION, parse_mode="Markdown", supports_streaming=True)
            track_message(user_id, video_msg.message_id)
        except:
            text_msg = bot.send_message(chat_id, WELCOME_CAPTION, parse_mode="Markdown")
            track_message(user_id, text_msg.message_id)
        return
    
    # Step 3: Membership button
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("📢 Join Group", url=GROUP_LINK),
        InlineKeyboardButton("📣 Join Channel", url=CHANNEL_LINK)
    )
    markup.add(InlineKeyboardButton("✅ Verify Membership", callback_data="verify"))
    
    verify_msg = bot.send_message(
        chat_id,
        "**🔒 Membership Required!**\n\n1️⃣ Join Group & Channel\n2️⃣ Click Verify button",
        reply_markup=markup,
        parse_mode="Markdown"
    )
    track_message(user_id, verify_msg.message_id)

# ==================== VERIFY CALLBACK ====================
@bot.callback_query_handler(func=lambda call: call.data == "verify")
def verify_callback(call):
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    message_id = call.message.message_id
    
    # Delete the verify message
    try:
        bot.delete_message(chat_id, message_id)
    except:
        pass
    
    # Clear previous messages
    cleanup_previous_messages(chat_id, user_id)
    
    if is_user_banned(user_id) and user_id != OWNER_ID:
        bot.answer_callback_query(call.id, "❌ You are banned!", show_alert=True)
        return
    
    if check_membership(user_id):
        mark_user_verified(user_id)
        
        try:
            video_msg = bot.send_video(chat_id, WELCOME_VIDEO, caption=WELCOME_CAPTION, parse_mode="Markdown", supports_streaming=True)
            track_message(user_id, video_msg.message_id)
        except:
            text_msg = bot.send_message(chat_id, WELCOME_CAPTION, parse_mode="Markdown")
            track_message(user_id, text_msg.message_id)
        
        bot.answer_callback_query(call.id, "✅ Verified! Welcome!")
    else:
        markup = InlineKeyboardMarkup(row_width=2)
        markup.add(
            InlineKeyboardButton("📢 Join Group", url=GROUP_LINK),
            InlineKeyboardButton("📣 Join Channel", url=CHANNEL_LINK)
        )
        markup.add(InlineKeyboardButton("✅ Try Again", callback_data="verify"))
        
        fail_msg = bot.send_message(
            chat_id,
            "❌ **Not a member!**\n\nPlease join both Group & Channel first.",
            reply_markup=markup,
            parse_mode="Markdown"
        )
        track_message(user_id, fail_msg.message_id)
        
        bot.answer_callback_query(call.id, "❌ Not verified")

# ==================== HELP COMMAND ====================
@bot.message_handler(commands=['help'])
def help_command(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    # Cleanup previous messages
    cleanup_previous_messages(chat_id, user_id, message.message_id)
    
    help_msg = bot.reply_to(message, HELP_MESSAGE, parse_mode="Markdown")
    track_message(user_id, help_msg.message_id)

# ==================== PROFILE COMMAND ====================
@bot.message_handler(commands=['profile'])
def profile_command(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    # Cleanup previous messages
    cleanup_previous_messages(chat_id, user_id, message.message_id)
    
    if is_user_banned(user_id) and user_id != OWNER_ID:
        msg = bot.reply_to(message, "🚫 You are banned!")
        track_message(user_id, msg.message_id)
        return
    
    username = message.from_user.username or "unknown"
    credits = get_user_credits(user_id)
    next_bonus = REFERRALS_NEEDED - (credits['referrals'] % REFERRALS_NEEDED)
    if next_bonus == REFERRALS_NEEDED:
        next_bonus = 0
    
    profile_msg = f"""
╔══════════════════════════════╗
║     📊 YOUR PROFILE         ║
╠══════════════════════════════╣
║   {BRAND}                    ║
╠══════════════════════════════╣
║   👤 ID: {user_id}           ║
║   📛 @{username}             ║
║   🏷️ Batch: {credits['batch'].upper()} ║
╠══════════════════════════════╣
║   💰 CREDITS:                ║
║   ━━━━━━━━━━━━━━━━━━━━━       ║
║   📊 Used: {credits['used']}/{credits['total']}  ║
║   💎 Left: {credits['left']}           ║
║                               ║
║   👥 Referrals: {credits['referrals']}   ║
║   🔥 Next Bonus: {next_bonus}          ║
╠══════════════════════════════╣
║   🔗 /share - Get Referral   ║
║   👑 {BRAND}                  ║
╚══════════════════════════════╝
"""
    msg = bot.reply_to(message, profile_msg, parse_mode="Markdown")
    track_message(user_id, msg.message_id)

# ==================== SHARE COMMAND ====================
@bot.message_handler(commands=['share'])
def share_command(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    # Cleanup previous messages
    cleanup_previous_messages(chat_id, user_id, message.message_id)
    
    if is_user_banned(user_id) and user_id != OWNER_ID:
        msg = bot.reply_to(message, "🚫 You are banned!")
        track_message(user_id, msg.message_id)
        return
    
    bot_username = bot.get_me().username
    referral_link = f"https://t.me/{bot_username}?start=ref_{user_id}"
    credits = get_user_credits(user_id)
    next_bonus = REFERRALS_NEEDED - (credits['referrals'] % REFERRALS_NEEDED)
    
    share_msg = f"""
╔══════════════════════════════╗
║     🔗 YOUR REFERRAL LINK   ║
╠══════════════════════════════╣
║   {BRAND}                    ║
╠══════════════════════════════╣
║   👥 Referrals: {credits['referrals']}   ║
║   🔥 Need {next_bonus} more    ║
║   ✨ +{REFERRAL_BONUS} Credits    ║
╠══════════════════════════════╣
║   `{referral_link}`          ║
╠══════════════════════════════╣
║   📤 Share with friends!     ║
╚══════════════════════════════╝
"""
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("📤 Share", switch_inline_query=f"Join Bot! {referral_link}"))
    
    msg = bot.reply_to(message, share_msg, parse_mode="Markdown", reply_markup=markup)
    track_message(user_id, msg.message_id)

# ==================== ADMINS COMMAND ====================
@bot.message_handler(commands=['admins'])
def admins_command(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    # Cleanup previous messages
    cleanup_previous_messages(chat_id, user_id, message.message_id)
    
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("👑 Contact Owner", url=f"tg://user?id={OWNER_ID}"))
    
    msg_text = f"""
╔══════════════════════════════╗
║     👑 CONTACT TEAM 👑      ║
╠══════════════════════════════╣
║   {BRAND}                    ║
╠══════════════════════════════╣
║   Owner ID: {OWNER_ID}       ║
╠══════════════════════════════╣
║   Click below to message     ║
╚══════════════════════════════╝
"""
    msg = bot.reply_to(message, msg_text, parse_mode="Markdown", reply_markup=markup)
    track_message(user_id, msg.message_id)

# ==================== VERIFY COMMAND ====================
@bot.message_handler(commands=['verify'])
def verify_command(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    # Cleanup previous messages
    cleanup_previous_messages(chat_id, user_id, message.message_id)
    
    if is_user_banned(user_id) and user_id != OWNER_ID:
        msg = bot.reply_to(message, "🚫 You are banned!")
        track_message(user_id, msg.message_id)
        return
    
    if check_membership(user_id):
        mark_user_verified(user_id)
        
        try:
            video_msg = bot.send_video(chat_id, WELCOME_VIDEO, caption=WELCOME_CAPTION, parse_mode="Markdown", supports_streaming=True)
            track_message(user_id, video_msg.message_id)
        except:
            text_msg = bot.send_message(chat_id, WELCOME_CAPTION, parse_mode="Markdown")
            track_message(user_id, text_msg.message_id)
    else:
        markup = InlineKeyboardMarkup()
        markup.add(
            InlineKeyboardButton("📢 Join Group", url=GROUP_LINK),
            InlineKeyboardButton("📣 Join Channel", url=CHANNEL_LINK)
        )
        fail_msg = bot.reply_to(
            message,
            "❌ **Not a member!**\n\nPlease join Group & Channel first.",
            reply_markup=markup,
            parse_mode="Markdown"
        )
        track_message(user_id, fail_msg.message_id)

# ==================== INFO COMMANDS WITH ANIMATION ====================
@bot.message_handler(commands=list(API_COMMANDS.keys()))
def info_commands(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    # Cleanup previous messages
    cleanup_previous_messages(chat_id, user_id, message.message_id)
    
    if is_user_banned(user_id) and user_id != OWNER_ID:
        msg = bot.reply_to(message, "🚫 You are banned from using this bot!")
        track_message(user_id, msg.message_id)
        return
    
    if not is_user_verified(user_id):
        if not check_membership(user_id):
            markup = InlineKeyboardMarkup()
            markup.add(
                InlineKeyboardButton("📢 Join Group", url=GROUP_LINK),
                InlineKeyboardButton("📣 Join Channel", url=CHANNEL_LINK)
            )
            deny_msg = bot.reply_to(
                message,
                "❌ **Access Denied!**\n\nPlease join Group & Channel first.\nThen use /verify",
                reply_markup=markup,
                parse_mode="Markdown"
            )
            track_message(user_id, deny_msg.message_id)
            return
        else:
            mark_user_verified(user_id)
    
    if not use_credit(user_id):
        bot_username = bot.get_me().username
        referral_link = f"https://t.me/{bot_username}?start=ref_{user_id}"
        no_credit_msg = bot.reply_to(
            message,
            f"❌ **No Credits Left!**\n\nShare with {REFERRALS_NEEDED} friends to get +{REFERRAL_BONUS} credits!\n\n/share\n\n{referral_link}",
            parse_mode="Markdown"
        )
        track_message(user_id, no_credit_msg.message_id)
        return
    
    cmd = message.text.split()[0][1:]
    args = message.text.split()[1] if len(message.text.split()) > 1 else None
    
    if not args:
        usage_msg = bot.reply_to(message, f"❌ Usage: /{cmd} [value]\n\nExample: /{cmd} 9876543210")
        track_message(user_id, usage_msg.message_id)
        return
    
    # Send typing action
    bot.send_chat_action(chat_id, 'typing')
    
    # Animation frames
    frames = ["🔍 Searching", "🔍 Searching.", "🔍 Searching..", "🔍 Searching...", 
              "⚡ Processing", "⚡ Processing.", "⚡ Processing..", "⚡ Processing...",
              "📡 Fetching data", "📡 Fetching data.", "📡 Fetching data..", "📡 Fetching data..."]
    
    # Send search animation
    search_msg = bot.reply_to(message, "🔍 **Searching**", parse_mode="Markdown")
    
    # Animate search (6 quick updates)
    for i in range(6):
        time.sleep(0.4)
        try:
            bot.edit_message_text(f"**{frames[i]}**", chat_id, search_msg.message_id, parse_mode="Markdown")
        except:
            pass
    
    # Fetch data
    result = fetch_data(cmd, args)
    
    # Delete search message
    try:
        bot.delete_message(chat_id, search_msg.message_id)
    except:
        pass
    
    # Get credits
    credits = get_user_credits(user_id)
    
    # Send result with remaining credits
    final_msg = result + f"\n\n⚡ Remaining: {credits['left']}"
    result_msg = bot.reply_to(message, final_msg, parse_mode="Markdown")
    track_message(user_id, result_msg.message_id)

# ==================== ADMIN COMMANDS ====================

@bot.message_handler(commands=['ban'])
def ban_command(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    # Cleanup previous messages
    cleanup_previous_messages(chat_id, user_id, message.message_id)
    
    if not is_admin_user(user_id):
        deny_msg = bot.reply_to(message, "❌ Admin only command!")
        track_message(user_id, deny_msg.message_id)
        return
    
    args = message.text.split()
    if len(args) < 2:
        usage_msg = bot.reply_to(message, "Usage: /ban [user_id] [reason]")
        track_message(user_id, usage_msg.message_id)
        return
    
    try:
        target = int(args[1])
        reason = " ".join(args[2:]) if len(args) > 2 else "No reason"
        
        if target == OWNER_ID:
            error_msg = bot.reply_to(message, "❌ Cannot ban owner!")
            track_message(user_id, error_msg.message_id)
            return
        
        ban_user(target, user_id, reason)
        success_msg = bot.reply_to(message, f"✅ User {target} banned!\nReason: {reason}")
        track_message(user_id, success_msg.message_id)
    except:
        error_msg = bot.reply_to(message, "❌ Invalid user ID!")
        track_message(user_id, error_msg.message_id)

@bot.message_handler(commands=['unban'])
def unban_command(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    cleanup_previous_messages(chat_id, user_id, message.message_id)
    
    if not is_admin_user(user_id):
        deny_msg = bot.reply_to(message, "❌ Admin only command!")
        track_message(user_id, deny_msg.message_id)
        return
    
    args = message.text.split()
    if len(args) < 2:
        usage_msg = bot.reply_to(message, "Usage: /unban [user_id]")
        track_message(user_id, usage_msg.message_id)
        return
    
    try:
        target = int(args[1])
        unban_user(target)
        success_msg = bot.reply_to(message, f"✅ User {target} unbanned!")
        track_message(user_id, success_msg.message_id)
    except:
        error_msg = bot.reply_to(message, "❌ Invalid user ID!")
        track_message(user_id, error_msg.message_id)

@bot.message_handler(commands=['userinfo'])
def userinfo_command(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    cleanup_previous_messages(chat_id, user_id, message.message_id)
    
    if not is_admin_user(user_id):
        deny_msg = bot.reply_to(message, "❌ Admin only command!")
        track_message(user_id, deny_msg.message_id)
        return
    
    args = message.text.split()
    if len(args) < 2:
        usage_msg = bot.reply_to(message, "Usage: /userinfo [user_id]")
        track_message(user_id, usage_msg.message_id)
        return
    
    try:
        target = int(args[1])
        credits = get_user_credits(target)
        
        info_msg = f"""
📊 **USER INFO**
━━━━━━━━━━━━━━━━
🆔 ID: {target}
🏷️ Batch: {credits['batch'].upper()}
👑 Admin: {'Yes' if is_admin_user(target) else 'No'}
🔴 Banned: {'Yes' if is_user_banned(target) else 'No'}
💰 Credits: {credits['used']}/{credits['total']}
👥 Referrals: {credits['referrals']}
"""
        result_msg = bot.reply_to(message, info_msg, parse_mode="Markdown")
        track_message(user_id, result_msg.message_id)
    except:
        error_msg = bot.reply_to(message, "❌ Invalid user ID!")
        track_message(user_id, error_msg.message_id)

@bot.message_handler(commands=['addadmin'])
def addadmin_command(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    cleanup_previous_messages(chat_id, user_id, message.message_id)
    
    if not is_admin_user(user_id):
        deny_msg = bot.reply_to(message, "❌ Admin only command!")
        track_message(user_id, deny_msg.message_id)
        return
    
    args = message.text.split()
    if len(args) < 2:
        usage_msg = bot.reply_to(message, "Usage: /addadmin [user_id]")
        track_message(user_id, usage_msg.message_id)
        return
    
    try:
        target = int(args[1])
        if target == OWNER_ID:
            error_msg = bot.reply_to(message, "❌ User is already owner!")
            track_message(user_id, error_msg.message_id)
            return
        add_admin(target)
        success_msg = bot.reply_to(message, f"✅ User {target} is now ADMIN!")
        track_message(user_id, success_msg.message_id)
    except:
        error_msg = bot.reply_to(message, "❌ Invalid user ID!")
        track_message(user_id, error_msg.message_id)

@bot.message_handler(commands=['removeadmin'])
def removeadmin_command(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    cleanup_previous_messages(chat_id, user_id, message.message_id)
    
    if not is_admin_user(user_id):
        deny_msg = bot.reply_to(message, "❌ Admin only command!")
        track_message(user_id, deny_msg.message_id)
        return
    
    args = message.text.split()
    if len(args) < 2:
        usage_msg = bot.reply_to(message, "Usage: /removeadmin [user_id]")
        track_message(user_id, usage_msg.message_id)
        return
    
    try:
        target = int(args[1])
        if target == OWNER_ID:
            error_msg = bot.reply_to(message, "❌ Cannot remove owner!")
            track_message(user_id, error_msg.message_id)
            return
        remove_admin(target)
        success_msg = bot.reply_to(message, f"✅ User {target} is no longer admin!")
        track_message(user_id, success_msg.message_id)
    except:
        error_msg = bot.reply_to(message, "❌ Invalid user ID!")
        track_message(user_id, error_msg.message_id)

@bot.message_handler(commands=['blockadmin'])
def blockadmin_command(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    cleanup_previous_messages(chat_id, user_id, message.message_id)
    
    if not is_admin_user(user_id):
        deny_msg = bot.reply_to(message, "❌ Admin only command!")
        track_message(user_id, deny_msg.message_id)
        return
    
    args = message.text.split()
    if len(args) < 2:
        usage_msg = bot.reply_to(message, "Usage: /blockadmin [user_id] [reason]")
        track_message(user_id, usage_msg.message_id)
        return
    
    try:
        target = int(args[1])
        reason = " ".join(args[2:]) if len(args) > 2 else "Admin blocked"
        
        if target == OWNER_ID:
            error_msg = bot.reply_to(message, "❌ Cannot block owner!")
            track_message(user_id, error_msg.message_id)
            return
        
        block_admin(target, user_id, reason)
        success_msg = bot.reply_to(message, f"✅ Admin {target} blocked!\nReason: {reason}")
        track_message(user_id, success_msg.message_id)
    except:
        error_msg = bot.reply_to(message, "❌ Invalid user ID!")
        track_message(user_id, error_msg.message_id)

@bot.message_handler(commands=['setadminlimit'])
def setadminlimit_command(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    cleanup_previous_messages(chat_id, user_id, message.message_id)
    
    if not is_admin_user(user_id):
        deny_msg = bot.reply_to(message, "❌ Admin only command!")
        track_message(user_id, deny_msg.message_id)
        return
    
    args = message.text.split()
    if len(args) < 3:
        usage_msg = bot.reply_to(message, "Usage: /setadminlimit [admin_id] [limit]")
        track_message(user_id, usage_msg.message_id)
        return
    
    try:
        target = int(args[1])
        limit = int(args[2])
        
        if target == OWNER_ID:
            error_msg = bot.reply_to(message, "❌ Cannot set limit for owner!")
            track_message(user_id, error_msg.message_id)
            return
        
        set_admin_limit(target, limit)
        success_msg = bot.reply_to(message, f"✅ Admin {target} limit set to {limit}!")
        track_message(user_id, success_msg.message_id)
    except:
        error_msg = bot.reply_to(message, "❌ Invalid input!")
        track_message(user_id, error_msg.message_id)

@bot.message_handler(commands=['adminlist'])
def adminlist_command(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    cleanup_previous_messages(chat_id, user_id, message.message_id)
    
    if not is_admin_user(user_id):
        deny_msg = bot.reply_to(message, "❌ Admin only command!")
        track_message(user_id, deny_msg.message_id)
        return
    
    c.execute("SELECT user_id FROM users WHERE is_admin = 1 OR is_owner = 1")
    admins = c.fetchall()
    
    msg = "👑 **ADMIN TEAM** 👑\n\n"
    markup = InlineKeyboardMarkup()
    
    for (admin_id,) in admins:
        role = "👑 OWNER" if admin_id == OWNER_ID else "👥 ADMIN"
        msg += f"{role}: `{admin_id}`\n"
        if admin_id != OWNER_ID:
            markup.add(InlineKeyboardButton(f"📩 Message {admin_id}", url=f"tg://user?id={admin_id}"))
    
    result_msg = bot.reply_to(message, msg, parse_mode="Markdown", reply_markup=markup)
    track_message(user_id, result_msg.message_id)

@bot.message_handler(commands=['setuserlimit'])
def setuserlimit_command(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    cleanup_previous_messages(chat_id, user_id, message.message_id)
    
    if not is_admin_user(user_id):
        deny_msg = bot.reply_to(message, "❌ Admin only command!")
        track_message(user_id, deny_msg.message_id)
        return
    
    args = message.text.split()
    if len(args) < 3:
        usage_msg = bot.reply_to(message, "Usage: /setuserlimit [user_id] [limit]")
        track_message(user_id, usage_msg.message_id)
        return
    
    try:
        target = int(args[1])
        limit = int(args[2])
        set_user_credits(target, limit)
        success_msg = bot.reply_to(message, f"✅ User {target} limit set to {limit}!")
        track_message(user_id, success_msg.message_id)
    except:
        error_msg = bot.reply_to(message, "❌ Invalid input!")
        track_message(user_id, error_msg.message_id)

@bot.message_handler(commands=['addcredits'])
def addcredits_command(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    cleanup_previous_messages(chat_id, user_id, message.message_id)
    
    if not is_admin_user(user_id):
        deny_msg = bot.reply_to(message, "❌ Admin only command!")
        track_message(user_id, deny_msg.message_id)
        return
    
    args = message.text.split()
    if len(args) < 3:
        usage_msg = bot.reply_to(message, "Usage: /addcredits [user_id] [amount]")
        track_message(user_id, usage_msg.message_id)
        return
    
    try:
        target = int(args[1])
        amount = int(args[2])
        add_user_credits(target, amount)
        success_msg = bot.reply_to(message, f"✅ Added {amount} credits to user {target}!")
        track_message(user_id, success_msg.message_id)
    except:
        error_msg = bot.reply_to(message, "❌ Invalid input!")
        track_message(user_id, error_msg.message_id)

@bot.message_handler(commands=['removecredits'])
def removecredits_command(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    cleanup_previous_messages(chat_id, user_id, message.message_id)
    
    if not is_admin_user(user_id):
        deny_msg = bot.reply_to(message, "❌ Admin only command!")
        track_message(user_id, deny_msg.message_id)
        return
    
    args = message.text.split()
    if len(args) < 3:
        usage_msg = bot.reply_to(message, "Usage: /removecredits [user_id] [amount]")
        track_message(user_id, usage_msg.message_id)
        return
    
    try:
        target = int(args[1])
        amount = int(args[2])
        remove_user_credits(target, amount)
        success_msg = bot.reply_to(message, f"✅ Removed {amount} credits from user {target}!")
        track_message(user_id, success_msg.message_id)
    except:
        error_msg = bot.reply_to(message, "❌ Invalid input!")
        track_message(user_id, error_msg.message_id)

@bot.message_handler(commands=['resetcredits'])
def resetcredits_command(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    cleanup_previous_messages(chat_id, user_id, message.message_id)
    
    if not is_admin_user(user_id):
        deny_msg = bot.reply_to(message, "❌ Admin only command!")
        track_message(user_id, deny_msg.message_id)
        return
    
    args = message.text.split()
    if len(args) < 2:
        usage_msg = bot.reply_to(message, "Usage: /resetcredits [user_id]")
        track_message(user_id, usage_msg.message_id)
        return
    
    try:
        target = int(args[1])
        reset_user_credits(target)
        success_msg = bot.reply_to(message, f"✅ User {target} credits reset to {FREE_CREDITS}!")
        track_message(user_id, success_msg.message_id)
    except:
        error_msg = bot.reply_to(message, "❌ Invalid user ID!")
        track_message(user_id, error_msg.message_id)

@bot.message_handler(commands=['givepremium'])
def givepremium_command(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    cleanup_previous_messages(chat_id, user_id, message.message_id)
    
    if not is_admin_user(user_id):
        deny_msg = bot.reply_to(message, "❌ Admin only command!")
        track_message(user_id, deny_msg.message_id)
        return
    
    args = message.text.split()
    if len(args) < 2:
        usage_msg = bot.reply_to(message, "Usage: /givepremium [user_id]")
        track_message(user_id, usage_msg.message_id)
        return
    
    try:
        target = int(args[1])
        set_user_batch(target, 'premium')
        success_msg = bot.reply_to(message, f"✅ User {target} is now PREMIUM!")
        track_message(user_id, success_msg.message_id)
    except:
        error_msg = bot.reply_to(message, "❌ Invalid user ID!")
        track_message(user_id, error_msg.message_id)

@bot.message_handler(commands=['givestar'])
def givestar_command(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    cleanup_previous_messages(chat_id, user_id, message.message_id)
    
    if not is_admin_user(user_id):
        deny_msg = bot.reply_to(message, "❌ Admin only command!")
        track_message(user_id, deny_msg.message_id)
        return
    
    args = message.text.split()
    if len(args) < 2:
        usage_msg = bot.reply_to(message, "Usage: /givestar [user_id]")
        track_message(user_id, usage_msg.message_id)
        return
    
    try:
        target = int(args[1])
        set_user_batch(target, 'star')
        success_msg = bot.reply_to(message, f"✅ User {target} is now STAR!")
        track_message(user_id, success_msg.message_id)
    except:
        error_msg = bot.reply_to(message, "❌ Invalid user ID!")
        track_message(user_id, error_msg.message_id)

@bot.message_handler(commands=['memberlist'])
def memberlist_command(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    cleanup_previous_messages(chat_id, user_id, message.message_id)
    
    if not is_admin_user(user_id):
        deny_msg = bot.reply_to(message, "❌ Admin only command!")
        track_message(user_id, deny_msg.message_id)
        return
    
    c.execute("SELECT COUNT(*) FROM users")
    total = c.fetchone()[0]
    
    c.execute("SELECT user_id, batch_type, is_banned FROM users ORDER BY joined_date DESC LIMIT 20")
    members = c.fetchall()
    
    msg = f"📋 **MEMBER LIST** (Last 20)\nTotal Members: {total}\n\n"
    for mid, batch, banned in members:
        emoji = "👑" if mid == OWNER_ID else "🔥" if batch == 'admin' else "⭐" if batch == 'star' else "💎" if batch == 'premium' else "👤"
        ban_emoji = "🔴" if banned else "🟢"
        msg += f"{ban_emoji} {emoji} `{mid}` - {batch}\n"
    
    result_msg = bot.reply_to(message, msg, parse_mode="Markdown")
    track_message(user_id, result_msg.message_id)

@bot.message_handler(commands=['premiumlist'])
def premiumlist_command(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    cleanup_previous_messages(chat_id, user_id, message.message_id)
    
    if not is_admin_user(user_id):
        deny_msg = bot.reply_to(message, "❌ Admin only command!")
        track_message(user_id, deny_msg.message_id)
        return
    
    c.execute("SELECT user_id FROM users WHERE batch_type IN ('premium', 'star', 'admin', 'owner')")
    premium = c.fetchall()
    
    if not premium:
        no_msg = bot.reply_to(message, "📝 No premium members!")
        track_message(user_id, no_msg.message_id)
        return
    
    msg = "💎 **PREMIUM MEMBERS** 💎\n\n"
    for (pid,) in premium[:20]:
        msg += f"• `{pid}`\n"
    
    result_msg = bot.reply_to(message, msg, parse_mode="Markdown")
    track_message(user_id, result_msg.message_id)

@bot.message_handler(commands=['banlist'])
def banlist_command(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    cleanup_previous_messages(chat_id, user_id, message.message_id)
    
    if not is_admin_user(user_id):
        deny_msg = bot.reply_to(message, "❌ Admin only command!")
        track_message(user_id, deny_msg.message_id)
        return
    
    c.execute("SELECT user_id, ban_reason, ban_date FROM banned_users")
    banned = c.fetchall()
    
    if not banned:
        no_msg = bot.reply_to(message, "📝 No banned users!")
        track_message(user_id, no_msg.message_id)
        return
    
    msg = "🔨 **BANNED USERS** 🔨\n\n"
    for bid, reason, date in banned:
        msg += f"• `{bid}` - {reason}\n  📅 {date[:10]}\n\n"
    
    result_msg = bot.reply_to(message, msg, parse_mode="Markdown")
    track_message(user_id, result_msg.message_id)

@bot.message_handler(commands=['boton'])
def boton_command(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    cleanup_previous_messages(chat_id, user_id, message.message_id)
    
    if not is_admin_user(user_id):
        deny_msg = bot.reply_to(message, "❌ Admin only command!")
        track_message(user_id, deny_msg.message_id)
        return
    
    update_setting('bot_active', 'true', user_id)
    success_msg = bot.reply_to(message, "🟢 **Bot is now ON!**", parse_mode="Markdown")
    track_message(user_id, success_msg.message_id)

@bot.message_handler(commands=['botoff'])
def botoff_command(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    cleanup_previous_messages(chat_id, user_id, message.message_id)
    
    if not is_admin_user(user_id):
        deny_msg = bot.reply_to(message, "❌ Admin only command!")
        track_message(user_id, deny_msg.message_id)
        return
    
    update_setting('bot_active', 'false', user_id)
    success_msg = bot.reply_to(message, "🔴 **Bot is now OFF!**", parse_mode="Markdown")
    track_message(user_id, success_msg.message_id)

@bot.message_handler(commands=['maintenance'])
def maintenance_command(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    cleanup_previous_messages(chat_id, user_id, message.message_id)
    
    if not is_admin_user(user_id):
        deny_msg = bot.reply_to(message, "❌ Admin only command!")
        track_message(user_id, deny_msg.message_id)
        return
    
    current = get_setting('maintenance')
    new_value = 'false' if current == 'true' else 'true'
    update_setting('maintenance', new_value, user_id)
    
    status = "ON" if new_value == 'true' else "OFF"
    success_msg = bot.reply_to(message, f"🛠️ **Maintenance mode is now {status}!**", parse_mode="Markdown")
    track_message(user_id, success_msg.message_id)

@bot.message_handler(commands=['togglejoin'])
def togglejoin_command(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    cleanup_previous_messages(chat_id, user_id, message.message_id)
    
    if not is_admin_user(user_id):
        deny_msg = bot.reply_to(message, "❌ Admin only command!")
        track_message(user_id, deny_msg.message_id)
        return
    
    current = get_setting('join_check')
    new_value = 'false' if current == 'true' else 'true'
    update_setting('join_check', new_value, user_id)
    
    status = "OFF" if new_value == 'false' else "ON"
    success_msg = bot.reply_to(message, f"🔒 **Join check is now {status}!**", parse_mode="Markdown")
    track_message(user_id, success_msg.message_id)

@bot.message_handler(commands=['togglecredits'])
def togglecredits_command(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    cleanup_previous_messages(chat_id, user_id, message.message_id)
    
    if not is_admin_user(user_id):
        deny_msg = bot.reply_to(message, "❌ Admin only command!")
        track_message(user_id, deny_msg.message_id)
        return
    
    current = get_setting('credit_system')
    new_value = 'false' if current == 'true' else 'true'
    update_setting('credit_system', new_value, user_id)
    
    status = "OFF" if new_value == 'false' else "ON"
    success_msg = bot.reply_to(message, f"💰 **Credit system is now {status}!**", parse_mode="Markdown")
    track_message(user_id, success_msg.message_id)

@bot.message_handler(commands=['settings'])
def settings_command(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    cleanup_previous_messages(chat_id, user_id, message.message_id)
    
    if not is_admin_user(user_id):
        deny_msg = bot.reply_to(message, "❌ Admin only command!")
        track_message(user_id, deny_msg.message_id)
        return
    
    bot_active = get_setting('bot_active')
    maintenance = get_setting('maintenance')
    join_check = get_setting('join_check')
    credit_system = get_setting('credit_system')
    
    msg = f"""
⚙️ **BOT SETTINGS**
━━━━━━━━━━━━━━━━
🟢 Bot Active: {'YES' if bot_active == 'true' else 'NO'}
🛠️ Maintenance: {'YES' if maintenance == 'true' else 'NO'}
🔒 Join Check: {'YES' if join_check == 'true' else 'NO'}
💰 Credit System: {'YES' if credit_system == 'true' else 'NO'}

👑 Owner: {OWNER_ID}
"""
    result_msg = bot.reply_to(message, msg, parse_mode="Markdown")
    track_message(user_id, result_msg.message_id)

# ==================== OWNER ONLY COMMANDS ====================

@bot.message_handler(commands=['broadcast'])
def broadcast_command(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    cleanup_previous_messages(chat_id, user_id, message.message_id)
    
    if user_id != OWNER_ID:
        deny_msg = bot.reply_to(message, "❌ Only owner can use this!")
        track_message(user_id, deny_msg.message_id)
        return
    
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        usage_msg = bot.reply_to(message, "Usage: /broadcast [message]")
        track_message(user_id, usage_msg.message_id)
        return
    
    broadcast_msg = args[1]
    c.execute("SELECT user_id FROM users WHERE is_banned = 0")
    users = c.fetchall()
    
    sent = 0
    for (uid,) in users:
        try:
            bot.send_message(uid, f"📢 **BROADCAST**\n\n{broadcast_msg}\n\n{BRAND}", parse_mode="Markdown")
            sent += 1
            time.sleep(0.05)
        except:
            continue
    
    success_msg = bot.reply_to(message, f"✅ Broadcast sent to {sent} users!")
    track_message(user_id, success_msg.message_id)

@bot.message_handler(commands=['stats'])
def stats_command(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    cleanup_previous_messages(chat_id, user_id, message.message_id)
    
    if user_id != OWNER_ID:
        deny_msg = bot.reply_to(message, "❌ Only owner can use this!")
        track_message(user_id, deny_msg.message_id)
        return
    
    c.execute("SELECT COUNT(*) FROM users")
    total_users = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM users WHERE is_admin = 1")
    total_admins = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM banned_users")
    total_banned = c.fetchone()[0]
    
    c.execute("SELECT SUM(credits_used) FROM users")
    total_commands = c.fetchone()[0] or 0
    
    msg = f"""
📊 **BOT STATISTICS**
━━━━━━━━━━━━━━━━
👥 Total Users: {total_users}
👑 Total Admins: {total_admins}
🔴 Banned Users: {total_banned}
📊 Commands Used: {total_commands}
"""
    result_msg = bot.reply_to(message, msg, parse_mode="Markdown")
    track_message(user_id, result_msg.message_id)

# ==================== ERROR HANDLER ====================
@bot.message_handler(func=lambda message: True)
def handle_all(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    cleanup_previous_messages(chat_id, user_id, message.message_id)
    
    error_msg = bot.reply_to(message, f"❌ Invalid Command!\n\nUse /help\n\n{BRAND}", parse_mode="Markdown")
    track_message(user_id, error_msg.message_id)

# ==================== FLASK APP ====================
app = Flask(__name__)

@app.route('/')
def home():
    return jsonify({
        "status": "online",
        "bot": "Tatsumaki",
        "brand": BRAND,
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })

def run_flask():
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)

# ==================== START BOT ====================
def run_bot():
    print("🚀 Tatsumaki Bot starting...")
    print(f"👑 {BRAND}")
    print(f"👑 Owner ID: {OWNER_ID}")
    print(f"📊 Total Commands: {len(API_COMMANDS)} APIs + Admin Commands")
    print("=" * 30)
    
    try:
        bot.remove_webhook()
        time.sleep(1)
    except:
        pass
    
    while True:
        try:
            bot.infinity_polling(timeout=60)
        except Exception as e:
            print(f"❌ Error: {e}")
            time.sleep(5)

if __name__ == "__main__":
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    run_bot()
