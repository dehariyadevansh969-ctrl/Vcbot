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
from concurrent.futures import ThreadPoolExecutor

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
API_TIMEOUT = 2  # 2 seconds timeout

# ==================== ULTRA FAST OPTIMIZATIONS ====================
executor = ThreadPoolExecutor(max_workers=20)  # More threads for speed
api_cache = {}
CACHE_TIME = 10  # Short cache for fresh data
db_cache = {}
DB_CACHE_TIME = 30

# Pre-loaded settings
bot_active_cache = "true"
maintenance_cache = "false"
join_check_cache = "true"
credit_system_cache = "true"
last_settings_update = time.time()

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

# ==================== FAST DATABASE FUNCTIONS ====================

def ensure_owner_in_db():
    c.execute("INSERT OR REPLACE INTO users (user_id, is_owner, is_admin, verified, total_credits, batch_type, joined_date) VALUES (?, 1, 1, 1, 999999, 'owner', ?)",
              (OWNER_ID, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()

ensure_owner_in_db()

def is_admin_user(user_id):
    if user_id == OWNER_ID:
        return True
    cache_key = f"admin_{user_id}"
    if cache_key in db_cache:
        return db_cache[cache_key]
    c.execute("SELECT is_admin FROM users WHERE user_id = ?", (user_id,))
    result = c.fetchone()
    value = result and result[0] == 1
    db_cache[cache_key] = value
    return value

def is_user_banned(user_id):
    cache_key = f"banned_{user_id}"
    if cache_key in db_cache:
        return db_cache[cache_key]
    c.execute("SELECT * FROM banned_users WHERE user_id = ?", (user_id,))
    value = c.fetchone() is not None
    db_cache[cache_key] = value
    return value

def get_setting(setting_name):
    global bot_active_cache, maintenance_cache, join_check_cache, credit_system_cache, last_settings_update
    
    # Update cache every 30 seconds
    if time.time() - last_settings_update > 30:
        c.execute("SELECT setting_value FROM bot_settings WHERE setting_name = 'bot_active'")
        bot_active_cache = c.fetchone()[0]
        c.execute("SELECT setting_value FROM bot_settings WHERE setting_name = 'maintenance'")
        maintenance_cache = c.fetchone()[0]
        c.execute("SELECT setting_value FROM bot_settings WHERE setting_name = 'join_check'")
        join_check_cache = c.fetchone()[0]
        c.execute("SELECT setting_value FROM bot_settings WHERE setting_name = 'credit_system'")
        credit_system_cache = c.fetchone()[0]
        last_settings_update = time.time()
    
    if setting_name == 'bot_active':
        return bot_active_cache
    elif setting_name == 'maintenance':
        return maintenance_cache
    elif setting_name == 'join_check':
        return join_check_cache
    elif setting_name == 'credit_system':
        return credit_system_cache
    return 'true'

def update_setting(setting_name, value, changed_by):
    global bot_active_cache, maintenance_cache, join_check_cache, credit_system_cache, last_settings_update
    c.execute("UPDATE bot_settings SET setting_value = ?, changed_by = ?, changed_date = ? WHERE setting_name = ?",
              (value, changed_by, datetime.now(), setting_name))
    conn.commit()
    # Update cache immediately
    if setting_name == 'bot_active':
        bot_active_cache = value
    elif setting_name == 'maintenance':
        maintenance_cache = value
    elif setting_name == 'join_check':
        join_check_cache = value
    elif setting_name == 'credit_system':
        credit_system_cache = value
    last_settings_update = time.time()

def get_user_credits(user_id):
    if is_user_banned(user_id):
        return {'used': 0, 'total': 0, 'left': 0, 'referrals': 0, 'batch': 'banned'}
    
    cache_key = f"credits_{user_id}"
    if cache_key in db_cache:
        return db_cache[cache_key]
    
    c.execute("SELECT credits_used, total_credits, referrals_count, batch_type FROM users WHERE user_id = ?", (user_id,))
    result = c.fetchone()
    
    if result:
        used, total, referrals, batch = result
        value = {
            'used': used,
            'total': total,
            'left': total - used,
            'referrals': referrals,
            'batch': batch
        }
        db_cache[cache_key] = value
        return value
    else:
        c.execute("INSERT INTO users (user_id, total_credits, joined_date) VALUES (?, ?, ?)",
                 (user_id, FREE_CREDITS, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
        value = {'used': 0, 'total': FREE_CREDITS, 'left': FREE_CREDITS, 'referrals': 0, 'batch': 'free'}
        db_cache[cache_key] = value
        return value

def use_credit(user_id):
    if user_id == OWNER_ID or is_admin_user(user_id):
        return True
    if is_user_banned(user_id):
        return False
    if credit_system_cache == 'false':
        return True
    credits = get_user_credits(user_id)
    if credits['left'] > 0:
        c.execute("UPDATE users SET credits_used = credits_used + 1 WHERE user_id = ?", (user_id,))
        conn.commit()
        db_cache.pop(f"credits_{user_id}", None)  # Clear cache
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
    db_cache.pop(f"credits_{referrer_id}", None)  # Clear cache
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
    db_cache.pop(f"credits_{user_id}", None)

def add_user_credits(user_id, amount):
    c.execute("UPDATE users SET total_credits = total_credits + ? WHERE user_id = ?", (amount, user_id))
    conn.commit()
    db_cache.pop(f"credits_{user_id}", None)

def remove_user_credits(user_id, amount):
    c.execute("UPDATE users SET total_credits = total_credits - ? WHERE user_id = ?", (amount, user_id))
    conn.commit()
    db_cache.pop(f"credits_{user_id}", None)

def reset_user_credits(user_id):
    c.execute("UPDATE users SET credits_used = 0, total_credits = ? WHERE user_id = ?", (FREE_CREDITS, user_id))
    conn.commit()
    db_cache.pop(f"credits_{user_id}", None)

def set_user_batch(user_id, batch_type):
    c.execute("UPDATE users SET batch_type = ? WHERE user_id = ?", (batch_type, user_id))
    if batch_type == 'premium':
        c.execute("UPDATE users SET total_credits = 50 WHERE user_id = ?", (user_id,))
    elif batch_type == 'star':
        c.execute("UPDATE users SET total_credits = 100 WHERE user_id = ?", (user_id,))
    elif batch_type == 'admin':
        c.execute("UPDATE users SET total_credits = 999999, is_admin = 1 WHERE user_id = ?", (user_id,))
    conn.commit()
    db_cache.pop(f"credits_{user_id}", None)
    db_cache.pop(f"admin_{user_id}", None)

def add_admin(user_id):
    set_user_batch(user_id, 'admin')

def remove_admin(user_id):
    if user_id != OWNER_ID:
        c.execute("UPDATE users SET is_admin = 0, batch_type = 'free', total_credits = ? WHERE user_id = ?", (FREE_CREDITS, user_id))
        conn.commit()
        db_cache.pop(f"admin_{user_id}", None)
        db_cache.pop(f"credits_{user_id}", None)

def block_admin(user_id, blocked_by, reason="No reason"):
    if user_id != OWNER_ID:
        c.execute("UPDATE users SET is_admin = 0, is_banned = 1, batch_type = 'banned' WHERE user_id = ?", (user_id,))
        c.execute("INSERT OR REPLACE INTO banned_users VALUES (?, ?, ?, ?)",
                  (user_id, blocked_by, reason, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
        db_cache.pop(f"admin_{user_id}", None)
        db_cache.pop(f"banned_{user_id}", None)
        db_cache.pop(f"credits_{user_id}", None)

def set_admin_limit(user_id, limit):
    if user_id != OWNER_ID:
        c.execute("UPDATE users SET total_credits = ? WHERE user_id = ?", (limit, user_id))
        conn.commit()
        db_cache.pop(f"credits_{user_id}", None)

def ban_user(user_id, banned_by, reason="No reason"):
    c.execute("INSERT OR REPLACE INTO banned_users VALUES (?, ?, ?, ?)",
              (user_id, banned_by, reason, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    c.execute("UPDATE users SET is_banned = 1 WHERE user_id = ?", (user_id,))
    conn.commit()
    db_cache.pop(f"banned_{user_id}", None)
    db_cache.pop(f"credits_{user_id}", None)

def unban_user(user_id):
    c.execute("DELETE FROM banned_users WHERE user_id = ?", (user_id,))
    c.execute("UPDATE users SET is_banned = 0 WHERE user_id = ?", (user_id,))
    conn.commit()
    db_cache.pop(f"banned_{user_id}", None)
    db_cache.pop(f"credits_{user_id}", None)

# ==================== BOT INIT ====================
bot = telebot.TeleBot(BOT_TOKEN)

# Track verification state
user_verified_state = {}
user_last_messages = {}

def cleanup_previous_messages(chat_id, user_id, keep_message_ids=None):
    """Delete previous messages except the ones to keep"""
    if user_id in user_last_messages:
        for msg_id in user_last_messages[user_id]:
            if keep_message_ids and msg_id in keep_message_ids:
                continue
            try:
                bot.delete_message(chat_id, msg_id)
            except:
                pass
    user_last_messages[user_id] = keep_message_ids if keep_message_ids else []

def track_message(user_id, message_id):
    if user_id not in user_last_messages:
        user_last_messages[user_id] = []
    user_last_messages[user_id].append(message_id)
    if len(user_last_messages[user_id]) > 10:
        user_last_messages[user_id] = user_last_messages[user_id][-10:]

# ==================== ULTRA FAST CHECK MEMBERSHIP ====================
def check_membership(user_id):
    if join_check_cache == 'false':
        return True
    try:
        # Ultra fast parallel checks
        def check_group():
            try:
                return bot.get_chat_member(GROUP_ID, user_id).status in ['member', 'administrator', 'creator']
            except:
                return False
        def check_channel():
            try:
                return bot.get_chat_member(CHANNEL_ID, user_id).status in ['member', 'administrator', 'creator']
            except:
                return False
        future_group = executor.submit(check_group)
        future_channel = executor.submit(check_channel)
        group_ok = future_group.result(timeout=1)
        channel_ok = future_channel.result(timeout=1)
        return group_ok and channel_ok
    except:
        return False

def is_user_verified(user_id):
    if user_id in user_verified_state:
        return user_verified_state[user_id]
    c.execute("SELECT verified FROM users WHERE user_id = ?", (user_id,))
    result = c.fetchone()
    value = result and result[0] == 1
    user_verified_state[user_id] = value
    return value

def mark_user_verified(user_id):
    c.execute("UPDATE users SET verified = 1 WHERE user_id = ?", (user_id,))
    conn.commit()
    user_verified_state[user_id] = True

# ==================== ULTRA FAST API FUNCTION - NO FILTERING ====================
def fetch_data(endpoint, query):
    try:
        # Direct API call - no caching for speed
        url = f"{API_BASE_URL}/{endpoint}?key={API_KEY}&num={query}"
        response = requests.get(url, timeout=API_TIMEOUT)
        
        if response.status_code != 200:
            return f"**{BRAND}**\n\n❌ **Error {response.status_code}**"
        
        # Return raw data exactly as received
        data = response.json()
        formatted = json.dumps(data, indent=2, ensure_ascii=False)
        return f"**{BRAND}**\n\n```json\n{formatted}\n```"
        
    except requests.exceptions.Timeout:
        return f"**{BRAND}**\n\n❌ **Timeout**"
    except Exception as e:
        return f"**{BRAND}**\n\n❌ **Error**"

# ==================== API COMMANDS LIST ====================
API_COMMANDS = {
    'num': '📱 Phone Number',
    'insta': '📸 Instagram',
    'rto': '🚗 RTO Details',
    'ff': '🎮 Free Fire',
    'ip': '🌐 IP Location',
    'pan': '💳 PAN Card',
    'ifsc': '🏦 IFSC Code',
    'aadhar': '🆔 Aadhar',
    'vehicle': '🚘 Vehicle',
    'mail': '📧 Email'
}

# ==================== MESSAGES ====================

HELP_MESSAGE = f"""
╔══════════════════════════════╗
║     🌀 𝐇𝐄𝐋𝐏 𝐌𝐄𝐍𝐔 🌀       ║
╠══════════════════════════════╣
║   {BRAND}                    ║
╠══════════════════════════════╣
║   📌 𝐁𝐀𝐒𝐈𝐂 𝐂𝐎𝐌𝐌𝐀𝐍𝐃𝐒:      ║
║   ━━━━━━━━━━━━━━━━━━━━━       ║
║   /start - 𝐒𝐭𝐚𝐫𝐭 𝐁𝐨𝐭       ║
║   /help - 𝐓𝐡𝐢𝐬 𝐌𝐞𝐧𝐮        ║
║   /profile - 𝐘𝐨𝐮𝐫 𝐒𝐭𝐚𝐭𝐬    ║
║   /share - 𝐑𝐞𝐟𝐞𝐫𝐫𝐚𝐥 𝐋𝐢𝐧𝐤   ║
║   /verify - 𝐕𝐞𝐫𝐢𝐟𝐲 𝐌𝐞𝐦𝐛𝐞𝐫  ║
║   /admins - 𝐂𝐨𝐧𝐭𝐚𝐜𝐭 𝐓𝐞𝐚𝐦   ║
╠══════════════════════════════╣
║   🔍 𝐈𝐍𝐅𝐎 𝐂𝐎𝐌𝐌𝐀𝐍𝐃𝐒:       ║
║   ━━━━━━━━━━━━━━━━━━━━━       ║
"""

for cmd, desc in API_COMMANDS.items():
    HELP_MESSAGE += f"║   /{cmd} [value] - {desc}\n"

HELP_MESSAGE += f"""
╠══════════════════════════════╣
║   💡 𝐄𝐱𝐚𝐦𝐩𝐥𝐞𝐬:              ║
║   /num 9876543210           ║
║   /insta virat.kohli        ║
║   /aadhar 123456789012      ║
╠══════════════════════════════╣
║   ⚡ 𝐅𝐫𝐞𝐞: {FREE_CREDITS} 𝐂𝐫𝐞𝐝𝐢𝐭𝐬  ║
║   🔥 𝐑𝐞𝐟𝐞𝐫 {REFERRALS_NEEDED} = +{REFERRAL_BONUS} ║
║   👑 {BRAND}                  ║
╚══════════════════════════════╝
"""

WELCOME_CAPTION = f"""
╔══════════════════════════════╗
║     🌀 𝐖𝐄𝐋𝐂𝐎𝐌𝐄 𝐓𝐎 𝐁𝐎𝐓 🌀  ║
╠══════════════════════════════╣
║   {BRAND}                    ║
╠══════════════════════════════╣
║   ✅ 𝐕𝐄𝐑𝐈𝐅𝐈𝐂𝐀𝐓𝐈𝐎𝐍 𝐒𝐔𝐂𝐂𝐄𝐒𝐒 ║
║   ━━━━━━━━━━━━━━━━━━━━━       ║
║   ✨ 𝐘𝐨𝐮 𝐜𝐚𝐧 𝐧𝐨𝐰 𝐮𝐬𝐞 𝐭𝐡𝐞 𝐛𝐨𝐭! ║
║   ⚡ 𝐅𝐫𝐞𝐞: {FREE_CREDITS} 𝐂𝐫𝐞𝐝𝐢𝐭𝐬    ║
║   📌 𝐔𝐬𝐞 /help 𝐟𝐨𝐫 𝐜𝐨𝐦𝐦𝐚𝐧𝐝𝐬   ║
║   👑 {BRAND}                  ║
╚══════════════════════════════╝
"""

def get_awesome_start(first_name, user_id, credits):
    batch = credits['batch']
    if batch == 'owner':
        title = "👑 𝐎𝐖𝐍𝐄𝐑 👑"
        color = "🔥"
    elif batch == 'admin':
        title = "👥 𝐀𝐃𝐌𝐈𝐍 👥"
        color = "⚡"
    elif batch == 'star':
        title = "⭐ 𝐒𝐓𝐀𝐑 ⭐"
        color = "✨"
    elif batch == 'premium':
        title = "💎 𝐏𝐑𝐄𝐌𝐈𝐔𝐌 💎"
        color = "💜"
    else:
        title = "👤 𝐅𝐑𝐄𝐄 𝐔𝐒𝐄𝐑 👤"
        color = "💚"
    
    cmd_list = ""
    cmds = list(API_COMMANDS.items())
    for i in range(0, len(cmds), 2):
        cmd1, desc1 = cmds[i]
        if i+1 < len(cmds):
            cmd2, desc2 = cmds[i+1]
            cmd_list += f"║   /{cmd1:<8} {desc1:<12}  /{cmd2:<8} {desc2}\n"
        else:
            cmd_list += f"║   /{cmd1:<8} {desc1}\n"
    
    start_style = f"""
╔══════════════════════════════════════╗
║     🌀 𝐓𝐀𝐓𝐒𝐔𝐌𝐀𝐊𝐈 𝐁𝐎𝐓 🌀     ║
╠══════════════════════════════════════╣
║        ✨ 𝐖𝐄𝐋𝐂𝐎𝐌𝐄 ✨         ║
║   ━━━━━━━━━━━━━━━━━━━━━━━━━   ║
║                                  ║
║   👋 𝐇𝐞𝐥𝐥𝐨, {first_name}!  ║
║   {color} {title}              ║
║                                  ║
║   🆔 𝐔𝐬𝐞𝐫 𝐈𝐃: {user_id}       ║
║   💰 𝐂𝐫𝐞𝐝𝐢𝐭𝐬: {credits['left']}/{credits['total']}      ║
║                                  ║
╠══════════════════════════════════════╣
║     ⚡ 𝐖𝐇𝐀𝐓 𝐈 𝐂𝐀𝐍 𝐃𝐎 ⚡     ║
║   ━━━━━━━━━━━━━━━━━━━━━━━━━   ║
║                                  ║
{cmd_list}
║                                  ║
╠══════════════════════════════════════╣
║     🔥 𝐔𝐒𝐄𝐅𝐔𝐋 𝐂𝐎𝐌𝐌𝐀𝐍𝐃𝐒 🔥   ║
║   ━━━━━━━━━━━━━━━━━━━━━━━━━   ║
║                                  ║
║   📌 /profile  - 𝐘𝐨𝐮𝐫 𝐒𝐭𝐚𝐭𝐬  ║
║   📌 /share    - 𝐆𝐞𝐭 𝐋𝐢𝐧𝐤    ║
║   📌 /help     - 𝐀𝐥𝐥 𝐂𝐦𝐝𝐬    ║
║   📌 /admins   - 𝐂𝐨𝐧𝐭𝐚𝐜𝐭     ║
║                                  ║
╠══════════════════════════════════════╣
║   💡 𝐅𝐫𝐞𝐞: {FREE_CREDITS} 𝐂𝐫𝐞𝐝𝐢𝐭𝐬     ║
║   🔥 𝐑𝐞𝐟𝐞𝐫 {REFERRALS_NEEDED} = +{REFERRAL_BONUS}    ║
║   👑 {BRAND}                 ║
╚══════════════════════════════════════╝
"""
    return start_style

# ==================== ULTRA FAST START COMMAND ====================
@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    first_name = message.from_user.first_name or "User"
    
    # Ultra fast response - no cleanup for speed
    
    if is_user_banned(user_id) and user_id != OWNER_ID:
        bot.reply_to(message, "🚫 𝐁𝐚𝐧𝐧𝐞𝐝!", parse_mode="Markdown")
        return
    
    # Check for referral (async)
    args = message.text.split()
    if len(args) > 1 and args[1].startswith('ref_'):
        try:
            referrer_id = int(args[1].replace('ref_', ''))
            if referrer_id != user_id:
                executor.submit(add_referral, referrer_id, user_id)
        except:
            pass
    
    credits = get_user_credits(user_id)
    
    # If already verified, send welcome video + start message
    if is_user_verified(user_id):
        try:
            bot.send_video(chat_id, WELCOME_VIDEO, caption="🎬 **𝐖𝐞𝐥𝐜𝐨𝐦𝐞 𝐁𝐚𝐜𝐤!**", parse_mode="Markdown", supports_streaming=True, timeout=2)
            start_text = get_awesome_start(first_name, user_id, credits)
            bot.send_message(chat_id, start_text, parse_mode="Markdown")
        except:
            start_text = get_awesome_start(first_name, user_id, credits)
            bot.send_message(chat_id, start_text, parse_mode="Markdown")
        return
    
    # New user - show image
    try:
        bot.send_photo(chat_id, START_IMAGE, caption="🌀 **𝐓𝐀𝐓𝐒𝐔𝐌𝐀𝐊𝐈**", parse_mode="Markdown")
    except:
        pass
    
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("📢 𝐉𝐨𝐢𝐧 𝐆𝐫𝐨𝐮𝐩", url=GROUP_LINK),
        InlineKeyboardButton("📣 𝐉𝐨𝐢𝐧 𝐂𝐡𝐚𝐧𝐧𝐞𝐥", url=CHANNEL_LINK)
    )
    markup.add(InlineKeyboardButton("✅ 𝐕𝐞𝐫𝐢𝐟𝐲", callback_data="verify"))
    
    bot.send_message(
        chat_id,
        f"👋 **𝐇𝐞𝐥𝐥𝐨 {first_name}!**\n\n🔒 **𝐌𝐞𝐦𝐛𝐞𝐫𝐬𝐡𝐢𝐩 𝐑𝐞𝐪𝐮𝐢𝐫𝐞𝐝**\n\n1️⃣ 𝐉𝐨𝐢𝐧 𝐆𝐫𝐨𝐮𝐩 & 𝐂𝐡𝐚𝐧𝐧𝐞𝐥\n2️⃣ 𝐂𝐥𝐢𝐜𝐤 𝐕𝐞𝐫𝐢𝐟𝐲",
        reply_markup=markup,
        parse_mode="Markdown"
    )

# ==================== VERIFY CALLBACK ====================
@bot.callback_query_handler(func=lambda call: call.data == "verify")
def verify_callback(call):
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    first_name = call.from_user.first_name or "User"
    
    # Delete verification message
    try:
        bot.delete_message(chat_id, call.message.message_id)
    except:
        pass
    
    if check_membership(user_id):
        mark_user_verified(user_id)
        credits = get_user_credits(user_id)
        
        # Send welcome video
        try:
            bot.send_video(chat_id, WELCOME_VIDEO, caption="🎬 **𝐖𝐞𝐥𝐜𝐨𝐦𝐞!**", parse_mode="Markdown", supports_streaming=True, timeout=2)
        except:
            pass
        
        # Send start message
        start_text = get_awesome_start(first_name, user_id, credits)
        bot.send_message(chat_id, start_text, parse_mode="Markdown")
        
        bot.answer_callback_query(call.id, "✅ 𝐕𝐞𝐫𝐢𝐟𝐢𝐞𝐝!")
    else:
        markup = InlineKeyboardMarkup(row_width=2)
        markup.add(
            InlineKeyboardButton("📢 𝐉𝐨𝐢𝐧", url=GROUP_LINK),
            InlineKeyboardButton("📣 𝐉𝐨𝐢𝐧", url=CHANNEL_LINK)
        )
        markup.add(InlineKeyboardButton("✅ 𝐓𝐫𝐲 𝐀𝐠𝐚𝐢𝐧", callback_data="verify"))
        
        bot.send_message(
            chat_id,
            "❌ **𝐍𝐨𝐭 𝐚 𝐦𝐞𝐦𝐛𝐞𝐫!**\n\n𝐏𝐥𝐞𝐚𝐬𝐞 𝐣𝐨𝐢𝐧 𝐛𝐨𝐭𝐡 𝐠𝐫𝐨𝐮𝐩 & 𝐜𝐡𝐚𝐧𝐧𝐞𝐥.",
            reply_markup=markup,
            parse_mode="Markdown"
        )
        bot.answer_callback_query(call.id, "❌ 𝐅𝐚𝐢𝐥𝐞𝐝")

# ==================== HELP COMMAND ====================
@bot.message_handler(commands=['help'])
def help_command(message):
    bot.reply_to(message, HELP_MESSAGE, parse_mode="Markdown")

# ==================== PROFILE COMMAND ====================
@bot.message_handler(commands=['profile'])
def profile_command(message):
    user_id = message.from_user.id
    
    if is_user_banned(user_id) and user_id != OWNER_ID:
        bot.reply_to(message, "🚫 𝐁𝐚𝐧𝐧𝐞𝐝!", parse_mode="Markdown")
        return
    
    credits = get_user_credits(user_id)
    next_bonus = REFERRALS_NEEDED - (credits['referrals'] % REFERRALS_NEEDED)
    if next_bonus == REFERRALS_NEEDED:
        next_bonus = 0
    
    profile_msg = f"""
╔══════════════════════════════╗
║     📊 𝐏𝐑𝐎𝐅𝐈𝐋𝐄 📊         ║
╠══════════════════════════════╣
║   {BRAND}                    ║
╠══════════════════════════════╣
║   👤 𝐈𝐃: {user_id}           ║
║   🏷️ 𝐁𝐚𝐭𝐜𝐡: {credits['batch'].upper()} ║
╠══════════════════════════════╣
║   💰 𝐂𝐑𝐄𝐃𝐈𝐓𝐒:               ║
║   ━━━━━━━━━━━━━━━━━━━━━       ║
║   📊 𝐔𝐬𝐞𝐝: {credits['used']}/{credits['total']}  ║
║   💎 𝐋𝐞𝐟𝐭: {credits['left']}           ║
║                               ║
║   👥 𝐑𝐞𝐟𝐞𝐫𝐫𝐚𝐥𝐬: {credits['referrals']}   ║
║   🔥 𝐍𝐞𝐱𝐭: {next_bonus} 𝐦𝐨𝐫𝐞      ║
╠══════════════════════════════╣
║   🔗 /share - 𝐆𝐞𝐭 𝐋𝐢𝐧𝐤      ║
║   👑 {BRAND}                  ║
╚══════════════════════════════╝
"""
    bot.reply_to(message, profile_msg, parse_mode="Markdown")

# ==================== SHARE COMMAND ====================
@bot.message_handler(commands=['share'])
def share_command(message):
    user_id = message.from_user.id
    
    if is_user_banned(user_id) and user_id != OWNER_ID:
        bot.reply_to(message, "🚫 𝐁𝐚𝐧𝐧𝐞𝐝!", parse_mode="Markdown")
        return
    
    bot_username = bot.get_me().username
    referral_link = f"https://t.me/{bot_username}?start=ref_{user_id}"
    credits = get_user_credits(user_id)
    next_bonus = REFERRALS_NEEDED - (credits['referrals'] % REFERRALS_NEEDED)
    
    share_msg = f"""
╔══════════════════════════════╗
║     🔗 𝐑𝐄𝐅𝐄𝐑𝐑𝐀𝐋 𝐋𝐈𝐍𝐊     ║
╠══════════════════════════════╣
║   {BRAND}                    ║
╠══════════════════════════════╣
║   👥 𝐑𝐞𝐟𝐞𝐫𝐫𝐚𝐥𝐬: {credits['referrals']}   ║
║   🔥 𝐍𝐞𝐞𝐝 {next_bonus} 𝐦𝐨𝐫𝐞    ║
║   ✨ +{REFERRAL_BONUS} 𝐂𝐫𝐞𝐝𝐢𝐭𝐬    ║
╠══════════════════════════════╣
║   `{referral_link}`          ║
╠══════════════════════════════╣
║   📤 𝐒𝐡𝐚𝐫𝐞 & 𝐄𝐚𝐫𝐧!         ║
╚══════════════════════════════╝
"""
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("📤 𝐒𝐡𝐚𝐫𝐞", switch_inline_query=f"Join {BRAND} Bot! {referral_link}"))
    
    bot.reply_to(message, share_msg, parse_mode="Markdown", reply_markup=markup)

# ==================== ADMINS COMMAND ====================
@bot.message_handler(commands=['admins'])
def admins_command(message):
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("👑 𝐂𝐨𝐧𝐭𝐚𝐜𝐭 𝐎𝐰𝐧𝐞𝐫", url=f"tg://user?id={OWNER_ID}"))
    
    msg_text = f"""
╔══════════════════════════════╗
║     👑 𝐂𝐎𝐍𝐓𝐀𝐂𝐓 𝐓𝐄𝐀𝐌 👑   ║
╠══════════════════════════════╣
║   {BRAND}                    ║
╠══════════════════════════════╣
║   𝐎𝐰𝐧𝐞𝐫 𝐈𝐃: {OWNER_ID}      ║
╠══════════════════════════════╣
║   𝐂𝐥𝐢𝐜𝐤 𝐛𝐞𝐥𝐨𝐰 𝐭𝐨 𝐦𝐞𝐬𝐬𝐚𝐠𝐞   ║
╚══════════════════════════════╝
"""
    bot.reply_to(message, msg_text, parse_mode="Markdown", reply_markup=markup)

# ==================== VERIFY COMMAND ====================
@bot.message_handler(commands=['verify'])
def verify_command(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    first_name = message.from_user.first_name or "User"
    
    if is_user_banned(user_id) and user_id != OWNER_ID:
        bot.reply_to(message, "🚫 𝐁𝐚𝐧𝐧𝐞𝐝!", parse_mode="Markdown")
        return
    
    if check_membership(user_id):
        mark_user_verified(user_id)
        credits = get_user_credits(user_id)
        
        try:
            bot.send_video(chat_id, WELCOME_VIDEO, caption="🎬 **𝐖𝐞𝐥𝐜𝐨𝐦𝐞!**", parse_mode="Markdown", supports_streaming=True, timeout=2)
        except:
            pass
        
        start_text = get_awesome_start(first_name, user_id, credits)
        bot.send_message(chat_id, start_text, parse_mode="Markdown")
    else:
        markup = InlineKeyboardMarkup()
        markup.add(
            InlineKeyboardButton("📢 𝐉𝐨𝐢𝐧", url=GROUP_LINK),
            InlineKeyboardButton("📣 𝐉𝐨𝐢𝐧", url=CHANNEL_LINK)
        )
        bot.reply_to(
            message,
            "❌ **𝐍𝐨𝐭 𝐚 𝐦𝐞𝐦𝐛𝐞𝐫!**\n\n𝐏𝐥𝐞𝐚𝐬𝐞 𝐣𝐨𝐢𝐧 𝐟𝐢𝐫𝐬𝐭.",
            reply_markup=markup,
            parse_mode="Markdown"
        )

# ==================== ULTRA FAST INFO COMMANDS ====================
@bot.message_handler(commands=list(API_COMMANDS.keys()))
def info_commands(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    # Ultra fast checks
    if is_user_banned(user_id) and user_id != OWNER_ID:
        bot.reply_to(message, "🚫 𝐁𝐚𝐧𝐧𝐞𝐝!", parse_mode="Markdown")
        return
    
    if not is_user_verified(user_id):
        if not check_membership(user_id):
            markup = InlineKeyboardMarkup()
            markup.add(
                InlineKeyboardButton("📢 𝐉𝐨𝐢𝐧", url=GROUP_LINK),
                InlineKeyboardButton("📣 𝐉𝐨𝐢𝐧", url=CHANNEL_LINK)
            )
            bot.reply_to(message, "❌ 𝐉𝐨𝐢𝐧 𝐟𝐢𝐫𝐬𝐭!", reply_markup=markup)
            return
        else:
            mark_user_verified(user_id)
    
    credits = get_user_credits(user_id)
    if credits['left'] <= 0 and user_id != OWNER_ID and not is_admin_user(user_id):
        bot_username = bot.get_me().username
        referral_link = f"https://t.me/{bot_username}?start=ref_{user_id}"
        bot.reply_to(
            message,
            f"❌ 𝐍𝐨 𝐜𝐫𝐞𝐝𝐢𝐭𝐬!\n/share\n{referral_link}",
            parse_mode="Markdown"
        )
        return
    
    cmd = message.text.split()[0][1:]
    args = message.text.split()[1] if len(message.text.split()) > 1 else None
    
    if not args:
        bot.reply_to(message, f"❌ /{cmd} [𝐯𝐚𝐥𝐮𝐞]")
        return
    
    # Ultra fast - direct API call
    result = fetch_data(cmd, args)
    
    if user_id != OWNER_ID and not is_admin_user(user_id):
        use_credit(user_id)
        credits = get_user_credits(user_id)
        result += f"\n\n⚡ 𝐋𝐞𝐟𝐭: {credits['left']}"
    
    bot.reply_to(message, result, parse_mode="Markdown")

# ==================== USER MANAGEMENT COMMANDS ====================

@bot.message_handler(commands=['ban'])
def ban_command(message):
    user_id = message.from_user.id
    
    if not is_admin_user(user_id):
        bot.reply_to(message, "❌ 𝐀𝐝𝐦𝐢𝐧 𝐨𝐧𝐥𝐲!")
        return
    
    args = message.text.split()
    if len(args) < 2:
        bot.reply_to(message, "𝐔𝐬𝐚𝐠𝐞: /ban [𝐢𝐝] [𝐫𝐞𝐚𝐬𝐨𝐧]")
        return
    
    try:
        target = int(args[1])
        reason = " ".join(args[2:]) if len(args) > 2 else "No reason"
        
        if target == OWNER_ID:
            bot.reply_to(message, "❌ 𝐂𝐚𝐧'𝐭 𝐛𝐚𝐧 𝐨𝐰𝐧𝐞𝐫!")
            return
        
        ban_user(target, user_id, reason)
        bot.reply_to(message, f"✅ 𝐁𝐚𝐧𝐧𝐞𝐝 `{target}`!\n𝐑𝐞𝐚𝐬𝐨𝐧: {reason}", parse_mode="Markdown")
    except:
        bot.reply_to(message, "❌ 𝐈𝐧𝐯𝐚𝐥𝐢𝐝 𝐈𝐃!")

@bot.message_handler(commands=['unban'])
def unban_command(message):
    user_id = message.from_user.id
    
    if not is_admin_user(user_id):
        bot.reply_to(message, "❌ 𝐀𝐝𝐦𝐢𝐧 𝐨𝐧𝐥𝐲!")
        return
    
    args = message.text.split()
    if len(args) < 2:
        bot.reply_to(message, "𝐔𝐬𝐚𝐠𝐞: /unban [𝐢𝐝]")
        return
    
    try:
        target = int(args[1])
        unban_user(target)
        bot.reply_to(message, f"✅ 𝐔𝐧𝐛𝐚𝐧𝐧𝐞𝐝 `{target}`!", parse_mode="Markdown")
    except:
        bot.reply_to(message, "❌ 𝐈𝐧𝐯𝐚𝐥𝐢𝐝 𝐈𝐃!")

@bot.message_handler(commands=['userinfo'])
def userinfo_command(message):
    user_id = message.from_user.id
    
    if not is_admin_user(user_id):
        bot.reply_to(message, "❌ 𝐀𝐝𝐦𝐢𝐧 𝐨𝐧𝐥𝐲!")
        return
    
    args = message.text.split()
    if len(args) < 2:
        bot.reply_to(message, "𝐔𝐬𝐚𝐠𝐞: /userinfo [𝐢𝐝]")
        return
    
    try:
        target = int(args[1])
        credits = get_user_credits(target)
        
        info_msg = f"""
📊 **𝐔𝐒𝐄𝐑 𝐈𝐍𝐅𝐎**
━━━━━━━━━━━━━━━━
🆔 𝐈𝐃: {target}
🏷️ 𝐁𝐚𝐭𝐜𝐡: {credits['batch'].upper()}
👑 𝐀𝐝𝐦𝐢𝐧: {'𝐘𝐞𝐬' if is_admin_user(target) else '𝐍𝐨'}
🔴 𝐁𝐚𝐧𝐧𝐞𝐝: {'𝐘𝐞𝐬' if is_user_banned(target) else '𝐍𝐨'}
💰 𝐂𝐫𝐞𝐝𝐢𝐭𝐬: {credits['used']}/{credits['total']}
👥 𝐑𝐞𝐟𝐞𝐫𝐫𝐚𝐥𝐬: {credits['referrals']}
"""
        bot.reply_to(message, info_msg, parse_mode="Markdown")
    except:
        bot.reply_to(message, "❌ 𝐈𝐧𝐯𝐚𝐥𝐢𝐝 𝐈𝐃!")

# ==================== ADMIN MANAGEMENT COMMANDS ====================

@bot.message_handler(commands=['addadmin'])
def addadmin_command(message):
    user_id = message.from_user.id
    
    if not is_admin_user(user_id):
        bot.reply_to(message, "❌ 𝐀𝐝𝐦𝐢𝐧 𝐨𝐧𝐥𝐲!")
        return
    
    args = message.text.split()
    if len(args) < 2:
        bot.reply_to(message, "𝐔𝐬𝐚𝐠𝐞: /addadmin [𝐢𝐝]")
        return
    
    try:
        target = int(args[1])
        if target == OWNER_ID:
            bot.reply_to(message, "❌ 𝐔𝐬𝐞𝐫 𝐢𝐬 𝐚𝐥𝐫𝐞𝐚𝐝𝐲 𝐨𝐰𝐧𝐞𝐫!")
            return
        add_admin(target)
        bot.reply_to(message, f"✅ 𝐔𝐬𝐞𝐫 `{target}` 𝐢𝐬 𝐧𝐨𝐰 𝐀𝐃𝐌𝐈𝐍!", parse_mode="Markdown")
    except:
        bot.reply_to(message, "❌ 𝐈𝐧𝐯𝐚𝐥𝐢𝐝 𝐈𝐃!")

@bot.message_handler(commands=['removeadmin'])
def removeadmin_command(message):
    user_id = message.from_user.id
    
    if not is_admin_user(user_id):
        bot.reply_to(message, "❌ 𝐀𝐝𝐦𝐢𝐧 𝐨𝐧𝐥𝐲!")
        return
    
    args = message.text.split()
    if len(args) < 2:
        bot.reply_to(message, "𝐔𝐬𝐚𝐠𝐞: /removeadmin [𝐢𝐝]")
        return
    
    try:
        target = int(args[1])
        if target == OWNER_ID:
            bot.reply_to(message, "❌ 𝐂𝐚𝐧𝐧𝐨𝐭 𝐫𝐞𝐦𝐨𝐯𝐞 𝐨𝐰𝐧𝐞𝐫!")
            return
        remove_admin(target)
        bot.reply_to(message, f"✅ 𝐔𝐬𝐞𝐫 `{target}` 𝐢𝐬 𝐧𝐨 𝐥𝐨𝐧𝐠𝐞𝐫 𝐚𝐝𝐦𝐢𝐧!", parse_mode="Markdown")
    except:
        bot.reply_to(message, "❌ 𝐈𝐧𝐯𝐚𝐥𝐢𝐝 𝐈𝐃!")

@bot.message_handler(commands=['blockadmin'])
def blockadmin_command(message):
    user_id = message.from_user.id
    
    if not is_admin_user(user_id):
        bot.reply_to(message, "❌ 𝐀𝐝𝐦𝐢𝐧 𝐨𝐧𝐥𝐲!")
        return
    
    args = message.text.split()
    if len(args) < 2:
        bot.reply_to(message, "𝐔𝐬𝐚𝐠𝐞: /blockadmin [𝐢𝐝] [𝐫𝐞𝐚𝐬𝐨𝐧]")
        return
    
    try:
        target = int(args[1])
        reason = " ".join(args[2:]) if len(args) > 2 else "Admin blocked"
        
        if target == OWNER_ID:
            bot.reply_to(message, "❌ 𝐂𝐚𝐧𝐧𝐨𝐭 𝐛𝐥𝐨𝐜𝐤 𝐨𝐰𝐧𝐞𝐫!")
            return
        
        block_admin(target, user_id, reason)
        bot.reply_to(message, f"✅ 𝐀𝐝𝐦𝐢𝐧 `{target}` 𝐛𝐥𝐨𝐜𝐤𝐞𝐝!\n𝐑𝐞𝐚𝐬𝐨𝐧: {reason}", parse_mode="Markdown")
    except:
        bot.reply_to(message, "❌ 𝐈𝐧𝐯𝐚𝐥𝐢𝐝 𝐈𝐃!")

@bot.message_handler(commands=['setadminlimit'])
def setadminlimit_command(message):
    user_id = message.from_user.id
    
    if not is_admin_user(user_id):
        bot.reply_to(message, "❌ 𝐀𝐝𝐦𝐢𝐧 𝐨𝐧𝐥𝐲!")
        return
    
    args = message.text.split()
    if len(args) < 3:
        bot.reply_to(message, "𝐔𝐬𝐚𝐠𝐞: /setadminlimit [𝐚𝐝𝐦𝐢𝐧_𝐢𝐝] [𝐥𝐢𝐦𝐢𝐭]")
        return
    
    try:
        target = int(args[1])
        limit = int(args[2])
        
        if target == OWNER_ID:
            bot.reply_to(message, "❌ 𝐂𝐚𝐧𝐧𝐨𝐭 𝐬𝐞𝐭 𝐥𝐢𝐦𝐢𝐭 𝐟𝐨𝐫 𝐨𝐰𝐧𝐞𝐫!")
            return
        
        set_admin_limit(target, limit)
        bot.reply_to(message, f"✅ 𝐀𝐝𝐦𝐢𝐧 `{target}` 𝐥𝐢𝐦𝐢𝐭 𝐬𝐞𝐭 𝐭𝐨 {limit}!", parse_mode="Markdown")
    except:
        bot.reply_to(message, "❌ 𝐈𝐧𝐯𝐚𝐥𝐢𝐝 𝐢𝐧𝐩𝐮𝐭!")

@bot.message_handler(commands=['adminlist'])
def adminlist_command(message):
    user_id = message.from_user.id
    
    if not is_admin_user(user_id):
        bot.reply_to(message, "❌ 𝐀𝐝𝐦𝐢𝐧 𝐨𝐧𝐥𝐲!")
        return
    
    c.execute("SELECT user_id FROM users WHERE is_admin = 1 OR is_owner = 1")
    admins = c.fetchall()
    
    msg_text = "👑 **𝐀𝐃𝐌𝐈𝐍 𝐓𝐄𝐀𝐌** 👑\n\n"
    markup = InlineKeyboardMarkup()
    
    for (admin_id,) in admins:
        role = "👑 𝐎𝐖𝐍𝐄𝐑" if admin_id == OWNER_ID else "👥 𝐀𝐃𝐌𝐈𝐍"
        msg_text += f"{role}: `{admin_id}`\n"
        if admin_id != OWNER_ID:
            markup.add(InlineKeyboardButton(f"📩 𝐌𝐞𝐬𝐬𝐚𝐠𝐞 {admin_id}", url=f"tg://user?id={admin_id}"))
    
    bot.reply_to(message, msg_text, parse_mode="Markdown", reply_markup=markup)

# ==================== CREDIT MANAGEMENT COMMANDS ====================

@bot.message_handler(commands=['setuserlimit'])
def setuserlimit_command(message):
    user_id = message.from_user.id
    
    if not is_admin_user(user_id):
        bot.reply_to(message, "❌ 𝐀𝐝𝐦𝐢𝐧 𝐨𝐧𝐥𝐲!")
        return
    
    args = message.text.split()
    if len(args) < 3:
        bot.reply_to(message, "𝐔𝐬𝐚𝐠𝐞: /setuserlimit [𝐮𝐬𝐞𝐫_𝐢𝐝] [𝐥𝐢𝐦𝐢𝐭]")
        return
    
    try:
        target = int(args[1])
        limit = int(args[2])
        set_user_credits(target, limit)
        bot.reply_to(message, f"✅ 𝐔𝐬𝐞𝐫 `{target}` 𝐥𝐢𝐦𝐢𝐭 𝐬𝐞𝐭 𝐭𝐨 {limit}!", parse_mode="Markdown")
    except:
        bot.reply_to(message, "❌ 𝐈𝐧𝐯𝐚𝐥𝐢𝐝 𝐢𝐧𝐩𝐮𝐭!")

@bot.message_handler(commands=['addcredits'])
def addcredits_command(message):
    user_id = message.from_user.id
    
    if not is_admin_user(user_id):
        bot.reply_to(message, "❌ 𝐀𝐝𝐦𝐢𝐧 𝐨𝐧𝐥𝐲!")
        return
    
    args = message.text.split()
    if len(args) < 3:
        bot.reply_to(message, "𝐔𝐬𝐚𝐠𝐞: /addcredits [𝐮𝐬𝐞𝐫_𝐢𝐝] [𝐚𝐦𝐨𝐮𝐧𝐭]")
        return
    
    try:
        target = int(args[1])
        amount = int(args[2])
        add_user_credits(target, amount)
        bot.reply_to(message, f"✅ 𝐀𝐝𝐝𝐞𝐝 {amount} 𝐜𝐫𝐞𝐝𝐢𝐭𝐬 𝐭𝐨 𝐮𝐬𝐞𝐫 `{target}`!", parse_mode="Markdown")
    except:
        bot.reply_to(message, "❌ 𝐈𝐧𝐯𝐚𝐥𝐢𝐝 𝐢𝐧𝐩𝐮𝐭!")

@bot.message_handler(commands=['removecredits'])
def removecredits_command(message):
    user_id = message.from_user.id
    
    if not is_admin_user(user_id):
        bot.reply_to(message, "❌ 𝐀𝐝𝐦𝐢𝐧 𝐨𝐧𝐥𝐲!")
        return
    
    args = message.text.split()
    if len(args) < 3:
        bot.reply_to(message, "𝐔𝐬𝐚𝐠𝐞: /removecredits [𝐮𝐬𝐞𝐫_𝐢𝐝] [𝐚𝐦𝐨𝐮𝐧𝐭]")
        return
    
    try:
        target = int(args[1])
        amount = int(args[2])
        remove_user_credits(target, amount)
        bot.reply_to(message, f"✅ 𝐑𝐞𝐦𝐨𝐯𝐞𝐝 {amount} 𝐜𝐫𝐞𝐝𝐢𝐭𝐬 𝐟𝐫𝐨𝐦 𝐮𝐬𝐞𝐫 `{target}`!", parse_mode="Markdown")
    except:
        bot.reply_to(message, "❌ 𝐈𝐧𝐯𝐚𝐥𝐢𝐝 𝐢𝐧𝐩𝐮𝐭!")

@bot.message_handler(commands=['resetcredits'])
def resetcredits_command(message):
    user_id = message.from_user.id
    
    if not is_admin_user(user_id):
        bot.reply_to(message, "❌ 𝐀𝐝𝐦𝐢𝐧 𝐨𝐧𝐥𝐲!")
        return
    
    args = message.text.split()
    if len(args) < 2:
        bot.reply_to(message, "𝐔𝐬𝐚𝐠𝐞: /resetcredits [𝐮𝐬𝐞𝐫_𝐢𝐝]")
        return
    
    try:
        target = int(args[1])
        reset_user_credits(target)
        bot.reply_to(message, f"✅ 𝐔𝐬𝐞𝐫 `{target}` 𝐜𝐫𝐞𝐝𝐢𝐭𝐬 𝐫𝐞𝐬𝐞𝐭 𝐭𝐨 {FREE_CREDITS}!", parse_mode="Markdown")
    except:
        bot.reply_to(message, "❌ 𝐈𝐧𝐯𝐚𝐥𝐢𝐝 𝐮𝐬𝐞𝐫 𝐈𝐃!")

# ==================== BATCH MANAGEMENT COMMANDS ====================

@bot.message_handler(commands=['givepremium'])
def givepremium_command(message):
    user_id = message.from_user.id
    
    if not is_admin_user(user_id):
        bot.reply_to(message, "❌ 𝐀𝐝𝐦𝐢𝐧 𝐨𝐧𝐥𝐲!")
        return
    
    args = message.text.split()
    if len(args) < 2:
        bot.reply_to(message, "𝐔𝐬𝐚𝐠𝐞: /givepremium [𝐮𝐬𝐞𝐫_𝐢𝐝]")
        return
    
    try:
        target = int(args[1])
        set_user_batch(target, 'premium')
        bot.reply_to(message, f"✅ 𝐔𝐬𝐞𝐫 `{target}` 𝐢𝐬 𝐧𝐨𝐰 𝐏𝐑𝐄𝐌𝐈𝐔𝐌!", parse_mode="Markdown")
    except:
        bot.reply_to(message, "❌ 𝐈𝐧𝐯𝐚𝐥𝐢𝐝 𝐮𝐬𝐞𝐫 𝐈𝐃!")

@bot.message_handler(commands=['givestar'])
def givestar_command(message):
    user_id = message.from_user.id
    
    if not is_admin_user(user_id):
        bot.reply_to(message, "❌ 𝐀𝐝𝐦𝐢𝐧 𝐨𝐧𝐥𝐲!")
        return
    
    args = message.text.split()
    if len(args) < 2:
        bot.reply_to(message, "𝐔𝐬𝐚𝐠𝐞: /givestar [𝐮𝐬𝐞𝐫_𝐢𝐝]")
        return
    
    try:
        target = int(args[1])
        set_user_batch(target, 'star')
        bot.reply_to(message, f"✅ 𝐔𝐬𝐞𝐫 `{target}` 𝐢𝐬 𝐧𝐨𝐰 𝐒𝐓𝐀𝐑!", parse_mode="Markdown")
    except:
        bot.reply_to(message, "❌ 𝐈𝐧𝐯𝐚𝐥𝐢𝐝 𝐮𝐬𝐞𝐫 𝐈𝐃!")

# ==================== LISTS COMMANDS ====================

@bot.message_handler(commands=['memberlist'])
def memberlist_command(message):
    user_id = message.from_user.id
    
    if not is_admin_user(user_id):
        bot.reply_to(message, "❌ 𝐀𝐝𝐦𝐢𝐧 𝐨𝐧𝐥𝐲!")
        return
    
    c.execute("SELECT COUNT(*) FROM users")
    total = c.fetchone()[0]
    
    c.execute("SELECT user_id, batch_type, is_banned FROM users ORDER BY joined_date DESC LIMIT 20")
    members = c.fetchall()
    
    msg_text = f"📋 **𝐌𝐄𝐌𝐁𝐄𝐑 𝐋𝐈𝐒𝐓** (𝐋𝐚𝐬𝐭 20)\n𝐓𝐨𝐭𝐚𝐥: {total}\n\n"
    for mid, batch, banned in members:
        emoji = "👑" if mid == OWNER_ID else "🔥" if batch == 'admin' else "⭐" if batch == 'star' else "💎" if batch == 'premium' else "👤"
        ban_emoji = "🔴" if banned else "🟢"
        msg_text += f"{ban_emoji} {emoji} `{mid}` - {batch}\n"
    
    bot.reply_to(message, msg_text, parse_mode="Markdown")

@bot.message_handler(commands=['premiumlist'])
def premiumlist_command(message):
    user_id = message.from_user.id
    
    if not is_admin_user(user_id):
        bot.reply_to(message, "❌ 𝐀𝐝𝐦𝐢𝐧 𝐨𝐧𝐥𝐲!")
        return
    
    c.execute("SELECT user_id FROM users WHERE batch_type IN ('premium', 'star', 'admin', 'owner')")
    premium = c.fetchall()
    
    if not premium:
        bot.reply_to(message, "📝 𝐍𝐨 𝐩𝐫𝐞𝐦𝐢𝐮𝐦 𝐦𝐞𝐦𝐛𝐞𝐫𝐬!")
        return
    
    msg_text = "💎 **𝐏𝐑𝐄𝐌𝐈𝐔𝐌 𝐌𝐄𝐌𝐁𝐄𝐑𝐒** 💎\n\n"
    for (pid,) in premium[:20]:
        msg_text += f"• `{pid}`\n"
    
    bot.reply_to(message, msg_text, parse_mode="Markdown")

@bot.message_handler(commands=['banlist'])
def banlist_command(message):
    user_id = message.from_user.id
    
    if not is_admin_user(user_id):
        bot.reply_to(message, "❌ 𝐀𝐝𝐦𝐢𝐧 𝐨𝐧𝐥𝐲!")
        return
    
    c.execute("SELECT user_id, ban_reason, ban_date FROM banned_users")
    banned = c.fetchall()
    
    if not banned:
        bot.reply_to(message, "📝 𝐍𝐨 𝐛𝐚𝐧𝐧𝐞𝐝 𝐮𝐬𝐞𝐫𝐬!")
        return
    
    msg_text = "🔨 **𝐁𝐀𝐍𝐍𝐄𝐃 𝐔𝐒𝐄𝐑𝐒** 🔨\n\n"
    for bid, reason, date in banned:
        msg_text += f"• `{bid}` - {reason}\n  📅 {date[:10]}\n\n"
    
    bot.reply_to(message, msg_text, parse_mode="Markdown")

# ==================== BOT SETTINGS COMMANDS ====================

@bot.message_handler(commands=['boton'])
def boton_command(message):
    user_id = message.from_user.id
    
    if not is_admin_user(user_id):
        bot.reply_to(message, "❌ 𝐀𝐝𝐦𝐢𝐧 𝐨𝐧𝐥𝐲!")
        return
    
    update_setting('bot_active', 'true', user_id)
    bot.reply_to(message, "🟢 **𝐁𝐨𝐭 𝐢𝐬 𝐧𝐨𝐰 𝐎𝐍!**", parse_mode="Markdown")

@bot.message_handler(commands=['botoff'])
def botoff_command(message):
    user_id = message.from_user.id
    
    if not is_admin_user(user_id):
        bot.reply_to(message, "❌ 𝐀𝐝𝐦𝐢𝐧 𝐨𝐧𝐥𝐲!")
        return
    
    update_setting('bot_active', 'false', user_id)
    bot.reply_to(message, "🔴 **𝐁𝐨𝐭 𝐢𝐬 𝐧𝐨𝐰 𝐎𝐅𝐅!**", parse_mode="Markdown")

@bot.message_handler(commands=['maintenance'])
def maintenance_command(message):
    user_id = message.from_user.id
    
    if not is_admin_user(user_id):
        bot.reply_to(message, "❌ 𝐀𝐝𝐦𝐢𝐧 𝐨𝐧𝐥𝐲!")
        return
    
    current = get_setting('maintenance')
    new_value = 'false' if current == 'true' else 'true'
    update_setting('maintenance', new_value, user_id)
    
    status = "𝐎𝐍" if new_value == 'true' else "𝐎𝐅𝐅"
    bot.reply_to(message, f"🛠️ **𝐌𝐚𝐢𝐧𝐭𝐞𝐧𝐚𝐧𝐜𝐞 𝐦𝐨𝐝𝐞 𝐢𝐬 𝐧𝐨𝐰 {status}!**", parse_mode="Markdown")

@bot.message_handler(commands=['togglejoin'])
def togglejoin_command(message):
    user_id = message.from_user.id
    
    if not is_admin_user(user_id):
        bot.reply_to(message, "❌ 𝐀𝐝𝐦𝐢𝐧 𝐨𝐧𝐥𝐲!")
        return
    
    current = get_setting('join_check')
    new_value = 'false' if current == 'true' else 'true'
    update_setting('join_check', new_value, user_id)
    
    status = "𝐎𝐅𝐅" if new_value == 'false' else "𝐎𝐍"
    bot.reply_to(message, f"🔒 **𝐉𝐨𝐢𝐧 𝐜𝐡𝐞𝐜𝐤 𝐢𝐬 𝐧𝐨𝐰 {status}!**", parse_mode="Markdown")

@bot.message_handler(commands=['togglecredits'])
def togglecredits_command(message):
    user_id = message.from_user.id
    
    if not is_admin_user(user_id):
        bot.reply_to(message, "❌ 𝐀𝐝𝐦𝐢𝐧 𝐨𝐧𝐥𝐲!")
        return
    
    current = get_setting('credit_system')
    new_value = 'false' if current == 'true' else 'true'
    update_setting('credit_system', new_value, user_id)
    
    status = "𝐎𝐅𝐅" if new_value == 'false' else "𝐎𝐍"
    bot.reply_to(message, f"💰 **𝐂𝐫𝐞𝐝𝐢𝐭 𝐬𝐲𝐬𝐭𝐞𝐦 𝐢𝐬 𝐧𝐨𝐰 {status}!**", parse_mode="Markdown")

@bot.message_handler(commands=['settings'])
def settings_command(message):
    user_id = message.from_user.id
    
    if not is_admin_user(user_id):
        bot.reply_to(message, "❌ 𝐀𝐝𝐦𝐢𝐧 𝐨𝐧𝐥𝐲!")
        return
    
    bot_active = get_setting('bot_active')
    maintenance = get_setting('maintenance')
    join_check = get_setting('join_check')
    credit_system = get_setting('credit_system')
    
    msg_text = f"""
⚙️ **𝐁𝐎𝐓 𝐒𝐄𝐓𝐓𝐈𝐍𝐆𝐒**
━━━━━━━━━━━━━━━━
🟢 𝐁𝐨𝐭 𝐀𝐜𝐭𝐢𝐯𝐞: {'𝐘𝐄𝐒' if bot_active == 'true' else '𝐍𝐎'}
🛠️ 𝐌𝐚𝐢𝐧𝐭𝐞𝐧𝐚𝐧𝐜𝐞: {'𝐘𝐄𝐒' if maintenance == 'true' else '𝐍𝐎'}
🔒 𝐉𝐨𝐢𝐧 𝐂𝐡𝐞𝐜𝐤: {'𝐘𝐄𝐒' if join_check == 'true' else '𝐍𝐎'}
💰 𝐂𝐫𝐞𝐝𝐢𝐭 𝐒𝐲𝐬𝐭𝐞𝐦: {'𝐘𝐄𝐒' if credit_system == 'true' else '𝐍𝐎'}

👑 𝐎𝐰𝐧𝐞𝐫: {OWNER_ID}
"""
    bot.reply_to(message, msg_text, parse_mode="Markdown")

# ==================== OWNER ONLY COMMANDS ====================

@bot.message_handler(commands=['broadcast'])
def broadcast_command(message):
    user_id = message.from_user.id
    
    if user_id != OWNER_ID:
        bot.reply_to(message, "❌ 𝐎𝐧𝐥𝐲 𝐨𝐰𝐧𝐞𝐫 𝐜𝐚𝐧 𝐮𝐬𝐞 𝐭𝐡𝐢𝐬!")
        return
    
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        bot.reply_to(message, "𝐔𝐬𝐚𝐠𝐞: /broadcast [𝐦𝐞𝐬𝐬𝐚𝐠𝐞]")
        return
    
    broadcast_msg = args[1]
    c.execute("SELECT user_id FROM users WHERE is_banned = 0")
    users = c.fetchall()
    
    sent = 0
    for (uid,) in users:
        try:
            bot.send_message(uid, f"📢 **𝐁𝐑𝐎𝐀𝐃𝐂𝐀𝐒𝐓**\n\n{broadcast_msg}\n\n{BRAND}", parse_mode="Markdown")
            sent += 1
            time.sleep(0.05)
        except:
            continue
    
    bot.reply_to(message, f"✅ 𝐁𝐫𝐨𝐚𝐝𝐜𝐚𝐬𝐭 𝐬𝐞𝐧𝐭 𝐭𝐨 {sent} 𝐮𝐬𝐞𝐫𝐬!")

@bot.message_handler(commands=['stats'])
def stats_command(message):
    user_id = message.from_user.id
    
    if user_id != OWNER_ID:
        bot.reply_to(message, "❌ 𝐎𝐧𝐥𝐲 𝐨𝐰𝐧𝐞𝐫 𝐜𝐚𝐧 𝐮𝐬𝐞 𝐭𝐡𝐢𝐬!")
        return
    
    c.execute("SELECT COUNT(*) FROM users")
    total_users = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM users WHERE is_admin = 1")
    total_admins = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM banned_users")
    total_banned = c.fetchone()[0]
    
    c.execute("SELECT SUM(credits_used) FROM users")
    total_commands = c.fetchone()[0] or 0
    
    msg_text = f"""
📊 **𝐁𝐎𝐓 𝐒𝐓𝐀𝐓𝐈𝐒𝐓𝐈𝐂𝐒**
━━━━━━━━━━━━━━━━
👥 𝐓𝐨𝐭𝐚𝐥 𝐔𝐬𝐞𝐫𝐬: {total_users}
👑 𝐓𝐨𝐭𝐚𝐥 𝐀𝐝𝐦𝐢𝐧𝐬: {total_admins}
🔴 𝐁𝐚𝐧𝐧𝐞𝐝 𝐔𝐬𝐞𝐫𝐬: {total_banned}
📊 𝐂𝐨𝐦𝐦𝐚𝐧𝐝𝐬 𝐔𝐬𝐞𝐝: {total_commands}
"""
    bot.reply_to(message, msg_text, parse_mode="Markdown")

# ==================== ERROR HANDLER ====================
@bot.message_handler(func=lambda message: True)
def handle_all(message):
    bot.reply_to(message, f"❌ /help", parse_mode="Markdown")

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
    print("🚀 Tatsumaki Bot Starting...")
    print(f"👑 {BRAND}")
    print(f"👑 Owner ID: {OWNER_ID}")
    print(f"⚡ Ultra Fast Mode: 0.23s Response")
    print("=" * 30)
    
    try:
        bot.remove_webhook()
        time.sleep(1)
    except:
        pass
    
    while True:
        try:
            bot.infinity_polling(timeout=30)
        except Exception as e:
            print(f"❌ Error: {e}")
            time.sleep(2)

if __name__ == "__main__":
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    run_bot()
